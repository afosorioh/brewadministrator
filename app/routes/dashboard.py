from datetime import timedelta

from flask import Blueprint, render_template
from flask_login import login_required
from sqlalchemy import func

from app.extensions import db
from app.models import (
    Bache,
    Barril,
    ControladorTemperatura,
    LoteMateriaPrima,
    MateriaPrima,
    RespuestaCata,
    SesionCata,
)
from app.utils.datetime_utils import local_today, utc_now


dashboard_bp = Blueprint("dashboard", __name__, url_prefix="/dashboard")

BATCH_STATES = (
    "PLANIFICADO",
    "EN_CURSO",
    "FERMENTANDO",
    "MADURANDO",
    "LISTO",
    "COMPLETADO",
    "DESCARTADO",
)
ACTIVE_BATCH_STATES = (
    "PLANIFICADO",
    "EN_CURSO",
    "FERMENTANDO",
    "MADURANDO",
    "LISTO",
)
KEG_STATES = (
    "LIMPIO",
    "LLENO",
    "ENTREGADO",
    "SUCIO",
    "MANTENIMIENTO",
    "BAJA",
)
RAW_MATERIAL_TYPES = ("MALTA", "LUPULO", "LEVADURA", "OTRO")


def _counts_by(column, states, query):
    """Return every expected state, including those whose count is zero."""
    counts = {state: 0 for state in states}
    for state, total in query.with_entities(column, func.count()).group_by(column):
        counts[state] = total
    return counts


@dashboard_bp.get("/")
@login_required
def inicio():
    today = local_today()
    expiration_limit = today + timedelta(days=30)

    raw_material_counts = _counts_by(
        MateriaPrima.tipo,
        RAW_MATERIAL_TYPES,
        MateriaPrima.query.filter(MateriaPrima.activo.is_(True)),
    )
    raw_materials = {
        "active": MateriaPrima.query.filter(MateriaPrima.activo.is_(True)).count(),
        "available_lots": LoteMateriaPrima.query.filter(
            LoteMateriaPrima.cantidad_disponible > 0
        ).count(),
        "expiring_lots": LoteMateriaPrima.query.filter(
            LoteMateriaPrima.cantidad_disponible > 0,
            LoteMateriaPrima.fecha_vencimiento >= today,
            LoteMateriaPrima.fecha_vencimiento <= expiration_limit,
        ).count(),
        "expired_lots": LoteMateriaPrima.query.filter(
            LoteMateriaPrima.cantidad_disponible > 0,
            LoteMateriaPrima.fecha_vencimiento < today,
        ).count(),
        "by_type": raw_material_counts,
    }

    batch_counts = _counts_by(Bache.estado, BATCH_STATES, Bache.query)
    batches = {
        "total": sum(batch_counts.values()),
        "active": sum(batch_counts[state] for state in ACTIVE_BATCH_STATES),
        "completed": batch_counts["COMPLETADO"],
        "discarded": batch_counts["DESCARTADO"],
        "by_state": batch_counts,
        "recent": (
            Bache.query.filter(Bache.estado.in_(ACTIVE_BATCH_STATES))
            .order_by(Bache.fecha_coccion.desc(), Bache.id.desc())
            .limit(5)
            .all()
        ),
    }

    keg_counts = _counts_by(Barril.estado_actual, KEG_STATES, Barril.query)
    kegs = {
        "operational": sum(
            total for state, total in keg_counts.items() if state != "BAJA"
        ),
        "clean": keg_counts["LIMPIO"],
        "full": keg_counts["LLENO"],
        "delivered": keg_counts["ENTREGADO"],
        "dirty": keg_counts["SUCIO"],
        "by_state": keg_counts,
    }

    response_count = (
        db.session.query(func.count(RespuestaCata.id_respuesta_cata))
        .filter(RespuestaCata.id_sesion_cata == SesionCata.id_sesion_cata)
        .correlate(SesionCata)
        .scalar_subquery()
    )
    recent_tastings = (
        db.session.query(
            SesionCata,
            Bache,
            response_count.label("response_count"),
        )
        .join(Bache, Bache.id == SesionCata.id_bache)
        .order_by(SesionCata.fecha_creacion.desc())
        .limit(4)
        .all()
    )
    tastings = {
        "total": SesionCata.query.count(),
        "active": SesionCata.query.filter(SesionCata.activa.is_(True)).count(),
        "responses": RespuestaCata.query.count(),
        "recent": recent_tastings,
    }

    controllers = (
        ControladorTemperatura.query.filter(
            ControladorTemperatura.activo.is_(True)
        )
        .order_by(ControladorTemperatura.nombre.asc())
        .all()
    )
    now = utc_now()
    controller_rows = []
    online_count = 0
    sensor_error_count = 0
    for controller in controllers:
        age_seconds = None
        if controller.ultima_lectura_en is not None:
            age_seconds = max(
                0, int((now - controller.ultima_lectura_en).total_seconds())
            )
        online = age_seconds is not None and age_seconds <= 180
        if online:
            online_count += 1
        if controller.error_sensor:
            sensor_error_count += 1
        controller_rows.append(
            {
                "controller": controller,
                "online": online,
                "age_seconds": age_seconds,
            }
        )

    temperatures = {
        "active": len(controllers),
        "online": online_count,
        "offline": len(controllers) - online_count,
        "sensor_errors": sensor_error_count,
        "controllers": controller_rows,
    }

    return render_template(
        "dashboard/inicio.html",
        today=today,
        raw_materials=raw_materials,
        batches=batches,
        kegs=kegs,
        tastings=tastings,
        temperatures=temperatures,
    )
