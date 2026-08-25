#!/usr/bin/env python3
"""Lector autonomo MT-512E Log v09 mediante Sitrad, Python 3.4.

No depende de las sondas exploratorias. Configura 28800 baudios y la paridad
MARK/SPACE directamente mediante Linux termios2. Solo transmite la consulta de
estado 0x20 observada y validada en el equipo.
"""
from __future__ import print_function

import argparse
import binascii
import fcntl
import json
import struct
import sys
import termios
import time

import serial


VERSION = "2026-08-24-mt512e-reader-standalone-v5"
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
    """Configura una velocidad arbitraria mediante Linux termios2/BOTHER."""
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
    """Configura N/E/O/M/S por termios2 y conserva BOTHER/28800."""
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


def send_query(port, address):
    """Envia ID con MARK y comando de estado 0x20 con SPACE."""
    set_parity(port, PARITY_MARK)
    port.write(one_byte(address))
    port.flush()
    time.sleep(0.003)

    set_parity(port, PARITY_SPACE)
    port.write(one_byte(0x20))
    port.flush()


def read_response(port, timeout):
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
        elif last_byte_at is not None and time.time() - last_byte_at >= 0.040:
            break
        else:
            time.sleep(0.003)
    return bytes(received)


def signed_be16(high, low):
    value = (high << 8) | low
    return value - 65536 if value & 0x8000 else value


def decode_frame(frame, expected_id):
    if len(frame) != 82:
        raise ValueError("longitud inesperada: %d; se esperaban 82 bytes" % len(frame))
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

    day = frame[13]
    month = frame[14]
    year = 2000 + frame[15]
    hour = frame[16]
    minute = frame[17]
    second = frame[18]
    device_time = "%04d-%02d-%02dT%02d:%02d:%02d" % (
        year, month, day, hour, minute, second
    )

    status_raw = frame[-2]
    output_status_raw = frame[10]
    return {
        "device_id": frame[0],
        "model_signature": hexdump(frame[1:3]),
        "firmware_version": frame[3],
        "temperature_c": temperature_raw / 10.0,
        "temperature_raw": temperature_raw,
        "setpoint_c": setpoint_raw / 10.0,
        "setpoint_raw": setpoint_raw,
        "device_time": device_time,
        "status_raw": status_raw,
        "output_status_raw": output_status_raw,
        "output_active": bool(output_status_raw & 0x01),
        "checksum": received_checksum,
        "checksum_valid": True,
        "frame_length": len(frame),
    }


def query(port, device_id, timeout):
    port.flushInput()
    port.flushOutput()
    send_query(port, device_id)
    return read_response(port, timeout)


def build_parser():
    parser = argparse.ArgumentParser(
        description="Lee temperatura y setpoint de un MT-512E Log v09"
    )
    parser.add_argument("--port", required=True)
    parser.add_argument("--device-id", type=int, default=5)
    parser.add_argument("--count", type=int, default=1)
    parser.add_argument("--interval", type=float, default=1.0)
    parser.add_argument("--timeout", type=float, default=0.8)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--show-frame", action="store_true")
    return parser


def main():
    args = build_parser().parse_args()
    if not 1 <= args.device_id <= 247:
        raise SystemExit("device-id debe estar entre 1 y 247")
    if args.count < 1:
        raise SystemExit("count debe ser mayor que cero")

    if not args.json:
        print("Lector version: %s" % VERSION)
        print("SOLO LECTURA: consulta Sitrad 0x20")

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
        configure_baudrate(port, 28800)
        for attempt in range(1, args.count + 1):
            frame = query(port, args.device_id, args.timeout)
            if not frame:
                print("SIN RESPUESTA", file=sys.stderr)
            else:
                try:
                    decoded = decode_frame(frame, args.device_id)
                except ValueError as error:
                    print("TRAMA INVALIDA: %s" % error, file=sys.stderr)
                    print("RX: %s" % hexdump(frame), file=sys.stderr)
                else:
                    if args.json:
                        print(json.dumps(decoded, sort_keys=True))
                    else:
                        print("\nLectura %d/%d" % (attempt, args.count))
                        print("  ID: %d | firmware: %d" % (
                            decoded["device_id"], decoded["firmware_version"]
                        ))
                        print("  Temperatura: %.1f C (raw=%d)" % (
                            decoded["temperature_c"], decoded["temperature_raw"]
                        ))
                        print("  Setpoint: %.1f C (raw=%d)" % (
                            decoded["setpoint_c"], decoded["setpoint_raw"]
                        ))
                        print("  Salida/copo: %s (raw=0x%02X)" % (
                            "ACTIVA" if decoded["output_active"] else "INACTIVA",
                            decoded["output_status_raw"]
                        ))
                        print("  Reloj: %s" % decoded["device_time"])
                        print("  Estado no decodificado: 0x%02X" % (
                            decoded["status_raw"]
                        ))
                        print("  Checksum valido")
                    if args.show_frame:
                        print("  RX: %s" % hexdump(frame))
            if attempt < args.count:
                time.sleep(args.interval)
    except RuntimeError as error:
        raise SystemExit(str(error))
    finally:
        port.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
