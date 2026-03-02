from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
)

from app.extensions import db

from app.models import (
    MateriaPrima,
    LevaduraDetalle,
    LupuloDetalle,
    MaltaDetalle,
    OtrosMtpDetalle,
    LoteMateriaPrima,
)

from flask_login import login_required
from app.authz import role_required

materias_primas_bp = Blueprint(
    "materias_primas",
    __name__,
    url_prefix="/materias_primas",
)


@materias_primas_bp.route("/")
@login_required
def lista():
    materias = MateriaPrima.query.order_by(MateriaPrima.nombre).all()
    return render_template("materias_primas/lista.html", materias=materias)

@materias_primas_bp.route("/nueva", methods=["GET", "POST"])
@login_required
@role_required("ADMIN", "GESTOR")
def crear():
    tipos = ["MALTA", "LUPULO", "LEVADURA", "OTRO"]
    unidades = ["KG", "G", "L", "ML", "UNIDAD"]

    if request.method == "POST":
        nombre = request.form.get("nombre")
        tipo = request.form.get("tipo")
        unidad_base = request.form.get("unidad_base")
        fabricante = request.form.get("fabricante") or None
        origen = request.form.get("origen") or None
        notas = request.form.get("notas") or None

        if not nombre or not tipo or not unidad_base:
            flash("Nombre, tipo y unidad son obligatorios", "danger")
            return redirect(url_for("materias_primas.crear"))

        mp = MateriaPrima(
            nombre=nombre,
            tipo=tipo,
            unidad_base=unidad_base,
            fabricante=fabricante,
            origen=origen,
            notas=notas,
            activo=True,
        )
        db.session.add(mp)
        db.session.flush()  # asegura que mp.id exista sin hacer commit aún

        # ----- Detalles específicos según tipo -----
        if tipo == "LEVADURA":
            floculacion = request.form.get("lev_floculacion")
            tipo_levadura = request.form.get("lev_tipo_levadura") or "OTRA"
            forma_lev = request.form.get("lev_forma") or "SECA"

            at_min = request.form.get("lev_atenuacion_min") or None
            at_max = request.form.get("lev_atenuacion_max") or None
            pitch = request.form.get("lev_pitch_rate") or None
            tmin = request.form.get("lev_temp_min") or None
            tmax = request.form.get("lev_temp_max") or None

            if floculacion:
                lev = LevaduraDetalle(
                    id_materia_prima=mp.id,
                    floculacion=floculacion,
                    tipo_levadura=tipo_levadura,
                    forma=forma_lev,
                    atenuacion_min=int(at_min) if at_min else None,
                    atenuacion_max=int(at_max) if at_max else None,
                    pitch_rate_mill_cel_ml_plato=float(pitch) if pitch else None,
                    temperatura_min_c=int(tmin) if tmin else None,
                    temperatura_max_c=int(tmax) if tmax else None,
                )
                db.session.add(lev)

        elif tipo == "LUPULO":
            uso = request.form.get("lup_uso") or "DUAL"
            forma_lup = request.form.get("lup_forma") or "PELLET"
            alfa = request.form.get("lup_alfa") or None
            beta = request.form.get("lup_beta") or None
            cohu = request.form.get("lup_cohumulona") or None
            aceites = request.form.get("lup_aceites") or None
            perfil = request.form.get("lup_perfil") or None
            anio = request.form.get("lup_anio") or None

            lup = LupuloDetalle(
                id_materia_prima=mp.id,
                uso=uso,
                forma=forma_lup,
                alfa_acidos_pct=float(alfa) if alfa else None,
                beta_acidos_pct=float(beta) if beta else None,
                cohumulona_pct=float(cohu) if cohu else None,
                aceites_totales_ml_100g=float(aceites) if aceites else None,
                perfil_aroma=perfil,
                año_cosecha=int(anio) if anio else None,
            )
            db.session.add(lup)

        elif tipo == "MALTA":
            tipo_malta = request.form.get("mal_tipo_malta") or "BASE"
            color_ebc = request.form.get("mal_color_ebc") or None
            color_lovi = request.form.get("mal_color_lovibond") or None
            potencial = request.form.get("mal_potencial") or None
            prote = request.form.get("mal_proteinas") or None
            ph = request.form.get("mal_ph_mosto") or None
            uso_max = request.form.get("mal_uso_max") or None

            mal = MaltaDetalle(
                id_materia_prima=mp.id,
                tipo_malta=tipo_malta,
                color_ebc=float(color_ebc) if color_ebc else None,
                color_lovibond=float(color_lovi) if color_lovi else None,
                potencial_gravedad=float(potencial) if potencial else None,
                proteinas_pct=float(prote) if prote else None,
                ph_mosto_color=float(ph) if ph else None,
                uso_max_pct_molienda=float(uso_max) if uso_max else None,
            )
            db.session.add(mal)

        elif tipo == "OTRO":
            otro_tipo = request.form.get("otro_tipo") or None
            otro_nombre = request.form.get("otro_nombre") or None

            if otro_tipo and otro_nombre:
                otro = OtrosMtpDetalle(
                    id_materia_prima=mp.id,
                    tipo=otro_tipo,
                    nombre=otro_nombre,
                )
                db.session.add(otro)

        db.session.commit()
        flash("Materia prima creada correctamente", "success")
        return redirect(url_for("materias_primas.detalle", mp_id=mp.id))

    # GET
    return render_template(
        "materias_primas/formulario.html",
        accion="crear",
        tipos=tipos,
        unidades=unidades,
        mp=None,
    )

@materias_primas_bp.route("/<int:mp_id>")
def detalle(mp_id):
    mp = MateriaPrima.query.get_or_404(mp_id)
    lotes = (
        LoteMateriaPrima.query
        .filter_by(id_materia_prima=mp.id)
        .order_by(LoteMateriaPrima.fecha_compra.desc())
        .all()
    )
    return render_template("materias_primas/detalle.html", mp=mp, lotes=lotes)

@materias_primas_bp.route("/<int:mp_id>/editar", methods=["GET", "POST"])
@login_required
@role_required("ADMIN", "GESTOR")
def editar(mp_id):
    mp = MateriaPrima.query.get_or_404(mp_id)
    tipos = ["MALTA", "LUPULO", "LEVADURA", "OTRO"]
    unidades = ["KG", "G", "L", "ML", "UNIDAD"]

    if request.method == "POST":
        mp.nombre = request.form.get("nombre")
        nuevo_tipo = request.form.get("tipo")
        mp.unidad_base = request.form.get("unidad_base")
        mp.fabricante = request.form.get("fabricante") or None
        mp.origen = request.form.get("origen") or None
        mp.notas = request.form.get("notas") or None

        if not mp.nombre or not nuevo_tipo or not mp.unidad_base:
            flash("Nombre, tipo y unidad son obligatorios", "danger")
            return redirect(url_for("materias_primas.editar", mp_id=mp.id))

        # Si cambia de tipo, eliminar detalles anteriores que ya no apliquen
        if mp.tipo != nuevo_tipo:
            if mp.tipo == "LEVADURA" and mp.levadura_detalle:
                db.session.delete(mp.levadura_detalle)
            if mp.tipo == "LUPULO" and mp.lupulo_detalle:
                db.session.delete(mp.lupulo_detalle)
            if mp.tipo == "MALTA" and mp.malta_detalle:
                db.session.delete(mp.malta_detalle)
            if mp.tipo == "OTRO" and mp.otros_detalle:
                db.session.delete(mp.otros_detalle)
        mp.tipo = nuevo_tipo

        # ----- Detalles específicos según tipo -----
        if mp.tipo == "LEVADURA":
            floculacion = request.form.get("lev_floculacion")
            tipo_levadura = request.form.get("lev_tipo_levadura") or "OTRA"
            forma_lev = request.form.get("lev_forma") or "SECA"
            at_min = request.form.get("lev_atenuacion_min") or None
            at_max = request.form.get("lev_atenuacion_max") or None
            pitch = request.form.get("lev_pitch_rate") or None
            tmin = request.form.get("lev_temp_min") or None
            tmax = request.form.get("lev_temp_max") or None

            if mp.levadura_detalle is None:
                mp.levadura_detalle = LevaduraDetalle(
                    id_materia_prima=mp.id,
                )

            lev = mp.levadura_detalle
            lev.floculacion = floculacion or lev.floculacion
            lev.tipo_levadura = tipo_levadura
            lev.forma = forma_lev
            lev.atenuacion_min = int(at_min) if at_min else None
            lev.atenuacion_max = int(at_max) if at_max else None
            lev.pitch_rate_mill_cel_ml_plato = float(pitch) if pitch else None
            lev.temperatura_min_c = int(tmin) if tmin else None
            lev.temperatura_max_c = int(tmax) if tmax else None

        elif mp.tipo == "LUPULO":
            uso = request.form.get("lup_uso") or "DUAL"
            forma_lup = request.form.get("lup_forma") or "PELLET"
            alfa = request.form.get("lup_alfa") or None
            beta = request.form.get("lup_beta") or None
            cohu = request.form.get("lup_cohumulona") or None
            aceites = request.form.get("lup_aceites") or None
            perfil = request.form.get("lup_perfil") or None
            anio = request.form.get("lup_anio") or None

            if mp.lupulo_detalle is None:
                mp.lupulo_detalle = LupuloDetalle(
                    id_materia_prima=mp.id,
                )

            lup = mp.lupulo_detalle
            lup.uso = uso
            lup.forma = forma_lup
            lup.alfa_acidos_pct = float(alfa) if alfa else None
            lup.beta_acidos_pct = float(beta) if beta else None
            lup.cohumulona_pct = float(cohu) if cohu else None
            lup.aceites_totales_ml_100g = float(aceites) if aceites else None
            lup.perfil_aroma = perfil
            lup.año_cosecha = int(anio) if anio else None

        elif mp.tipo == "MALTA":
            tipo_malta = request.form.get("mal_tipo_malta") or "BASE"
            color_ebc = request.form.get("mal_color_ebc") or None
            color_lovi = request.form.get("mal_color_lovibond") or None
            potencial = request.form.get("mal_potencial") or None
            prote = request.form.get("mal_proteinas") or None
            ph = request.form.get("mal_ph_mosto") or None
            uso_max = request.form.get("mal_uso_max") or None

            if mp.malta_detalle is None:
                mp.malta_detalle = MaltaDetalle(
                    id_materia_prima=mp.id,
                )

            mal = mp.malta_detalle
            mal.tipo_malta = tipo_malta
            mal.color_ebc = float(color_ebc) if color_ebc else None
            mal.color_lovibond = float(color_lovi) if color_lovi else None
            mal.potencial_gravedad = float(potencial) if potencial else None
            mal.proteinas_pct = float(prote) if prote else None
            mal.ph_mosto_color = float(ph) if ph else None
            mal.uso_max_pct_molienda = float(uso_max) if uso_max else None

        elif mp.tipo == "OTRO":
            otro_tipo = request.form.get("otro_tipo") or None
            otro_nombre = request.form.get("otro_nombre") or None

            # Si no se envían datos, eliminamos detalle si existía
            if not otro_tipo or not otro_nombre:
                if mp.otros_detalle:
                    db.session.delete(mp.otros_detalle)
            else:
                if mp.otros_detalle is None:
                    mp.otros_detalle = OtrosMtpDetalle(
                        id_materia_prima=mp.id,
                    )
                mp.otros_detalle.tipo = otro_tipo
                mp.otros_detalle.nombre = otro_nombre

        db.session.commit()
        flash("Materia prima actualizada correctamente", "success")
        return redirect(url_for("materias_primas.detalle", mp_id=mp.id))

    return render_template(
        "materias_primas/formulario.html",
        accion="editar",
        tipos=tipos,
        unidades=unidades,
        mp=mp,
    )

@materias_primas_bp.route("/<int:mp_id>/eliminar", methods=["POST"])
@login_required
@role_required("ADMIN", "GESTOR")
def eliminar(mp_id):
    mp = MateriaPrima.query.get_or_404(mp_id)

    # Si tiene lotes asociados, no permitimos borrar
    if mp.lotes.count() > 0:
        flash(
            "No se puede eliminar la materia prima porque tiene lotes asociados. "
            "Elimina o ajusta primero los lotes.",
            "danger",
        )
        return redirect(url_for("materias_primas.detalle", mp_id=mp.id))

    # Si llega aquí, no tiene lotes, se puede borrar
    # Eliminar detalles específicos si existen
    if mp.levadura_detalle:
        db.session.delete(mp.levadura_detalle)

    if mp.lupulo_detalle:
        db.session.delete(mp.lupulo_detalle)

    if mp.malta_detalle:
        db.session.delete(mp.malta_detalle)

    if mp.otros_detalle:
        db.session.delete(mp.otros_detalle)

    db.session.delete(mp)
    db.session.commit()
    flash("Materia prima eliminada correctamente", "success")
    return redirect(url_for("materias_primas.lista"))

@materias_primas_bp.route("/<int:mp_id>/lotes/nuevo", methods=["GET", "POST"])
def crear_lote(mp_id):
    mp = MateriaPrima.query.get_or_404(mp_id)

    if request.method == "POST":
        codigo_lote = request.form.get("codigo_lote")
        fecha_compra = request.form.get("fecha_compra") or None
        proveedor = request.form.get("proveedor") or None
        cantidad_inicial = request.form.get("cantidad_inicial") or None
        cantidad_disponible = request.form.get("cantidad_disponible") or None
        costo_unitario = request.form.get("costo_unitario") or None
        fecha_vencimiento = request.form.get("fecha_vencimiento") or None
        notas = request.form.get("notas") or None

        if not codigo_lote or not cantidad_inicial:
            flash("Código de lote y cantidad inicial son obligatorios", "danger")
            return redirect(url_for("materias_primas.crear_lote", mp_id=mp.id))

        if not cantidad_disponible:
            cantidad_disponible = cantidad_inicial

        lote = LoteMateriaPrima(
            id_materia_prima=mp.id,
            codigo_lote=codigo_lote,
            fecha_compra=fecha_compra,
            proveedor=proveedor,
            cantidad_inicial=float(cantidad_inicial),
            cantidad_disponible=float(cantidad_disponible),
            costo_unitario=float(costo_unitario) if costo_unitario else None,
            fecha_vencimiento=fecha_vencimiento,
            notas=notas,
        )
        db.session.add(lote)
        db.session.commit()
        flash("Lote creado correctamente", "success")
        return redirect(url_for("materias_primas.detalle", mp_id=mp.id))

    # GET
    return render_template("materias_primas/lote_formulario.html", mp=mp, lote=None, accion="crear")

@materias_primas_bp.route("/<int:mp_id>/lotes/<int:lote_id>/editar", methods=["GET", "POST"])
def editar_lote(mp_id, lote_id):
    mp = MateriaPrima.query.get_or_404(mp_id)
    lote = LoteMateriaPrima.query.get_or_404(lote_id)

    if lote.id_materia_prima != mp.id:
        flash("El lote no pertenece a esta materia prima", "danger")
        return redirect(url_for("materias_primas.detalle", mp_id=mp.id))

    if request.method == "POST":
        lote.codigo_lote = request.form.get("codigo_lote")
        lote.fecha_compra = request.form.get("fecha_compra") or None
        lote.proveedor = request.form.get("proveedor") or None
        cantidad_inicial = request.form.get("cantidad_inicial") or None
        cantidad_disponible = request.form.get("cantidad_disponible") or None
        costo_unitario = request.form.get("costo_unitario") or None
        lote.fecha_vencimiento = request.form.get("fecha_vencimiento") or None
        lote.notas = request.form.get("notas") or None

        if not lote.codigo_lote or not cantidad_inicial:
            flash("Código de lote y cantidad inicial son obligatorios", "danger")
            return redirect(url_for("materias_primas.editar_lote", mp_id=mp.id, lote_id=lote.id))

        lote.cantidad_inicial = float(cantidad_inicial)
        lote.cantidad_disponible = float(cantidad_disponible) if cantidad_disponible else lote.cantidad_inicial
        lote.costo_unitario = float(costo_unitario) if costo_unitario else None

        db.session.commit()
        flash("Lote actualizado correctamente", "success")
        return redirect(url_for("materias_primas.detalle", mp_id=mp.id))

    return render_template("materias_primas/lote_formulario.html", mp=mp, lote=lote, accion="editar")

@materias_primas_bp.route("/<int:mp_id>/lotes/<int:lote_id>/eliminar", methods=["POST"])
def eliminar_lote(mp_id, lote_id):
    mp = MateriaPrima.query.get_or_404(mp_id)
    lote = LoteMateriaPrima.query.get_or_404(lote_id)

    if lote.id_materia_prima != mp.id:
        flash("El lote no pertenece a esta materia prima", "danger")
        return redirect(url_for("materias_primas.detalle", mp_id=mp.id))

    db.session.delete(lote)
    db.session.commit()
    flash("Lote eliminado correctamente", "success")
    return redirect(url_for("materias_primas.detalle", mp_id=mp.id))

