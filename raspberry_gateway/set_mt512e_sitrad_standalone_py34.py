#!/usr/bin/env python3
"""Lee y cambia el setpoint de un MT-512E Log v09 mediante Sitrad.

Compatible con Python 3.4 y PySerial 2.6. Configura 28800 baudios y la
paridad MARK/SPACE directamente mediante Linux termios2.

La escritura esta protegida: antes de transmitir exige una lectura valida,
que --expect-current coincida con el setpoint leido y --confirm-write.
"""
from __future__ import print_function

import argparse
import binascii
import fcntl
import struct
import sys
import termios
import time
from decimal import Decimal, InvalidOperation

import serial


VERSION = "2026-08-24-mt512e-setpoint-standalone-v2"
BAUDRATE = 28800
READ_COMMAND = 0x20
WRITE_SETUP_COMMAND = 0x40
SETPOINT_FUNCTION = 0x00
FRAME_LENGTH = 82

PARITY_MARK = getattr(serial, "PARITY_MARK", "M")
PARITY_SPACE = getattr(serial, "PARITY_SPACE", "S")
PARITY_EVEN = getattr(serial, "PARITY_EVEN", "E")
PARITY_ODD = getattr(serial, "PARITY_ODD", "O")
PARITY_NONE = getattr(serial, "PARITY_NONE", "N")
CMSPAR = getattr(termios, "CMSPAR", 0x40000000)
CBAUD = getattr(termios, "CBAUD", 0x100F)
BOTHER = 0x1000

# Linux asm-generic/termbits.h: cuatro tcflag_t, c_line, 19 cc_t y dos speed_t.
TERMIOS2_FORMAT = "=IIIIB19BII"
TERMIOS2_SIZE = struct.calcsize(TERMIOS2_FORMAT)


def ioctl_code(direction, type_character, number, size):
    return ((direction << 30) | (size << 16) |
            (ord(type_character) << 8) | number)


TCGETS2 = ioctl_code(2, "T", 0x2A, TERMIOS2_SIZE)
TCSETS2 = ioctl_code(1, "T", 0x2B, TERMIOS2_SIZE)


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
            raise RuntimeError(
                "el driver no conservo la velocidad %d (leyo %d/%d)" % (
                    baudrate, actual[-2], actual[-1]
                )
            )
    except (IOError, OSError, fcntl.error) as error:
        raise RuntimeError(
            "termios2 no pudo configurar %d baudios: %s" % (
                baudrate, error
            )
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
            raise RuntimeError("paridad desconocida: %s" % parity)

        values[2] = control
        put_termios2(port, values)

        actual = get_termios2(port)[2]
        mask = termios.PARENB | termios.PARODD | CMSPAR
        if (actual & mask) != (control & mask):
            raise RuntimeError(
                "el driver no conservo la configuracion de paridad %s" % parity
            )
    except (OSError, IOError, fcntl.error) as error:
        raise RuntimeError(
            "termios2 no pudo configurar paridad %s: %s" % (parity, error)
        )


def send_address_and_payload(port, address, payload):
    """Envia el ID con MARK y todos los bytes restantes con SPACE."""
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
        raise ValueError("valor fuera del rango int16: %d" % value)
    unsigned = value & 0xFFFF
    return ((unsigned >> 8) & 0xFF, unsigned & 0xFF)


def parse_temperature(value):
    try:
        parsed = Decimal(value)
    except (InvalidOperation, ValueError):
        raise argparse.ArgumentTypeError("temperatura invalida: %s" % value)

    if not parsed.is_finite():
        raise argparse.ArgumentTypeError("la temperatura debe ser finita")
    if parsed < Decimal("-50.0") or parsed > Decimal("200.0"):
        raise argparse.ArgumentTypeError(
            "la temperatura debe estar entre -50.0 y 200.0 C"
        )
    if parsed != parsed.quantize(Decimal("0.1")):
        raise argparse.ArgumentTypeError(
            "use como maximo un decimal, por ejemplo 16.5"
        )
    return parsed


def temperature_to_raw(value):
    return int(value * Decimal(10))


def command_checksum(address, payload_without_checksum):
    """Checksum Sitrad de comando: omite el byte de comando (indice 1)."""
    logical_frame = bytearray((address,)) + bytearray(payload_without_checksum)
    return sum(logical_frame[index]
               for index in range(len(logical_frame))
               if index != 1) & 0xFF


def build_setpoint_payload(address, setpoint_raw):
    high, low = raw_to_be16(setpoint_raw)
    payload = bytearray((
        WRITE_SETUP_COMMAND,
        SETPOINT_FUNCTION,
        high,
        low,
    ))
    payload.append(command_checksum(address, payload))
    return bytes(payload)


def decode_frame(frame, expected_id):
    if len(frame) != FRAME_LENGTH:
        raise ValueError(
            "longitud inesperada: %d; se esperaban %d bytes" % (
                len(frame), FRAME_LENGTH
            )
        )
    if frame[0] != expected_id:
        raise ValueError("respondio ID %d; se esperaba ID %d" % (
            frame[0], expected_id
        ))

    expected_checksum = sum(bytearray(frame[:-2])) & 0xFF
    received_checksum = frame[-1]
    if expected_checksum != received_checksum:
        raise ValueError("checksum invalido: calculado=%02X recibido=%02X" % (
            expected_checksum, received_checksum
        ))

    temperature_raw = signed_be16(frame[11], frame[12])
    setpoint_raw = signed_be16(frame[78], frame[79])
    sensor_flags = frame[8]
    output_status_raw = frame[10]
    return {
        "device_id": frame[0],
        "firmware_version": frame[3],
        "temperature_raw": temperature_raw,
        "temperature_c": temperature_raw / 10.0,
        "setpoint_raw": setpoint_raw,
        "setpoint_c": setpoint_raw / 10.0,
        "sensor_flags": sensor_flags,
        "output_status_raw": output_status_raw,
        "output_active": bool(output_status_raw & 0x01),
        "checksum_valid": True,
    }


def query(port, device_id, timeout):
    port.flushInput()
    port.flushOutput()
    send_address_and_payload(port, device_id, one_byte(READ_COMMAND))
    return read_response(port, timeout)


def read_valid_state(port, device_id, timeout):
    frame = query(port, device_id, timeout)
    if not frame:
        raise RuntimeError("el controlador no respondio a la consulta 0x20")
    try:
        decoded = decode_frame(frame, device_id)
    except ValueError as error:
        raise RuntimeError("respuesta de lectura invalida: %s; RX=%s" % (
            error, hexdump(frame)
        ))
    return decoded, frame


def send_setpoint(port, device_id, payload, timeout):
    port.flushInput()
    port.flushOutput()
    send_address_and_payload(port, device_id, payload)
    return read_response(port, timeout)


def build_parser():
    parser = argparse.ArgumentParser(
        description="Cambia con protecciones el setpoint de un MT-512E Log v09"
    )
    parser.add_argument("--port", required=True)
    parser.add_argument("--device-id", type=int, default=5)
    parser.add_argument("--setpoint", required=True, type=parse_temperature)
    parser.add_argument(
        "--expect-current",
        type=parse_temperature,
        help="setpoint que debe tener actualmente el controlador"
    )
    parser.add_argument(
        "--max-delta",
        type=parse_temperature,
        default=Decimal("2.0"),
        help="cambio maximo permitido en C (por defecto: 2.0)"
    )
    parser.add_argument("--timeout", type=float, default=0.8)
    parser.add_argument("--verify-attempts", type=int, default=5)
    parser.add_argument("--verify-interval", type=float, default=0.5)
    parser.add_argument("--show-frame", action="store_true")
    parser.add_argument(
        "--confirm-write",
        action="store_true",
        help="autoriza expresamente la escritura; sin esta opcion es simulacion"
    )
    return parser


def main():
    args = build_parser().parse_args()
    if not 1 <= args.device_id <= 247:
        raise SystemExit("device-id debe estar entre 1 y 247")
    if args.timeout <= 0:
        raise SystemExit("timeout debe ser mayor que cero")
    if args.verify_attempts < 1:
        raise SystemExit("verify-attempts debe ser mayor que cero")
    if args.max_delta < Decimal("0.0"):
        raise SystemExit("max-delta no puede ser negativo")

    target_raw = temperature_to_raw(args.setpoint)
    payload = build_setpoint_payload(args.device_id, target_raw)
    logical_frame = one_byte(args.device_id) + payload

    print("Escritor version: %s" % VERSION)
    print("Objetivo: %.1f C (raw=%d)" % (float(args.setpoint), target_raw))
    print("TX logico: %s" % hexdump(logical_frame))

    if not args.confirm_write:
        print("SIMULACION: no se transmitio nada.")
        print("Para escribir use --expect-current y --confirm-write.")
        return 0
    if args.expect_current is None:
        raise SystemExit(
            "--confirm-write requiere tambien --expect-current"
        )

    try:
        port = serial.Serial(
            port=args.port,
            baudrate=38400,
            bytesize=serial.EIGHTBITS,
            parity=PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=0.02
        )
    except (serial.SerialException, ValueError, TypeError, OSError, IOError) as error:
        raise SystemExit("No se pudo abrir el puerto: %s" % error)

    try:
        configure_baudrate(port, BAUDRATE)

        before, before_frame = read_valid_state(
            port, args.device_id, args.timeout
        )
        expected_raw = temperature_to_raw(args.expect_current)
        print("Lectura previa:")
        print("  Temperatura: %.1f C" % before["temperature_c"])
        print("  Setpoint: %.1f C" % before["setpoint_c"])
        print("  Salida/copo: %s" % (
            "ACTIVA" if before["output_active"] else "INACTIVA"
        ))
        if args.show_frame:
            print("  RX: %s" % hexdump(before_frame))

        if before["firmware_version"] != 9:
            raise RuntimeError(
                "firmware inesperado %d; este escritor es solo para v09" %
                before["firmware_version"]
            )
        if before["setpoint_raw"] != expected_raw:
            raise RuntimeError(
                "ABORTADO: setpoint leido %.1f C; se esperaba %.1f C" % (
                    before["setpoint_c"], float(args.expect_current)
                )
            )

        delta_raw = abs(target_raw - before["setpoint_raw"])
        max_delta_raw = temperature_to_raw(args.max_delta)
        if delta_raw > max_delta_raw:
            raise RuntimeError(
                "ABORTADO: el cambio de %.1f C supera --max-delta %.1f C" % (
                    delta_raw / 10.0, float(args.max_delta)
                )
            )

        print("Escribiendo comando Sitrad 0x40...")
        acknowledgement = send_setpoint(
            port, args.device_id, payload, args.timeout
        )
        if acknowledgement:
            print("  Respuesta inmediata: %s" % hexdump(acknowledgement))
        else:
            print("  Sin respuesta inmediata; se validara mediante relectura.")

        for attempt in range(1, args.verify_attempts + 1):
            time.sleep(args.verify_interval)
            try:
                after, after_frame = read_valid_state(
                    port, args.device_id, args.timeout
                )
            except RuntimeError as error:
                print("  Verificacion %d/%d: %s" % (
                    attempt, args.verify_attempts, error
                ), file=sys.stderr)
                continue

            print("  Verificacion %d/%d: setpoint %.1f C" % (
                attempt, args.verify_attempts, after["setpoint_c"]
            ))
            if args.show_frame:
                print("  RX: %s" % hexdump(after_frame))
            if after["setpoint_raw"] == target_raw:
                print("CAMBIO CONFIRMADO: setpoint=%.1f C" % after["setpoint_c"])
                return 0

        raise RuntimeError(
            "NO CONFIRMADO: el controlador no reporto el setpoint %.1f C" %
            float(args.setpoint)
        )
    except RuntimeError as error:
        print(str(error), file=sys.stderr)
        return 1
    finally:
        port.close()


if __name__ == "__main__":
    sys.exit(main())
