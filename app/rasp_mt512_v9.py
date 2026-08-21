#!/usr/bin/env python3
"""Servicio edge MT-512E Log v09/Sitrad para Python 3.4.

Dependencias externas: PySerial 2.6. Lee los controladores cada minuto,
conserva mediciones en SQLite y las envia por HTTPS. Los comandos remotos son
idempotentes y se verifican mediante una nueva lectura del controlador.
"""
from __future__ import print_function

import argparse
import binascii
import datetime
import fcntl
import json
import logging
import os
import signal
import sqlite3
import struct
import sys
import termios
import time
import uuid

try:
    from urllib.error import HTTPError, URLError
    from urllib.parse import quote
    from urllib.request import Request, urlopen
except ImportError:  # pragma: no cover
    from urllib2 import HTTPError, Request, URLError, urlopen
    from urllib import quote

import serial


VERSION = "2026-08-21-mt512e-gateway-py34-v1"
LOGGER = logging.getLogger("brew_temperature_gateway")
BAUDRATE = 28800
READ_COMMAND = 0x20
WRITE_SETUP_COMMAND = 0x40
SETPOINT_FUNCTION = 0x00
FRAME_LENGTH = 82
WRITE_ACK = bytes(bytearray((0x16, 0x10)))

PARITY_MARK = getattr(serial, "PARITY_MARK", "M")
PARITY_SPACE = getattr(serial, "PARITY_SPACE", "S")
PARITY_EVEN = getattr(serial, "PARITY_EVEN", "E")
PARITY_ODD = getattr(serial, "PARITY_ODD", "O")
PARITY_NONE = getattr(serial, "PARITY_NONE", "N")
CMSPAR = getattr(termios, "CMSPAR", 0x40000000)
CBAUD = getattr(termios, "CBAUD", 0x100F)
BOTHER = 0x1000
TERMIOS2_FORMAT = "=IIIIB19BII"
TERMIOS2_SIZE = struct.calcsize(TERMIOS2_FORMAT)


def ioctl_code(direction, type_character, number, size):
    return ((direction << 30) | (size << 16) |
            (ord(type_character) << 8) | number)


TCGETS2 = ioctl_code(2, "T", 0x2A, TERMIOS2_SIZE)
TCSETS2 = ioctl_code(1, "T", 0x2B, TERMIOS2_SIZE)


class GatewayError(RuntimeError):
    pass


class ApiError(GatewayError):
    pass


class ControllerError(GatewayError):
    pass


def utc_now_iso():
    return datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def one_byte(value):
    return bytes(bytearray((value,)))


def hexdump(data):
    encoded = binascii.hexlify(data).decode("ascii").upper()
    return " ".join(encoded[index:index + 2]
                    for index in range(0, len(encoded), 2))


def get_termios2(port):
    payload = bytearray(TERMIOS2_SIZE)
    fcntl.ioctl(port.fileno(), TCGETS2, payload, True)
    return list(struct.unpack(TERMIOS2_FORMAT, bytes(payload)))


def put_termios2(port, values):
    payload = struct.pack(TERMIOS2_FORMAT, *values)
    fcntl.ioctl(port.fileno(), TCSETS2, payload)


def configure_baudrate(port, baudrate):
    try:
        values = get_termios2(port)
        values[2] = (values[2] & ~CBAUD) | BOTHER
        values[-2] = baudrate
        values[-1] = baudrate
        put_termios2(port, values)
        actual = get_termios2(port)
        if actual[-2] != baudrate or actual[-1] != baudrate:
            raise ControllerError(
                "el driver no conservo %d baudios (leyo %d/%d)" % (
                    baudrate, actual[-2], actual[-1]
                )
            )
    except (IOError, OSError, fcntl.error) as error:
        raise ControllerError(
            "termios2 no pudo configurar %d baudios: %s" % (baudrate, error)
        )


def set_parity(port, parity):
    try:
        values = get_termios2(port)
        control = values[2]
        control &= ~(termios.PARENB | termios.PARODD | CMSPAR)
        if parity == PARITY_NONE:
            pass
        elif parity == PARITY_EVEN:
            control |= termios.PARENB
        elif parity == PARITY_ODD:
            control |= termios.PARENB | termios.PARODD
        elif parity == PARITY_MARK:
            control |= termios.PARENB | termios.PARODD | CMSPAR
        elif parity == PARITY_SPACE:
            control |= termios.PARENB | CMSPAR
        else:
            raise ControllerError("paridad desconocida: %s" % parity)
        values[2] = control
        put_termios2(port, values)
    except (IOError, OSError, fcntl.error) as error:
        raise ControllerError(
            "termios2 no pudo configurar paridad %s: %s" % (parity, error)
        )


def send_address_and_payload(port, address, payload):
    set_parity(port, PARITY_MARK)
    port.write(one_byte(address))
    port.flush()
    time.sleep(0.003)
    set_parity(port, PARITY_SPACE)
    port.write(payload)
    port.flush()


def read_response(port, timeout, silence=0.040):
    deadline = time.time() + timeout
    last_byte_at = None
    received = bytearray()
    while time.time() < deadline:
        waiting = port.inWaiting()
        if waiting:
            chunk = port.read(waiting)
            if chunk:
                received.extend(chunk)
                last_byte_at = time.time()
        elif last_byte_at is not None and time.time() - last_byte_at >= silence:
            break
        else:
            time.sleep(0.003)
    return bytes(received)


def signed_be16(high, low):
    value = (high << 8) | low
    return value - 65536 if value & 0x8000 else value


def raw_to_be16(value):
    if value < -32768 or value > 32767:
        raise ControllerError("valor fuera de int16: %d" % value)
    unsigned = value & 0xFFFF
    return ((unsigned >> 8) & 0xFF, unsigned & 0xFF)


def command_checksum(address, payload_without_checksum):
    logical = bytearray((address,)) + bytearray(payload_without_checksum)
    return sum(logical[index] for index in range(len(logical))
               if index != 1) & 0xFF


def build_setpoint_payload(address, setpoint_raw):
    high, low = raw_to_be16(setpoint_raw)
    payload = bytearray((
        WRITE_SETUP_COMMAND, SETPOINT_FUNCTION, high, low
    ))
    payload.append(command_checksum(address, payload))
    return bytes(payload)


def decode_frame(frame, expected_id):
    if len(frame) != FRAME_LENGTH:
        raise ControllerError(
            "longitud %d; se esperaban %d bytes; RX=%s" % (
                len(frame), FRAME_LENGTH, hexdump(frame)
            )
        )
    if frame[0] != expected_id:
        raise ControllerError(
            "respondio ID %d; se esperaba %d" % (frame[0], expected_id)
        )
    calculated = sum(bytearray(frame[:-2])) & 0xFF
    if calculated != frame[-1]:
        raise ControllerError(
            "checksum invalido calculado=%02X recibido=%02X" % (
                calculated, frame[-1]
            )
        )
    temperature_raw = signed_be16(frame[11], frame[12])
    setpoint_raw = signed_be16(frame[78], frame[79])
    flags_p1 = frame[8]
    return {
        "device_id": frame[0],
        "firmware_version": frame[3],
        "temperature_c": temperature_raw / 10.0,
        "temperature_raw": temperature_raw,
        "setpoint_c": setpoint_raw / 10.0,
        "setpoint_raw": setpoint_raw,
        "output_active": bool(flags_p1 & 0x04),
        "sensor_error": bool(flags_p1 & 0x01),
        "flags_p1": flags_p1,
    }


class SitradBus(object):
    def __init__(self, port_name, timeout):
        try:
            self.port = serial.Serial(
                port=port_name,
                baudrate=38400,
                bytesize=serial.EIGHTBITS,
                parity=PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=0.02
            )
        except (serial.SerialException, ValueError, TypeError,
                IOError, OSError) as error:
            raise ControllerError("no se pudo abrir %s: %s" % (
                port_name, error
            ))
        self.timeout = timeout
        try:
            configure_baudrate(self.port, BAUDRATE)
        except Exception:
            self.port.close()
            raise

    def read_state(self, device_id):
        self.port.flushInput()
        self.port.flushOutput()
        send_address_and_payload(self.port, device_id, one_byte(READ_COMMAND))
        frame = read_response(self.port, self.timeout)
        if not frame:
            raise ControllerError("ID %d sin respuesta" % device_id)
        return decode_frame(frame, device_id)

    def set_setpoint(self, device_id, value_c, expected_current_c,
                     minimum_c, maximum_c, maximum_delta_c):
        before = self.read_state(device_id)
        target_raw = int(round(float(value_c) * 10.0))
        expected_raw = int(round(float(expected_current_c) * 10.0))
        if before["setpoint_raw"] != expected_raw:
            raise ControllerError(
                "setpoint actual %.1f C; el comando esperaba %.1f C" % (
                    before["setpoint_c"], float(expected_current_c)
                )
            )
        if not float(minimum_c) <= float(value_c) <= float(maximum_c):
            raise ControllerError(
                "setpoint %.1f fuera de limites [%.1f, %.1f]" % (
                    float(value_c), float(minimum_c), float(maximum_c)
                )
            )
        if abs(target_raw - before["setpoint_raw"]) > int(
                round(float(maximum_delta_c) * 10.0)):
            raise ControllerError(
                "cambio mayor que el maximo permitido de %.1f C" %
                float(maximum_delta_c)
            )

        payload = build_setpoint_payload(device_id, target_raw)
        self.port.flushInput()
        self.port.flushOutput()
        send_address_and_payload(self.port, device_id, payload)
        acknowledgement = read_response(self.port, self.timeout)
        if acknowledgement != WRITE_ACK:
            raise ControllerError(
                "ACK de escritura inesperado: %s" % (
                    hexdump(acknowledgement) if acknowledgement else "vacio"
                )
            )
        for unused_attempt in range(5):
            time.sleep(0.5)
            after = self.read_state(device_id)
            if after["setpoint_raw"] == target_raw:
                return after
        raise ControllerError(
            "el controlador no confirmo el setpoint %.1f C" % float(value_c)
        )

    def close(self):
        self.port.close()


class LocalStore(object):
    def __init__(self, path):
        directory = os.path.dirname(os.path.abspath(path))
        if not os.path.isdir(directory):
            os.makedirs(directory)
        self.connection = sqlite3.connect(path)
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.executescript("""
            CREATE TABLE IF NOT EXISTS readings (
                reading_id TEXT PRIMARY KEY,
                payload TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS command_results (
                command_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                message TEXT NOT NULL,
                acknowledged INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS controller_cache (
                controller_id TEXT PRIMARY KEY,
                payload TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS gateway_metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
        """)
        self.connection.commit()

    def add_reading(self, payload):
        self.connection.execute(
            "INSERT OR IGNORE INTO readings "
            "(reading_id, payload, created_at) VALUES (?, ?, ?)",
            (payload["reading_id"], json.dumps(payload, separators=(",", ":")),
             payload["observed_at"])
        )
        self.connection.commit()

    def pending_readings(self, limit):
        rows = self.connection.execute(
            "SELECT payload FROM readings ORDER BY created_at, reading_id LIMIT ?",
            (limit,)
        ).fetchall()
        return [json.loads(row[0]) for row in rows]

    def remove_readings(self, reading_ids):
        self.connection.executemany(
            "DELETE FROM readings WHERE reading_id = ?",
            ((reading_id,) for reading_id in reading_ids)
        )
        self.connection.commit()

    def save_controllers(self, controllers):
        now = utc_now_iso()
        self.connection.executemany(
            "INSERT OR REPLACE INTO controller_cache "
            "(controller_id, payload, updated_at) VALUES (?, ?, ?)",
            ((item["controller_id"], json.dumps(item, separators=(",", ":")), now)
             for item in controllers)
        )
        active_ids = [item["controller_id"] for item in controllers]
        if active_ids:
            placeholders = ",".join("?" for unused in active_ids)
            self.connection.execute(
                "DELETE FROM controller_cache WHERE controller_id NOT IN (%s)" %
                placeholders, active_ids
            )
        else:
            self.connection.execute("DELETE FROM controller_cache")
        self.connection.execute(
            "INSERT OR REPLACE INTO gateway_metadata (key, value) "
            "VALUES ('controllers_initialized', '1')"
        )
        self.connection.commit()

    def cached_controllers(self):
        rows = self.connection.execute(
            "SELECT payload FROM controller_cache ORDER BY controller_id"
        ).fetchall()
        return [json.loads(row[0]) for row in rows]

    def controller_cache_initialized(self):
        row = self.connection.execute(
            "SELECT value FROM gateway_metadata "
            "WHERE key = 'controllers_initialized'"
        ).fetchone()
        return row is not None

    def command_result(self, command_id):
        row = self.connection.execute(
            "SELECT status, message, acknowledged FROM command_results "
            "WHERE command_id = ?", (command_id,)
        ).fetchone()
        if row is None:
            return None
        return {"status": row[0], "message": row[1],
                "acknowledged": bool(row[2])}

    def save_command_result(self, command_id, status, message):
        self.connection.execute(
            "INSERT OR REPLACE INTO command_results "
            "(command_id, status, message, acknowledged, updated_at) "
            "VALUES (?, ?, ?, 0, ?)",
            (command_id, status, message, utc_now_iso())
        )
        self.connection.commit()

    def pending_command_results(self):
        rows = self.connection.execute(
            "SELECT command_id, status, message FROM command_results "
            "WHERE acknowledged = 0 ORDER BY updated_at"
        ).fetchall()
        return [{"command_id": row[0], "status": row[1], "message": row[2]}
                for row in rows]

    def mark_command_acknowledged(self, command_id):
        self.connection.execute(
            "UPDATE command_results SET acknowledged = 1 WHERE command_id = ?",
            (command_id,)
        )
        self.connection.commit()

    def close(self):
        self.connection.close()


class ApiClient(object):
    def __init__(self, base_url, token, gateway_id, timeout):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.gateway_id = gateway_id
        self.timeout = timeout

    def request(self, method, path, payload=None):
        data = None
        if payload is not None:
            data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        request = Request(self.base_url + path, data=data)
        request.get_method = lambda: method
        request.add_header("Authorization", "Bearer " + self.token)
        request.add_header("Accept", "application/json")
        request.add_header("Content-Type", "application/json")
        try:
            response = urlopen(request, timeout=self.timeout)
            body = response.read()
        except HTTPError as error:
            detail = error.read().decode("utf-8", "replace")
            raise ApiError("HTTP %d: %s" % (error.code, detail))
        except (URLError, IOError, OSError) as error:
            raise ApiError("fallo comunicando con la VPS: %s" % error)
        if not body:
            return {}
        try:
            parsed = json.loads(body.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as error:
            raise ApiError("respuesta JSON invalida: %s" % error)
        if not isinstance(parsed, dict):
            raise ApiError("la VPS no respondio un objeto JSON")
        return parsed

    def fetch_controllers(self):
        path = "/api/edge/v1/gateways/%s/controllers" % quote(
            self.gateway_id, safe=""
        )
        result = self.request("GET", path)
        controllers = result.get("controllers", [])
        if not isinstance(controllers, list):
            raise ApiError("'controllers' no es una lista")
        return controllers

    def send_readings(self, readings):
        return self.request(
            "POST", "/api/edge/v1/temperature-readings",
            {"readings": readings}
        )

    def fetch_commands(self):
        path = "/api/edge/v1/gateways/%s/commands" % quote(
            self.gateway_id, safe=""
        )
        result = self.request("GET", path)
        commands = result.get("commands", [])
        if not isinstance(commands, list):
            raise ApiError("'commands' no es una lista")
        return commands

    def acknowledge(self, command_id, status, message):
        path = "/api/edge/v1/commands/%s/ack" % quote(command_id, safe="")
        self.request("POST", path, {"status": status, "message": message})


def validate_controller(item):
    required = ("controller_id", "device_id", "name",
                "minimum_setpoint_c", "maximum_setpoint_c")
    for key in required:
        if key not in item:
            raise GatewayError("controlador sin campo '%s'" % key)
    parsed = {
        "controller_id": str(item["controller_id"]),
        "device_id": int(item["device_id"]),
        "name": str(item["name"]),
        "minimum_setpoint_c": float(item["minimum_setpoint_c"]),
        "maximum_setpoint_c": float(item["maximum_setpoint_c"]),
    }
    if not 1 <= parsed["device_id"] <= 247:
        raise GatewayError("device_id fuera de rango")
    if parsed["minimum_setpoint_c"] >= parsed["maximum_setpoint_c"]:
        raise GatewayError("limites de setpoint invalidos")
    return parsed


def load_config(path):
    with open(path, "r") as config_file:
        raw = json.load(config_file)
    required = ("gateway_id", "serial_port", "database_path",
                "poll_interval_seconds", "api_base_url")
    for key in required:
        if key not in raw:
            raise GatewayError("falta '%s' en la configuracion" % key)
    token_env = str(raw.get("api_token_env", "BREW_TEMPERATURE_API_TOKEN"))
    token = os.environ.get(token_env, "")
    api_enabled = bool(raw.get("api_enabled", True))
    if api_enabled and not token:
        raise GatewayError("falta la variable de entorno %s" % token_env)
    controllers = [validate_controller(item)
                   for item in raw.get("fallback_controllers", [])]
    return {
        "gateway_id": str(raw["gateway_id"]),
        "serial_port": str(raw["serial_port"]),
        "database_path": str(raw["database_path"]),
        "poll_interval_seconds": max(5, int(raw["poll_interval_seconds"])),
        "serial_timeout_seconds": float(raw.get("serial_timeout_seconds", 0.8)),
        "api_enabled": api_enabled,
        "api_base_url": str(raw["api_base_url"]),
        "api_token": token,
        "api_timeout_seconds": float(raw.get("api_timeout_seconds", 10.0)),
        "batch_size": int(raw.get("batch_size", 100)),
        "command_max_delta_c": float(raw.get("command_max_delta_c", 5.0)),
        "fallback_controllers": controllers,
    }


class GatewayService(object):
    def __init__(self, config, store, bus, api):
        self.config = config
        self.store = store
        self.bus = bus
        self.api = api
        self.running = True

    def stop(self, unused_signum=None, unused_frame=None):
        self.running = False

    def controllers(self):
        if self.api is not None:
            try:
                remote = [validate_controller(item)
                          for item in self.api.fetch_controllers()]
                self.store.save_controllers(remote)
                return remote
            except (ApiError, GatewayError) as error:
                LOGGER.warning("No se actualizo la lista de controladores: %s", error)
        cached = self.store.cached_controllers()
        if cached or self.store.controller_cache_initialized():
            return cached
        return self.config["fallback_controllers"]

    def poll(self, controllers):
        for controller in controllers:
            observed_at = utc_now_iso()
            try:
                state = self.bus.read_state(controller["device_id"])
            except ControllerError as error:
                LOGGER.error("%s: %s", controller["controller_id"], error)
                continue
            payload = {
                "reading_id": str(uuid.uuid4()),
                "gateway_id": self.config["gateway_id"],
                "controller_id": controller["controller_id"],
                "device_id": controller["device_id"],
                "observed_at": observed_at,
                "temperature_c": state["temperature_c"],
                "setpoint_c": state["setpoint_c"],
                "output_active": state["output_active"],
                "sensor_error": state["sensor_error"],
                "firmware_version": state["firmware_version"],
            }
            self.store.add_reading(payload)
            LOGGER.info(
                "%s: temperatura=%.1f C setpoint=%.1f C salida=%s",
                controller["name"], state["temperature_c"],
                state["setpoint_c"],
                "activa" if state["output_active"] else "inactiva"
            )

    def flush_readings(self):
        if self.api is None:
            return
        readings = self.store.pending_readings(self.config["batch_size"])
        if not readings:
            return
        try:
            self.api.send_readings(readings)
        except ApiError as error:
            LOGGER.warning("Lecturas conservadas para reintento: %s", error)
            return
        self.store.remove_readings([item["reading_id"] for item in readings])

    def execute_command(self, command, controller_map):
        command_id = str(command["command_id"])
        previous = self.store.command_result(command_id)
        if previous is not None:
            return
        try:
            controller = controller_map[str(command["controller_id"])]
            if command.get("action") != "set_setpoint":
                raise ControllerError("accion no soportada")
            if "expected_setpoint_c" not in command:
                raise ControllerError("falta expected_setpoint_c")
            state = self.bus.set_setpoint(
                controller["device_id"], float(command["value"]),
                float(command["expected_setpoint_c"]),
                controller["minimum_setpoint_c"],
                controller["maximum_setpoint_c"],
                self.config["command_max_delta_c"]
            )
            message = "setpoint confirmado en %.1f C" % state["setpoint_c"]
            status = "completed"
            LOGGER.info("Comando %s: %s", command_id, message)
        except (KeyError, TypeError, ValueError, ControllerError) as error:
            status = "failed"
            message = str(error)
            LOGGER.error("Comando %s fallido: %s", command_id, message)
        self.store.save_command_result(command_id, status, message)

    def flush_command_results(self):
        if self.api is None:
            return
        for result in self.store.pending_command_results():
            try:
                self.api.acknowledge(
                    result["command_id"], result["status"], result["message"]
                )
            except ApiError as error:
                LOGGER.warning("ACK %s pendiente: %s", result["command_id"], error)
                return
            self.store.mark_command_acknowledged(result["command_id"])

    def process_commands(self, controllers):
        if self.api is None:
            return
        self.flush_command_results()
        try:
            commands = self.api.fetch_commands()
        except ApiError as error:
            LOGGER.warning("No se descargaron comandos: %s", error)
            return
        controller_map = dict((item["controller_id"], item)
                              for item in controllers)
        for command in commands:
            self.execute_command(command, controller_map)
        self.flush_command_results()

    def run_once(self):
        controllers = self.controllers()
        if not controllers:
            LOGGER.warning("No hay controladores habilitados")
        self.poll(controllers)
        self.flush_readings()
        self.process_commands(controllers)

    def run_forever(self):
        while self.running:
            started = time.time()
            try:
                self.run_once()
            except Exception:
                LOGGER.exception("Fallo no controlado en el ciclo")
            remaining = self.config["poll_interval_seconds"] - (
                time.time() - started
            )
            while self.running and remaining > 0:
                delay = min(1.0, remaining)
                time.sleep(delay)
                remaining -= delay


def build_parser():
    parser = argparse.ArgumentParser(
        description="Servicio Sitrad MT-512E Log v09 para Raspberry Pi"
    )
    parser.add_argument(
        "--config", default="/etc/brew-temperature-gateway/config.json"
    )
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--check-config", action="store_true")
    parser.add_argument("--debug", action="store_true")
    return parser


def main():
    args = build_parser().parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s"
    )
    try:
        config = load_config(args.config)
    except (IOError, OSError, ValueError, GatewayError) as error:
        raise SystemExit("Configuracion invalida: %s" % error)
    if args.check_config:
        print("Configuracion valida para %s" % config["gateway_id"])
        return 0

    store = LocalStore(config["database_path"])
    bus = None
    try:
        bus = SitradBus(
            config["serial_port"], config["serial_timeout_seconds"]
        )
        api = None
        if config["api_enabled"]:
            api = ApiClient(
                config["api_base_url"], config["api_token"],
                config["gateway_id"], config["api_timeout_seconds"]
            )
        service = GatewayService(config, store, bus, api)
        signal.signal(signal.SIGTERM, service.stop)
        signal.signal(signal.SIGINT, service.stop)
        if args.once:
            service.run_once()
        else:
            service.run_forever()
    except ControllerError as error:
        LOGGER.error("No se inicio el bus Sitrad: %s", error)
        return 1
    finally:
        if bus is not None:
            bus.close()
        store.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
