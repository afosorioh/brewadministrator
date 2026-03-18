from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, abort
from flask_login import login_required, current_user
from sqlalchemy import desc, func
from app.extensions import db
from app.models import Bache, SesionCata
import secrets
import qrcode
import io
import base64

from collections import Counter
from app.models import (
    RespuestaCata,
    RespuestaCataSabor,
    RespuestaCataAroma
)

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

@bp.route("/<int:id_sesion_cata>/estadisticas")
@login_required
def estadisticas(id_sesion_cata):
    sesion = SesionCata.query.get_or_404(id_sesion_cata)

    respuestas = RespuestaCata.query.filter_by(id_sesion_cata=id_sesion_cata).all()
    total_respuestas = len(respuestas)

    if total_respuestas == 0:
        return render_template(
            "catas/estadisticas.html",
            sesion=sesion,
            total_respuestas=0,
            promedios={},
            porcentajes_sexo=[],
            porcentajes_edad=[],
            porcentajes_nacionalidad=[],
            distribucion_color=[],
            distribucion_carbonatacion=[],
            distribucion_espuma=[],
            distribucion_cuerpo=[],
            top_sabores=[],
            top_aromas=[],
            alertas=[]
        )

    def porcentaje_counter(valores):
        total = len(valores)
        counter = Counter(valores)
        resultado = []
        for clave, cantidad in counter.items():
            resultado.append({
                "label": clave,
                "cantidad": cantidad,
                "porcentaje": round((cantidad * 100.0) / total, 1)
            })
        return sorted(resultado, key=lambda x: (-x["cantidad"], x["label"]))

    def promedio(attr):
        vals = [getattr(r, attr) for r in respuestas if getattr(r, attr) is not None]
        if not vals:
            return None
        return round(sum(vals) / len(vals), 2)

    porcentajes_sexo = porcentaje_counter([r.sexo for r in respuestas if r.sexo])
    porcentajes_edad = porcentaje_counter([r.rango_edad for r in respuestas if r.rango_edad])
    porcentajes_nacionalidad = porcentaje_counter([r.nacionalidad for r in respuestas if r.nacionalidad])

    distribucion_color = porcentaje_counter([r.color_categoria for r in respuestas if r.color_categoria])
    distribucion_carbonatacion = porcentaje_counter([r.carbonatacion_nivel for r in respuestas if r.carbonatacion_nivel])
    distribucion_espuma = porcentaje_counter([r.espuma_nivel for r in respuestas if r.espuma_nivel])
    distribucion_cuerpo = porcentaje_counter([r.cuerpo_nivel for r in respuestas if r.cuerpo_nivel])
    distribucion_amargor = porcentaje_counter([r.amargor_nivel for r in respuestas if r.amargor_nivel])

    promedios = {
        "color": promedio("puntaje_color"),
        "carbonatacion_espuma": promedio("puntaje_carbonatacion_espuma"),
        "sabor": promedio("puntaje_sabor"),
        "aroma": promedio("puntaje_aroma"),
        "impresion_general": promedio("puntaje_impresion_general"),
    }

    promedios_validos = [v for v in promedios.values() if v is not None]
    promedio_global = round(sum(promedios_validos) / len(promedios_validos), 2) if promedios_validos else None

    sabores_rows = (
        db.session.query(RespuestaCataSabor.sabor, func.count(RespuestaCataSabor.id_respuesta_cata_sabor))
        .join(RespuestaCata, RespuestaCata.id_respuesta_cata == RespuestaCataSabor.id_respuesta_cata)
        .filter(RespuestaCata.id_sesion_cata == id_sesion_cata)
        .group_by(RespuestaCataSabor.sabor)
        .order_by(func.count(RespuestaCataSabor.id_respuesta_cata_sabor).desc())
        .all()
    )

    aromas_rows = (
        db.session.query(RespuestaCataAroma.aroma, func.count(RespuestaCataAroma.id_respuesta_cata_aroma))
        .join(RespuestaCata, RespuestaCata.id_respuesta_cata == RespuestaCataAroma.id_respuesta_cata)
        .filter(RespuestaCata.id_sesion_cata == id_sesion_cata)
        .group_by(RespuestaCataAroma.aroma)
        .order_by(func.count(RespuestaCataAroma.id_respuesta_cata_aroma).desc())
        .all()
    )

    top_sabores = [
        {
            "label": s,
            "cantidad": c,
            "porcentaje": round((c * 100.0) / total_respuestas, 1)
        }
        for s, c in sabores_rows
    ]

    top_aromas = [
        {
            "label": a,
            "cantidad": c,
            "porcentaje": round((c * 100.0) / total_respuestas, 1)
        }
        for a, c in aromas_rows
    ]

    alertas = []

    if promedios.get("sabor") is not None and promedios["sabor"] < 3:
        alertas.append("El puntaje promedio de sabor es bajo. Conviene revisar balance de receta, fermentación y maduración.")

    if promedios.get("aroma") is not None and promedios["aroma"] < 3:
        alertas.append("El aroma está siendo evaluado por debajo de 3. Puede valer la pena revisar frescura, lúpulo y perfil fermentativo.")

    if promedios.get("carbonatacion_espuma") is not None and promedios["carbonatacion_espuma"] < 3:
        alertas.append("La carbonatación/espuma tiene una percepción débil. Revisa gasificación, nivel de CO2 y retención de espuma.")

    sabores_labels = {x["label"] for x in top_sabores}
    aromas_labels = {x["label"] for x in top_aromas}

    if "medicinal" in aromas_labels:
        alertas.append("Se detectó descriptor medicinal. Revisa sanitización, fermentación y posibles desviaciones sensoriales.")
    if "mantequilla" in aromas_labels:
        alertas.append("Se detectó mantequilla. Puede ser señal de diacetilo y conviene revisar fermentación y acondicionamiento.")
    if "cebolla" in aromas_labels:
        alertas.append("Se detectó cebolla. Revisa calidad/manejo del lúpulo y estabilidad del producto.")
    if "acido" in sabores_labels:
        alertas.append("Hay percepción ácida en sabor. Verifica si corresponde al estilo o si puede indicar desviación del lote.")

    return render_template(
        "catas/estadisticas.html",
        sesion=sesion,
        total_respuestas=total_respuestas,
        promedio_global=promedio_global,
        promedios=promedios,
        porcentajes_sexo=porcentajes_sexo,
        porcentajes_edad=porcentajes_edad,
        porcentajes_nacionalidad=porcentajes_nacionalidad,
        distribucion_color=distribucion_color,
        distribucion_carbonatacion=distribucion_carbonatacion,
        distribucion_espuma=distribucion_espuma,
        distribucion_cuerpo=distribucion_cuerpo,
        top_sabores=top_sabores,
        top_aromas=top_aromas,
        alertas=alertas
    )