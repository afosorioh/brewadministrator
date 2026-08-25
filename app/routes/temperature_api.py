import hmac
import os
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from functools import wraps

from flask import Blueprint, current_app, jsonify, request

from app.extensions import db
from app.models import (
    Bache,
    ComandoControladorTemperatura,
    ControladorTemperatura,
    LecturaTemperatura,
)
from app.utils.datetime_utils import utc_now


temperature_api_bp = Blueprint("temperature_edge_api", __name__)


def _configured_token():
    return current_app.config.get("TEMPERATURE_EDGE_API_TOKEN") or os.environ.get(
        "TEMPERATURE_EDGE_API_TOKEN", ""
    )


def edge_token_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        expected = _configured_token()
        authorization = request.headers.get("Authorization", "")
        supplied = authorization[7:] if authorization.startswith("Bearer ") else ""
        if not expected:
            return jsonify({"error": "API edge no configurada"}), 503
        if not supplied or not hmac.compare_digest(str(supplied), str(expected)):
            return jsonify({"error": "token invalido"}), 401
        return view(*args, **kwargs)
    return wrapped


def _parse_datetime(value):
    if not isinstance(value, str) or not value:
        raise ValueError("observed_at es obligatorio")
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as error:
        raise ValueError("observed_at no tiene un formato ISO 8601 valido") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("observed_at debe incluir zona horaria (Z u offset)")
    return parsed.astimezone(timezone.utc).replace(tzinfo=None)


def _decimal_tenth(value, field, minimum=-100.0, maximum=250.0):
    if isinstance(value, bool):
        raise ValueError("%s debe ser numerico" % field)
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValueError("%s debe ser numerico" % field)
    if not parsed.is_finite() or parsed < Decimal(str(minimum)) or parsed > Decimal(str(maximum)):
        raise ValueError("%s fuera de rango" % field)
    if parsed != parsed.quantize(Decimal("0.1")):
        raise ValueError("%s admite un decimal" % field)
    return parsed


@temperature_api_bp.get("/api/edge/v1/gateways/<gateway_id>/controllers")
@edge_token_required
def controllers(gateway_id):
    rows = (
        ControladorTemperatura.query
        .filter_by(gateway_id=gateway_id, activo=True)
        .order_by(ControladorTemperatura.device_id.asc())
        .all()
    )
    return jsonify({
        "controllers": [
            {
                "controller_id": item.codigo,
                "name": item.nombre,
                "device_id": item.device_id,
                "minimum_setpoint_c": float(item.setpoint_min_c),
                "maximum_setpoint_c": float(item.setpoint_max_c),
                "batch_id": item.id_bache_actual,
            }
            for item in rows
        ]
    })


@temperature_api_bp.post("/api/edge/v1/temperature-readings")
@edge_token_required
def receive_readings():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or not isinstance(payload.get("readings"), list):
        return jsonify({"error": "se requiere readings como lista"}), 400
    readings = payload["readings"]
    if not 1 <= len(readings) <= 500:
        return jsonify({"error": "el lote debe contener entre 1 y 500 lecturas"}), 400

    accepted = 0
    duplicates = 0
    try:
        for raw in readings:
            if not isinstance(raw, dict):
                raise ValueError("cada lectura debe ser un objeto")
            reading_id = str(raw.get("reading_id", ""))
            try:
                uuid.UUID(reading_id)
            except (ValueError, AttributeError):
                raise ValueError("reading_id invalido")

            if db.session.get(LecturaTemperatura, reading_id) is not None:
                duplicates += 1
                continue

            gateway_id = str(raw.get("gateway_id", ""))
            controller_code = str(raw.get("controller_id", ""))
            controller = ControladorTemperatura.query.filter_by(
                codigo=controller_code, gateway_id=gateway_id, activo=True
            ).first()
            if controller is None:
                raise ValueError(
                    "controlador %s no existe o no pertenece a %s" % (
                        controller_code, gateway_id
                    )
                )
            if int(raw.get("device_id")) != controller.device_id:
                raise ValueError("device_id no coincide para %s" % controller_code)

            observed_at = _parse_datetime(raw.get("observed_at"))
            if observed_at > utc_now() + timedelta(minutes=5):
                raise ValueError("observed_at no puede estar en el futuro")
            temperature = _decimal_tenth(raw.get("temperature_c"), "temperature_c")
            setpoint = _decimal_tenth(raw.get("setpoint_c"), "setpoint_c")
            output_active = raw.get("output_active")
            sensor_error = raw.get("sensor_error", False)
            if not isinstance(output_active, bool) or not isinstance(sensor_error, bool):
                raise ValueError("output_active y sensor_error deben ser booleanos")
            firmware = raw.get("firmware_version")
            firmware = int(firmware) if firmware is not None else None
            batch_id = raw.get("batch_id", controller.id_bache_actual)
            if batch_id is not None:
                batch_id = int(batch_id)
                if db.session.get(Bache, batch_id) is None:
                    raise ValueError("batch_id no existe")

            reading = LecturaTemperatura(
                reading_id=reading_id,
                id_controlador=controller.id,
                id_bache=batch_id,
                observado_en=observed_at,
                temperatura_c=temperature,
                setpoint_c=setpoint,
                salida_activa=output_active,
                error_sensor=sensor_error,
                firmware_version=firmware,
            )
            db.session.add(reading)
            if controller.ultima_lectura_en is None or observed_at >= controller.ultima_lectura_en:
                controller.temperatura_actual_c = temperature
                controller.setpoint_actual_c = setpoint
                controller.salida_activa = output_active
                controller.error_sensor = sensor_error
                controller.firmware_version = firmware
                controller.ultima_lectura_en = observed_at
            accepted += 1
        db.session.commit()
    except (ValueError, TypeError) as error:
        db.session.rollback()
        return jsonify({"error": str(error)}), 400
    return jsonify({"accepted": accepted, "duplicates": duplicates})


@temperature_api_bp.get("/api/edge/v1/gateways/<gateway_id>/commands")
@edge_token_required
def commands(gateway_id):
    rows = (
        ComandoControladorTemperatura.query
        .filter(
            ComandoControladorTemperatura.gateway_id == gateway_id,
            ComandoControladorTemperatura.estado.in_(("pending", "delivered")),
        )
        .order_by(ComandoControladorTemperatura.creado_en.asc())
        .limit(50)
        .all()
    )
    now = utc_now()
    response = []
    for item in rows:
        if item.estado == "pending":
            item.estado = "delivered"
            item.entregado_en = now
        response.append({
            "command_id": item.command_id,
            "controller_id": item.controlador.codigo,
            "action": item.accion,
            "value": float(item.valor),
            "expected_setpoint_c": float(item.setpoint_esperado_c),
        })
    db.session.commit()
    return jsonify({"commands": response})


@temperature_api_bp.post("/api/edge/v1/commands/<command_id>/ack")
@edge_token_required
def acknowledge_command(command_id):
    command = db.session.get(ComandoControladorTemperatura, command_id)
    if command is None:
        return jsonify({"error": "comando no encontrado"}), 404
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or payload.get("status") not in (
            "completed", "failed"):
        return jsonify({"error": "status debe ser completed o failed"}), 400

    command.estado = payload["status"]
    command.mensaje = str(payload.get("message", ""))[:2000]
    command.confirmado_en = utc_now()
    if command.estado == "completed":
        command.controlador.setpoint_actual_c = command.valor
    db.session.commit()
    return jsonify({"status": command.estado})
