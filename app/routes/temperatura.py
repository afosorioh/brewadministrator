import re
import uuid
from datetime import datetime
from decimal import Decimal, InvalidOperation

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy.exc import IntegrityError

from app.authz import role_required
from app.extensions import db
from app.models import (
    ComandoControladorTemperatura,
    ControladorTemperatura,
    LecturaTemperatura,
)


temperatura_bp = Blueprint("temperatura", __name__, url_prefix="/temperatura")
CODE_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{1,78}[a-z0-9]$")


def _decimal_form(name):
    value = (request.form.get(name) or "").strip()
    try:
        parsed = Decimal(value)
    except (InvalidOperation, ValueError):
        raise ValueError("%s debe ser un numero" % name)
    if not parsed.is_finite() or parsed != parsed.quantize(Decimal("0.1")):
        raise ValueError("%s debe tener como maximo un decimal" % name)
    return parsed


def _populate_from_form(controller):
    codigo = (request.form.get("codigo") or "").strip().lower()
    nombre = (request.form.get("nombre") or "").strip()
    gateway_id = (request.form.get("gateway_id") or "").strip()
    if not CODE_PATTERN.match(codigo):
        raise ValueError(
            "El codigo debe usar minusculas, numeros y guiones (3 a 80 caracteres)."
        )
    if not nombre or not gateway_id:
        raise ValueError("Nombre y gateway son obligatorios.")
    try:
        device_id = int(request.form.get("device_id", ""))
    except ValueError:
        raise ValueError("El ID RS-485 debe ser numerico.")
    if not 1 <= device_id <= 247:
        raise ValueError("El ID RS-485 debe estar entre 1 y 247.")
    minimum = _decimal_form("setpoint_min_c")
    maximum = _decimal_form("setpoint_max_c")
    if minimum < Decimal("-50.0") or maximum > Decimal("200.0"):
        raise ValueError("Los limites deben estar entre -50.0 y 200.0 C.")
    if minimum >= maximum:
        raise ValueError("El limite minimo debe ser menor que el maximo.")

    controller.codigo = codigo
    controller.nombre = nombre
    controller.gateway_id = gateway_id
    controller.device_id = device_id
    controller.setpoint_min_c = minimum
    controller.setpoint_max_c = maximum
    controller.activo = request.form.get("activo") == "on"


@temperatura_bp.get("/")
@login_required
def lista():
    controllers = ControladorTemperatura.query.order_by(
        ControladorTemperatura.nombre.asc()
    ).all()
    now = datetime.utcnow()
    ages = {}
    latest_commands = {}
    for item in controllers:
        ages[item.id] = (
            None if item.ultima_lectura_en is None
            else max(0, int((now - item.ultima_lectura_en).total_seconds()))
        )
        latest_commands[item.id] = (
            ComandoControladorTemperatura.query
            .filter_by(id_controlador=item.id)
            .order_by(ComandoControladorTemperatura.creado_en.desc())
            .first()
        )
    return render_template(
        "temperatura/lista.html", controllers=controllers, ages=ages,
        latest_commands=latest_commands
    )


@temperatura_bp.route("/nuevo", methods=["GET", "POST"])
@login_required
@role_required("ADMIN", "GESTOR")
def crear():
    controller = ControladorTemperatura(
        gateway_id="brewery-main-rpi", setpoint_min_c=-10.0,
        setpoint_max_c=30.0, activo=True
    )
    if request.method == "POST":
        try:
            _populate_from_form(controller)
            db.session.add(controller)
            db.session.commit()
        except ValueError as error:
            flash(str(error), "danger")
        except IntegrityError:
            db.session.rollback()
            flash("El codigo o el ID RS-485 ya esta registrado en ese gateway.", "danger")
        else:
            flash("Controlador creado. La Raspberry lo detectara en el siguiente ciclo.", "success")
            return redirect(url_for("temperatura.lista"))
    return render_template(
        "temperatura/formulario.html", controller=controller, accion="crear"
    )


@temperatura_bp.route("/<int:controller_id>/editar", methods=["GET", "POST"])
@login_required
@role_required("ADMIN", "GESTOR")
def editar(controller_id):
    controller = ControladorTemperatura.query.get_or_404(controller_id)
    if request.method == "POST":
        try:
            _populate_from_form(controller)
            db.session.commit()
        except ValueError as error:
            flash(str(error), "danger")
        except IntegrityError:
            db.session.rollback()
            flash("El codigo o el ID RS-485 ya esta registrado en ese gateway.", "danger")
        else:
            flash("Controlador actualizado.", "success")
            return redirect(url_for("temperatura.lista"))
    return render_template(
        "temperatura/formulario.html", controller=controller, accion="editar"
    )


@temperatura_bp.get("/<int:controller_id>")
@login_required
def detalle(controller_id):
    controller = ControladorTemperatura.query.get_or_404(controller_id)
    readings = (
        LecturaTemperatura.query.filter_by(id_controlador=controller.id)
        .order_by(LecturaTemperatura.observado_en.desc()).limit(200).all()
    )
    commands = (
        ComandoControladorTemperatura.query.filter_by(id_controlador=controller.id)
        .order_by(ComandoControladorTemperatura.creado_en.desc()).limit(20).all()
    )
    return render_template(
        "temperatura/detalle.html", controller=controller,
        readings=readings, commands=commands
    )


@temperatura_bp.post("/<int:controller_id>/setpoint")
@login_required
@role_required("ADMIN", "GESTOR")
def cambiar_setpoint(controller_id):
    controller = ControladorTemperatura.query.get_or_404(controller_id)
    if not controller.activo:
        flash("El controlador esta inactivo.", "danger")
        return redirect(url_for("temperatura.lista"))
    if controller.setpoint_actual_c is None or controller.ultima_lectura_en is None:
        flash("Debe existir una lectura reciente antes de enviar comandos.", "danger")
        return redirect(url_for("temperatura.lista"))
    age = (datetime.utcnow() - controller.ultima_lectura_en).total_seconds()
    if age > 180:
        flash("La ultima lectura tiene mas de 3 minutos; no se envio el comando.", "danger")
        return redirect(url_for("temperatura.lista"))
    try:
        target = _decimal_form("setpoint_c")
    except ValueError as error:
        flash(str(error), "danger")
        return redirect(url_for("temperatura.lista"))
    if not controller.setpoint_min_c <= target <= controller.setpoint_max_c:
        flash("El setpoint esta fuera de los limites configurados.", "danger")
        return redirect(url_for("temperatura.lista"))
    maximum_delta = Decimal(str(current_app.config.get(
        "TEMPERATURE_COMMAND_MAX_DELTA_C", 5.0
    )))
    if abs(target - controller.setpoint_actual_c) > maximum_delta:
        flash(
            "Por seguridad, cada comando puede cambiar maximo %.1f C." %
            float(maximum_delta), "danger"
        )
        return redirect(url_for("temperatura.lista"))
    pending = ComandoControladorTemperatura.query.filter(
        ComandoControladorTemperatura.id_controlador == controller.id,
        ComandoControladorTemperatura.estado.in_(("pending", "delivered")),
    ).first()
    if pending is not None:
        flash("Ya existe un cambio de setpoint pendiente para este controlador.", "warning")
        return redirect(url_for("temperatura.lista"))

    command = ComandoControladorTemperatura(
        command_id=str(uuid.uuid4()),
        id_controlador=controller.id,
        gateway_id=controller.gateway_id,
        accion="set_setpoint",
        valor=target,
        setpoint_esperado_c=controller.setpoint_actual_c,
        estado="pending",
        creado_por=current_user.id,
    )
    db.session.add(command)
    db.session.commit()
    flash("Cambio de setpoint encolado. Se aplicara en el siguiente ciclo.", "success")
    return redirect(url_for("temperatura.lista"))


@temperatura_bp.post("/<int:controller_id>/eliminar")
@login_required
@role_required("ADMIN")
def eliminar(controller_id):
    controller = ControladorTemperatura.query.get_or_404(controller_id)
    db.session.delete(controller)
    db.session.commit()
    flash("Controlador y su historial fueron eliminados.", "success")
    return redirect(url_for("temperatura.lista"))
