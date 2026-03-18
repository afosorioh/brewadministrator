from flask import Blueprint, render_template, request, redirect, url_for, abort, flash
from app.extensions import db
from app.models import SesionCata, RespuestaCata, RespuestaCataSabor, RespuestaCataAroma


bp_publica = Blueprint("catas_publicas", __name__)

def clasificar_color(valor):
    if valor <= 10:
        return "casi_blanco"
    elif valor <= 30:
        return "amarillo"
    elif valor <= 50:
        return "rojo"
    elif valor <= 75:
        return "brown"
    return "negro"


def valor_seguro_lista(form, key):
    # para checkboxes múltiples
    return [v.strip() for v in form.getlist(key) if v and v.strip()]

@bp_publica.route("/c/<codigo_publico>", methods=["GET"])
def formulario_publico(codigo_publico):
    sesion = SesionCata.query.filter_by(codigo_publico=codigo_publico).first_or_404()

    if not sesion.activa:
        abort(404)

    return render_template("catas/publica_form.html", sesion=sesion)


@bp_publica.route("/c/<codigo_publico>/enviar", methods=["POST"])
def enviar_respuesta(codigo_publico):
    sesion = SesionCata.query.filter_by(codigo_publico=codigo_publico).first_or_404()

    if not sesion.activa:
        abort(404)

    correo = (request.form.get("correo") or "").strip()
    sexo = (request.form.get("sexo") or "").strip()
    rango_edad = (request.form.get("rango_edad") or "").strip()
    nacionalidad = (request.form.get("nacionalidad") or "").strip()

    puntaje_color = request.form.get("puntaje_color", type=int)
    puntaje_carbonatacion_espuma = request.form.get("puntaje_carbonatacion_espuma", type=int)
    puntaje_sabor = request.form.get("puntaje_sabor", type=int)
    puntaje_aroma = request.form.get("puntaje_aroma", type=int)
    puntaje_impresion_general = request.form.get("puntaje_impresion_general", type=int)

    color_valor = request.form.get("color_valor", type=int)

    carbonatacion_nivel = (request.form.get("carbonatacion_nivel") or "").strip()
    espuma_nivel = (request.form.get("espuma_nivel") or "").strip()
    cuerpo_nivel = (request.form.get("cuerpo_nivel") or "").strip()

    impresion_general_texto = (request.form.get("impresion_general_texto") or "").strip()

    sabores = valor_seguro_lista(request.form, "sabores")
    aromas = valor_seguro_lista(request.form, "aromas")

    errores = []

    # requeridos base
    if not correo:
        errores.append("El correo es obligatorio.")
    if sexo not in ["masculino", "femenino", "otro", "prefiero_no_indicar"]:
        errores.append("Debes seleccionar el sexo.")
    if rango_edad not in ["18_25", "26_35", "36_45", "46_55", "56_65", "66_mas"]:
        errores.append("Debes seleccionar el rango de edad.")
    if nacionalidad not in ["colombiana", "extranjera"]:
        errores.append("Debes seleccionar la nacionalidad.")

    # puntajes 1-5
    for nombre, valor in [
        ("Color", puntaje_color),
        ("Carbonatación y espuma", puntaje_carbonatacion_espuma),
        ("Sabor", puntaje_sabor),
        ("Aroma", puntaje_aroma),
        ("Impresión general", puntaje_impresion_general),
    ]:
        if valor is None or valor < 1 or valor > 5:
            errores.append(f"El puntaje de {nombre} debe estar entre 1 y 5.")

    if color_valor is None or color_valor < 0 or color_valor > 100:
        errores.append("El valor de color debe estar entre 0 y 100.")

    if carbonatacion_nivel not in ["baja", "media", "alta"]:
        errores.append("Debes seleccionar el nivel de carbonatación.")

    if espuma_nivel not in ["baja", "media", "alta"]:
        errores.append("Debes seleccionar el nivel de espuma.")

    if cuerpo_nivel not in ["bajo", "medio", "alto"]:
        errores.append("Debes seleccionar el cuerpo.")

    if errores:
        for e in errores:
            flash(e, "danger")
        return render_template("catas/publica_form.html", sesion=sesion), 400

    respuesta = RespuestaCata(
        id_sesion_cata=sesion.id_sesion_cata,
        correo=correo,
        sexo=sexo,
        rango_edad=rango_edad,
        nacionalidad=nacionalidad,

        puntaje_color=puntaje_color,
        puntaje_carbonatacion_espuma=puntaje_carbonatacion_espuma,
        puntaje_sabor=puntaje_sabor,
        puntaje_aroma=puntaje_aroma,
        puntaje_impresion_general=puntaje_impresion_general,

        color_valor=color_valor,
        color_categoria=clasificar_color(color_valor),

        carbonatacion_nivel=carbonatacion_nivel,
        espuma_nivel=espuma_nivel,
        cuerpo_nivel=cuerpo_nivel,

        impresion_general_texto=impresion_general_texto or None,

        ip_origen=request.headers.get("X-Forwarded-For", request.remote_addr),
        user_agent=request.user_agent.string if request.user_agent else None
    )

    db.session.add(respuesta)
    db.session.flush()

    for sabor in sabores:
        db.session.add(
            RespuestaCataSabor(
                id_respuesta_cata=respuesta.id_respuesta_cata,
                sabor=sabor
            )
        )

    for aroma in aromas:
        db.session.add(
            RespuestaCataAroma(
                id_respuesta_cata=respuesta.id_respuesta_cata,
                aroma=aroma
            )
        )

    db.session.commit()

    return redirect(url_for("catas_publicas.gracias", codigo_publico=sesion.codigo_publico))

@bp_publica.route("/c/<codigo_publico>/gracias", methods=["GET"])
def gracias(codigo_publico):
    sesion = SesionCata.query.filter_by(codigo_publico=codigo_publico).first_or_404()
    return render_template("catas/publica_gracias.html", sesion=sesion)

