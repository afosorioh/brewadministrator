from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, abort
from flask_login import login_required, current_user
from sqlalchemy import desc
from app.extensions import db
from app.models import Bache, SesionCata
import secrets
import qrcode
import io
import base64

bp = Blueprint("catas", __name__, url_prefix="/catas")


def generar_codigo_publico():
    return "CATA-" + secrets.token_hex(4).upper()


def generar_codigo_unico():
    while True:
        codigo = generar_codigo_publico()
        existe = SesionCata.query.filter_by(codigo_publico=codigo).first()
        if not existe:
            return codigo


def construir_link_publico(codigo_publico):
    public_base = current_app.config.get("PUBLIC_BASE_URL")
    if public_base:
        base = public_base.rstrip("/")
    else:
        base = request.host_url.rstrip("/")

    return f"{base}/c/{codigo_publico}"


def generar_qr_base64(texto):
    qr = qrcode.QRCode(
        version=2,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4
    )
    qr.add_data(texto)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    img_b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
    return img_b64


@bp.route("/")
@login_required
def lista():
    sesiones = (
        SesionCata.query
        .join(Bache)
        .order_by(desc(SesionCata.fecha_creacion))
        .all()
    )
    return render_template("catas/lista.html", sesiones=sesiones)


@bp.route("/nueva", methods=["GET", "POST"])
@login_required
def nueva():
    baches = (
        Bache.query
        .order_by(desc(Bache.fecha_coccion), Bache.codigo_bache.asc())
        .all()
    )

    if request.method == "POST":
        id_bache = request.form.get("id_bache", type=int)
        titulo = (request.form.get("titulo") or "").strip()
        descripcion = (request.form.get("descripcion") or "").strip()
        observaciones = (request.form.get("observaciones") or "").strip()
        activa = True if request.form.get("activa") == "on" else False

        if not id_bache:
            flash("Debes seleccionar un bache.", "warning")
            return render_template("catas/form.html", baches=baches)

        bache = Bache.query.get(id_bache)
        if not bache:
            flash("El bache seleccionado no existe.", "danger")
            return render_template("catas/form.html", baches=baches)

        codigo_publico = generar_codigo_unico()

        sesion = SesionCata(
            id_bache=id_bache,
            codigo_publico=codigo_publico,
            titulo=titulo or f"Cata {bache.codigo_bache}",
            descripcion=descripcion or None,
            activa=activa,
            creada_por=getattr(current_user, "id", None),
            observaciones=observaciones or None
        )

        db.session.add(sesion)
        db.session.commit()

        flash("Sesión de cata creada correctamente.", "success")
        return redirect(url_for("catas.detalle", id_sesion_cata=sesion.id_sesion_cata))

    return render_template("catas/form.html", baches=baches)


@bp.route("/<int:id_sesion_cata>")
@login_required
def detalle(id_sesion_cata):
    sesion = SesionCata.query.get_or_404(id_sesion_cata)

    link_publico = construir_link_publico(sesion.codigo_publico)
    qr_base64 = generar_qr_base64(link_publico)

    return render_template(
        "catas/detalle.html",
        sesion=sesion,
        link_publico=link_publico,
        qr_base64=qr_base64
    )


@bp.route("/<int:id_sesion_cata>/toggle", methods=["POST"])
@login_required
def toggle_activa(id_sesion_cata):
    sesion = SesionCata.query.get_or_404(id_sesion_cata)
    sesion.activa = not sesion.activa
    db.session.commit()

    flash(
        "Sesión activada correctamente." if sesion.activa else "Sesión desactivada correctamente.",
        "success"
    )
    return redirect(url_for("catas.detalle", id_sesion_cata=sesion.id_sesion_cata))


@bp.route("/c/<codigo_publico>")
def acceso_publico_redirect(codigo_publico):
    sesion = SesionCata.query.filter_by(codigo_publico=codigo_publico).first_or_404()
    if not sesion.activa:
        abort(404)

    return redirect(url_for("catas.publica", codigo_publico=codigo_publico))


@bp.route("/publica/<codigo_publico>")
def publica(codigo_publico):
    sesion = SesionCata.query.filter_by(codigo_publico=codigo_publico).first_or_404()
    if not sesion.activa:
        abort(404)

    return render_template("catas/publica_placeholder.html", sesion=sesion)