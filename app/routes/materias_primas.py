from flask import (
    Blueprint,
    abort,
    render_template,
    request,
    redirect,
    send_from_directory,
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
from flask_babel import gettext as _
from app.authz import role_required
from app.services.quality_certificates import (
    InvalidQualityCertificate,
    certificate_directory,
    delete_quality_certificate,
    maximum_certificate_size_mb,
    save_quality_certificate,
)

materias_primas_bp = Blueprint(
    "materias_primas",
    __name__,
    url_prefix="/materias_primas",
)

TIPOS_MATERIA_PRIMA = ("MALTA", "LUPULO", "LEVADURA", "OTRO")


def _tipo_filtro_solicitado():
    tipo = (request.args.get("tipo") or "").strip().upper()
    return tipo if tipo in TIPOS_MATERIA_PRIMA else ""


@materias_primas_bp.route("/")
@login_required
def lista():
    tipo_seleccionado = _tipo_filtro_solicitado()
    consulta = MateriaPrima.query

    if tipo_seleccionado:
        consulta = consulta.filter(MateriaPrima.tipo == tipo_seleccionado)

    materias = consulta.order_by(MateriaPrima.nombre).all()
    return render_template(
        "materias_primas/lista.html",
        materias=materias,
        tipos=TIPOS_MATERIA_PRIMA,
        tipo_seleccionado=tipo_seleccionado,
    )


@materias_primas_bp.route("/buscar")
@login_required
def buscar():
    termino = (request.args.get("q") or "").strip()
    tipo_seleccionado = _tipo_filtro_solicitado()

    if len(termino) < 3:
        materias = []
        empty_message = _("Escribe al menos 3 caracteres para buscar.")
    else:
        escaped = (
            termino.replace("\\", "\\\\")
            .replace("%", "\\%")
            .replace("_", "\\_")
        )
        consulta = MateriaPrima.query.filter(
            MateriaPrima.nombre.ilike(
                f"{escaped}%",
                escape="\\",
            )
        )

        if tipo_seleccionado:
            consulta = consulta.filter(
                MateriaPrima.tipo == tipo_seleccionado
            )

        materias = consulta.order_by(MateriaPrima.nombre).all()
        empty_message = _("No se encontraron materias primas.")

    return render_template(
        "materias_primas/_filas_lista.html",
        materias=materias,
        empty_message=empty_message,
    )


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
            flash(_("Nombre, tipo y unidad son obligatorios"), "danger")
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
        flash(_("Materia prima creada correctamente"), "success")
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
            flash(_("Nombre, tipo y unidad son obligatorios"), "danger")
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
        flash(_("Materia prima actualizada correctamente"), "success")
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
            _("No se puede eliminar la materia prima porque tiene lotes asociados. "
              "Elimina o ajusta primero los lotes."),
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
    flash(_("Materia prima eliminada correctamente"), "success")
    return redirect(url_for("materias_primas.lista"))

@materias_primas_bp.route("/<int:mp_id>/lotes/nuevo", methods=["GET", "POST"])
@login_required
@role_required("ADMIN", "GESTOR")
def crear_lote(mp_id):
    mp = MateriaPrima.query.get_or_404(mp_id)

    if request.method == "POST":
        codigo_lote = (request.form.get("codigo_lote") or "").strip()
        fecha_compra = request.form.get("fecha_compra") or None
        proveedor = request.form.get("proveedor") or None
        cantidad = _to_float(request.form.get("cantidad_inicial"))
        costo_unitario = _to_float(request.form.get("costo_unitario"))
        fecha_vencimiento = request.form.get("fecha_vencimiento") or None
        notas = request.form.get("notas") or None

        if not codigo_lote or cantidad is None:
            flash(_("Código de lote y cantidad son obligatorios."), "danger")
            return redirect(url_for("materias_primas.crear_lote", mp_id=mp.id))

        if cantidad <= 0:
            flash(_("La cantidad debe ser mayor que cero."), "danger")
            return redirect(url_for("materias_primas.crear_lote", mp_id=mp.id))

        try:
            certificado = save_quality_certificate(
                request.files.get("certificado_calidad")
            )
        except InvalidQualityCertificate as error:
            flash(str(error), "danger")
            return redirect(url_for("materias_primas.crear_lote", mp_id=mp.id))

        lote = LoteMateriaPrima(
            id_materia_prima=mp.id,
            codigo_lote=codigo_lote,
            fecha_compra=fecha_compra,
            proveedor=proveedor,
            cantidad_inicial=cantidad,
            cantidad_disponible=cantidad,
            costo_unitario=costo_unitario,
            fecha_vencimiento=fecha_vencimiento,
            notas=notas,
            certificado_calidad_archivo=(certificado or (None, None))[0],
            certificado_calidad_nombre=(certificado or (None, None))[1],
        )
        db.session.add(lote)
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            if certificado:
                delete_quality_certificate(certificado[0])
            raise

        flash(_("Lote creado correctamente."), "success")
        return redirect(url_for("materias_primas.detalle", mp_id=mp.id))

    return render_template(
        "materias_primas/lote_formulario.html",
        mp=mp,
        lote=None,
        accion="crear",
        maximo_certificado_mb=maximum_certificate_size_mb(),
    )

@materias_primas_bp.route("/<int:mp_id>/lotes/<int:lote_id>/editar", methods=["GET", "POST"])
@login_required
@role_required("ADMIN", "GESTOR")
def editar_lote(mp_id, lote_id):
    mp = MateriaPrima.query.get_or_404(mp_id)
    lote = LoteMateriaPrima.query.get_or_404(lote_id)

    if lote.id_materia_prima != mp.id:
        flash(_("El lote no pertenece a esta materia prima."), "danger")
        return redirect(url_for("materias_primas.detalle", mp_id=mp.id))

    if request.method == "POST":
        codigo_lote = (request.form.get("codigo_lote") or "").strip()
        fecha_compra = request.form.get("fecha_compra") or None
        proveedor = request.form.get("proveedor") or None
        cantidad_adicional = _to_float(request.form.get("cantidad_inicial"), 0.0)
        costo_unitario = _to_float(request.form.get("costo_unitario"))
        fecha_vencimiento = request.form.get("fecha_vencimiento") or None
        notas = request.form.get("notas") or None

        if not codigo_lote:
            flash(_("El código de lote es obligatorio."), "danger")
            return redirect(url_for("materias_primas.editar_lote", mp_id=mp.id, lote_id=lote.id))

        if cantidad_adicional < 0:
            flash(_("La cantidad a agregar no puede ser negativa."), "danger")
            return redirect(url_for("materias_primas.editar_lote", mp_id=mp.id, lote_id=lote.id))

        try:
            certificado_nuevo = save_quality_certificate(
                request.files.get("certificado_calidad")
            )
        except InvalidQualityCertificate as error:
            flash(str(error), "danger")
            return redirect(url_for("materias_primas.editar_lote", mp_id=mp.id, lote_id=lote.id))

        certificado_anterior = lote.certificado_calidad_archivo

        lote.codigo_lote = codigo_lote
        lote.fecha_compra = fecha_compra
        lote.proveedor = proveedor
        lote.fecha_vencimiento = fecha_vencimiento
        lote.notas = notas
        lote.costo_unitario = costo_unitario

        if cantidad_adicional > 0:
            lote.cantidad_inicial = float(lote.cantidad_inicial) + cantidad_adicional
            lote.cantidad_disponible = float(lote.cantidad_disponible) + cantidad_adicional

        if certificado_nuevo:
            lote.certificado_calidad_archivo = certificado_nuevo[0]
            lote.certificado_calidad_nombre = certificado_nuevo[1]

        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            if certificado_nuevo:
                delete_quality_certificate(certificado_nuevo[0])
            raise

        if certificado_nuevo:
            delete_quality_certificate(certificado_anterior)
        flash(_("Lote actualizado correctamente."), "success")
        return redirect(url_for("materias_primas.detalle", mp_id=mp.id))

    return render_template(
        "materias_primas/lote_formulario.html",
        mp=mp,
        lote=lote,
        accion="editar",
        maximo_certificado_mb=maximum_certificate_size_mb(),
    )


@materias_primas_bp.route(
    "/<int:mp_id>/lotes/<int:lote_id>/certificado"
)
@login_required
def descargar_certificado_lote(mp_id, lote_id):
    lote = LoteMateriaPrima.query.get_or_404(lote_id)

    if lote.id_materia_prima != mp_id or not lote.certificado_calidad_archivo:
        abort(404)

    return send_from_directory(
        certificate_directory(),
        lote.certificado_calidad_archivo,
        as_attachment=True,
        download_name=lote.certificado_calidad_nombre,
    )

@materias_primas_bp.route("/<int:mp_id>/lotes/<int:lote_id>/eliminar", methods=["POST"])
@login_required
@role_required("ADMIN", "GESTOR")
def eliminar_lote(mp_id, lote_id):
    mp = MateriaPrima.query.get_or_404(mp_id)
    lote = LoteMateriaPrima.query.get_or_404(lote_id)

    if lote.id_materia_prima != mp.id:
        flash(_("El lote no pertenece a esta materia prima"), "danger")
        return redirect(url_for("materias_primas.detalle", mp_id=mp.id))

    certificado = lote.certificado_calidad_archivo
    db.session.delete(lote)
    db.session.commit()
    delete_quality_certificate(certificado)
    flash(_("Lote eliminado correctamente"), "success")
    return redirect(url_for("materias_primas.detalle", mp_id=mp.id))

def _to_float(value, default=None):
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
