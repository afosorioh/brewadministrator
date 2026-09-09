import re
import uuid
from decimal import Decimal, InvalidOperation

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_babel import gettext as _
from flask_login import current_user, login_required
from sqlalchemy.exc import IntegrityError

from app.authz import role_required
from app.extensions import db
from app.models import (
    Bache,
    ComandoControladorTemperatura,
    ControladorTemperatura,
    LecturaTemperatura,
)
from app.utils.datetime_utils import format_local_datetime, utc_now


temperatura_bp = Blueprint("temperatura", __name__, url_prefix="/temperatura")
CODE_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{1,78}[a-z0-9]$")


def _decimal_form(name):
    value = (request.form.get(name) or "").strip()
    field_label = {
        "setpoint_min_c": _("Setpoint mínimo"),
        "setpoint_max_c": _("Setpoint máximo"),
        "setpoint_c": _("Setpoint"),
    }.get(name, name)
    try:
        parsed = Decimal(value)
    except (InvalidOperation, ValueError):
        raise ValueError(
            _("%(field)s debe ser un número.", field=field_label)
        )
    if not parsed.is_finite() or parsed != parsed.quantize(Decimal("0.1")):
        raise ValueError(
            _("%(field)s debe tener como máximo un decimal.", field=field_label)
        )
    return parsed


def _populate_from_form(controller):
    codigo = (request.form.get("codigo") or "").strip().lower()
    nombre = (request.form.get("nombre") or "").strip()
    gateway_id = (request.form.get("gateway_id") or "").strip()
    if not CODE_PATTERN.match(codigo):
        raise ValueError(
            _("El código debe usar minúsculas, números y guiones (3 a 80 caracteres).")
        )
    if not nombre or not gateway_id:
        raise ValueError(_("Nombre y gateway son obligatorios."))
    try:
        device_id = int(request.form.get("device_id", ""))
    except ValueError:
        raise ValueError(_("El ID RS-485 debe ser numérico."))
    if not 1 <= device_id <= 247:
        raise ValueError(_("El ID RS-485 debe estar entre 1 y 247."))
    protocolo = (request.form.get("protocolo") or "sitrad").strip().lower()
    if protocolo not in ("sitrad", "modbus"):
        raise ValueError(_("El protocolo debe ser Sitrad o Modbus."))
    minimum = _decimal_form("setpoint_min_c")
    maximum = _decimal_form("setpoint_max_c")
    if minimum < Decimal("-50.0") or maximum > Decimal("200.0"):
        raise ValueError(_("Los límites deben estar entre -50.0 y 200.0 °C."))
    if minimum >= maximum:
        raise ValueError(_("El límite mínimo debe ser menor que el máximo."))

    batch_value = (request.form.get("id_bache_actual") or "").strip()
    batch_id = None
    if batch_value:
        try:
            batch_id = int(batch_value)
        except ValueError:
            raise ValueError(_("El bache seleccionado no es válido."))
        if db.session.get(Bache, batch_id) is None:
            raise ValueError(_("El bache seleccionado no existe."))

    controller.codigo = codigo
    controller.nombre = nombre
    controller.gateway_id = gateway_id
    controller.device_id = device_id
    controller.protocolo = protocolo
    controller.setpoint_min_c = minimum
    controller.setpoint_max_c = maximum
    controller.activo = request.form.get("activo") == "on"
    controller.id_bache_actual = batch_id


def _batches_for_form():
    return Bache.query.order_by(
        Bache.fecha_coccion.desc(), Bache.codigo_bache.desc()
    ).all()


@temperatura_bp.get("/")
@login_required
def lista():
    controllers = ControladorTemperatura.query.order_by(
        ControladorTemperatura.nombre.asc()
    ).all()
    now = utc_now()
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
            flash(_("El código o el ID RS-485 ya está registrado en ese gateway."), "danger")
        else:
            flash(_("Controlador creado. La Raspberry lo detectará en el siguiente ciclo."), "success")
            return redirect(url_for("temperatura.lista"))
    return render_template(
        "temperatura/formulario.html", controller=controller, accion="crear",
        batches=_batches_for_form()
    )


@temperatura_bp.route("/<int:controller_id>/editar", methods=["GET", "POST"])
@login_required
@role_required("ADMIN", "GESTOR")
def editar(controller_id):
    controller = ControladorTemperatura.query.get_or_404(controller_id)
    if request.method == "POST":
        try:
            _populate_from_form(controller)
            if (
                controller.id_bache_actual is not None
                and request.form.get("asignar_lecturas_sin_bache") == "on"
            ):
                LecturaTemperatura.query.filter_by(
                    id_controlador=controller.id, id_bache=None
                ).update(
                    {LecturaTemperatura.id_bache: controller.id_bache_actual},
                    synchronize_session=False,
                )
            db.session.commit()
        except ValueError as error:
            flash(str(error), "danger")
        except IntegrityError:
            db.session.rollback()
            flash(_("El código o el ID RS-485 ya está registrado en ese gateway."), "danger")
        else:
            flash(_("Controlador actualizado."), "success")
            return redirect(url_for("temperatura.lista"))
    return render_template(
        "temperatura/formulario.html", controller=controller, accion="editar",
        batches=_batches_for_form()
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
    chart_labels = [
        format_local_datetime(reading.observado_en)
        for reading in reversed(readings)
    ]
    return render_template(
        "temperatura/detalle.html", controller=controller,
        readings=readings, commands=commands, chart_labels=chart_labels
    )


@temperatura_bp.post("/<int:controller_id>/setpoint")
@login_required
@role_required("ADMIN", "GESTOR")
def cambiar_setpoint(controller_id):
    controller = ControladorTemperatura.query.get_or_404(controller_id)
    if not controller.activo:
        flash(_("El controlador está inactivo."), "danger")
        return redirect(url_for("temperatura.lista"))
    if controller.setpoint_actual_c is None or controller.ultima_lectura_en is None:
        flash(_("Debe existir una lectura reciente antes de enviar comandos."), "danger")
        return redirect(url_for("temperatura.lista"))
    age = (utc_now() - controller.ultima_lectura_en).total_seconds()
    if age > 180:
        flash(_("La última lectura tiene más de 3 minutos; no se envió el comando."), "danger")
        return redirect(url_for("temperatura.lista"))
    try:
        target = _decimal_form("setpoint_c")
    except ValueError as error:
        flash(str(error), "danger")
        return redirect(url_for("temperatura.lista"))
    if not controller.setpoint_min_c <= target <= controller.setpoint_max_c:
        flash(_("El setpoint está fuera de los límites configurados."), "danger")
        return redirect(url_for("temperatura.lista"))
    maximum_delta = Decimal(str(current_app.config.get(
        "TEMPERATURE_COMMAND_MAX_DELTA_C", 5.0
    )))
    if abs(target - controller.setpoint_actual_c) > maximum_delta:
        flash(
            _(
                "Por seguridad, cada comando puede cambiar como máximo %(delta)s °C.",
                delta=f"{float(maximum_delta):.1f}",
            ),
            "danger",
        )
        return redirect(url_for("temperatura.lista"))
    pending = ComandoControladorTemperatura.query.filter(
        ComandoControladorTemperatura.id_controlador == controller.id,
        ComandoControladorTemperatura.estado.in_(("pending", "delivered")),
    ).first()
    if pending is not None:
        flash(_("Ya existe un cambio de setpoint pendiente para este controlador."), "warning")
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
    flash(_("Cambio de setpoint encolado. Se aplicará en el siguiente ciclo."), "success")
    return redirect(url_for("temperatura.lista"))


@temperatura_bp.post("/<int:controller_id>/eliminar")
@login_required
@role_required("ADMIN")
def eliminar(controller_id):
    controller = ControladorTemperatura.query.get_or_404(controller_id)
    db.session.delete(controller)
    db.session.commit()
    flash(_("Controlador y su historial fueron eliminados."), "success")
    return redirect(url_for("temperatura.lista"))
