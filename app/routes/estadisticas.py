from io import BytesIO
from datetime import datetime

from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file
from flask_login import login_required

from app.extensions import db
from app.models import LoteMateriaPrima, MateriaPrima, Bache, BacheMateriaPrima, MedicionBache

import matplotlib
matplotlib.use("Agg")  # importante para servidores sin GUI
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

estadisticas_bp = Blueprint("estadisticas", __name__, url_prefix="/estadisticas")


def _to_sg(x):
    """Convierte densidad a SG: 1055 -> 1.055; 1.055 -> 1.055"""
    if x is None:
        return None
    try:
        v = float(x)
    except Exception:
        return None
    return v / 1000.0 if v > 10 else v


def _last_medicion(bache_id, tipo):
    return (
        MedicionBache.query
        .filter_by(id_bache=bache_id, tipo=tipo)
        .order_by(MedicionBache.fecha.desc())
        .first()
    )


def _calculos_bache(bache):
    # OG (del bache)
    og = _to_sg(bache.densidad_inicial)

    # FG (última densidad medida)
    ult_dens = _last_medicion(bache.id, "DENSIDAD")
    fg = _to_sg(ult_dens.valor) if ult_dens else None

    abv = None
    atenuacion = None
    if og is not None and fg is not None and og > 1.0 and fg > 0:
        abv = (og - fg) * 131.25
        if (og - 1.0) != 0:
            atenuacion = ((og - fg) / (og - 1.0)) * 100.0

    ult_temp = _last_medicion(bache.id, "TEMPERATURA")
    ult_ph = _last_medicion(bache.id, "PH")

    return {
        "og": og,
        "fg": fg,
        "abv": abv,
        "atenuacion": atenuacion,
        "ult_dens": ult_dens,
        "ult_temp": ult_temp,
        "ult_ph": ult_ph,
    }


@estadisticas_bp.route("/bache", methods=["GET", "POST"])
@login_required
def bache():
    bache = None
    materias = []
    stats = {}

    codigo = request.form.get("codigo_bache") if request.method == "POST" else request.args.get("codigo_bache")

    if codigo:
        codigo = codigo.strip()

        bache = Bache.query.filter_by(codigo_bache=codigo).first()

        if not bache:
            flash("No se encontró el bache.", "warning")
            return render_template("estadisticas/bache.html", bache=None)

        # Materias primas usadas en el bache
        materias = (
            db.session.query(BacheMateriaPrima, LoteMateriaPrima, MateriaPrima)
            .join(LoteMateriaPrima, BacheMateriaPrima.id_lote == LoteMateriaPrima.id)
            .join(MateriaPrima, LoteMateriaPrima.id_materia_prima == MateriaPrima.id)
            .filter(BacheMateriaPrima.id_bache == bache.id)
            .all()
        )

        # --- Cálculos (igual que en detalle) ---
        def _to_sg(x):
            if x is None:
                return None
            v = float(x)
            return v / 1000.0 if v > 10 else v

        og = _to_sg(bache.densidad_inicial)

        ult_dens = (
            MedicionBache.query
            .filter_by(id_bache=bache.id, tipo="DENSIDAD")
            .order_by(MedicionBache.fecha.desc())
            .first()
        )

        ult_temp = (
            MedicionBache.query
            .filter_by(id_bache=bache.id, tipo="TEMPERATURA")
            .order_by(MedicionBache.fecha.desc())
            .first()
        )

        ult_ph = (
            MedicionBache.query
            .filter_by(id_bache=bache.id, tipo="PH")
            .order_by(MedicionBache.fecha.desc())
            .first()
        )

        fg = _to_sg(ult_dens.valor) if ult_dens else None

        abv = None
        atenuacion = None
        if og and fg and og > 1:
            abv = (og - fg) * 131.25
            atenuacion = ((og - fg) / (og - 1)) * 100 if (og - 1) != 0 else None

        stats = {
            "og": og,
            "fg": fg,
            "abv": abv,
            "atenuacion": atenuacion,
            "ult_dens": ult_dens,
            "ult_temp": ult_temp,
            "ult_ph": ult_ph,
        }

    return render_template(
        "estadisticas/bache.html",
        bache=bache,
        materias=materias,
        stats=stats,
    )


@estadisticas_bp.route("/bache/<int:bache_id>/grafica.png")
@login_required
def bache_grafica(bache_id):
    bache = Bache.query.get_or_404(bache_id)

    meds = (
        MedicionBache.query
        .filter_by(id_bache=bache.id)
        .filter(MedicionBache.tipo.in_(["PH", "TEMPERATURA", "DENSIDAD"]))
        .order_by(MedicionBache.fecha.asc())
        .all()
    )

    from io import BytesIO
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates

    fechas = {"PH": [], "TEMPERATURA": [], "DENSIDAD": []}
    valores = {"PH": [], "TEMPERATURA": [], "DENSIDAD": []}

    def _to_sg(x):
        return x / 1000.0 if x and x > 10 else x

    for m in meds:
        fechas[m.tipo].append(m.fecha)
        if m.tipo == "DENSIDAD":
            valores[m.tipo].append(_to_sg(float(m.valor)))
        else:
            valores[m.tipo].append(float(m.valor))

    fig, ax = plt.subplots(3, 1, figsize=(10, 6), sharex=True)

    ax[0].plot(fechas["PH"], valores["PH"], marker="o")
    ax[0].set_title("pH")

    ax[1].plot(fechas["DENSIDAD"], valores["DENSIDAD"], marker="o")
    ax[1].set_title("Densidad (SG)")

    ax[2].plot(fechas["TEMPERATURA"], valores["TEMPERATURA"], marker="o")
    ax[2].set_title("Temperatura (°C)")

    for a in ax:
        a.grid(True)
        a.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))

    fig.autofmt_xdate()
    fig.tight_layout()

    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=150)
    plt.close(fig)
    buf.seek(0)

    return send_file(buf, mimetype="image/png")