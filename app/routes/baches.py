from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    send_file,
)
from app.extensions import db
from app.models import (
    Bache,
    Receta,
    BacheMateriaPrima,
    BacheLevaduraUso,
    LoteMateriaPrima,
    MateriaPrima,
    MedicionBache,
)

from flask_login import login_required
from app.authz import role_required

from datetime import datetime
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas


baches_bp = Blueprint(
    "baches",
    __name__,
    url_prefix="/baches",
)


def _to_sg(x):
    """Convierte densidad a SG:
    - si viene como 1055 -> 1.055
    - si ya viene como 1.055 -> 1.055
    """
    if x is None:
        return None
    try:
        v = float(x)
    except Exception:
        return None
    return v / 1000.0 if v > 10 else v

def _bache_detalle_context(bache):
    # materias primas usadas
    materias = (
        db.session.query(BacheMateriaPrima, LoteMateriaPrima, MateriaPrima)
        .join(LoteMateriaPrima, BacheMateriaPrima.id_lote == LoteMateriaPrima.id)
        .join(MateriaPrima, LoteMateriaPrima.id_materia_prima == MateriaPrima.id)
        .filter(BacheMateriaPrima.id_bache == bache.id)
        .all()
    )

    # mediciones (histórico completo)
    mediciones = (
        MedicionBache.query
        .filter_by(id_bache=bache.id)
        .order_by(MedicionBache.id_bache.desc())
        .all()
    )

    usos_levadura_por_lote = _usos_levadura_por_lote(bache.id)


    # últimas por tipo
    def last_of(tipo):
        return (
            MedicionBache.query
            .filter_by(id_bache=bache.id, tipo=tipo)
            .order_by(MedicionBache.id_bache.desc())
            .first()
        )

    ult_dens = last_of("DENSIDAD")
    ult_temp = last_of("TEMPERATURA")
    ult_ph = last_of("PH")

    og = _to_sg(bache.densidad_inicial)
    fg = _to_sg(ult_dens.valor) if ult_dens else None

    abv = None
    atenuacion = None
    if og is not None and fg is not None and og > 1.0 and fg > 0:
        abv = (og - fg) * 131.25
        if og - 1.0 != 0:
            atenuacion = ((og - fg) / (og - 1.0)) * 100.0

    return {
        "materias": materias,
        "mediciones": mediciones,
        "ult_dens": ult_dens,
        "ult_temp": ult_temp,
        "ult_ph": ult_ph,
        "og": og,
        "fg": fg,
        "abv": abv,
        "atenuacion": atenuacion,
        "usos_levadura_por_lote": usos_levadura_por_lote,
    }


def _guardar_usos_levadura(bache, lote_ids, lev_tipo_uso, lev_generacion, lev_comentarios):
    """
    Crea/actualiza BacheLevaduraUso para las filas donde el lote sea de MateriaPrima tipo LEVADURA.
    Se asume que los arrays son paralelos a las filas del formulario (mismo índice).
    """
    # Prefetch lotes para evitar N queries
    lotes_int = []
    for lid in lote_ids:
        if lid:
            try:
                lotes_int.append(int(lid))
            except Exception:
                pass

    lotes_map = {}
    if lotes_int:
        for l in LoteMateriaPrima.query.filter(LoteMateriaPrima.id.in_(lotes_int)).all():
            lotes_map[l.id] = l

    for i in range(len(lote_ids)):
        lid = lote_ids[i]
        if not lid:
            continue

        try:
            lid_int = int(lid)
        except Exception:
            continue

        lote = lotes_map.get(lid_int)
        if not lote:
            continue

        # Solo levadura
        if not lote.materia_prima or lote.materia_prima.tipo != "LEVADURA":
            continue

        tipo = (lev_tipo_uso[i] if i < len(lev_tipo_uso) else "NUEVA") or "NUEVA"
        if tipo not in ("NUEVA", "REUTILIZADA"):
            tipo = "NUEVA"

        gen = 0
        if tipo == "REUTILIZADA":
            try:
                gen = int(lev_generacion[i]) if i < len(lev_generacion) and lev_generacion[i] else 1
            except Exception:
                gen = 1
            gen = max(1, min(8, gen))
        else:
            gen = 0

        comentario = lev_comentarios[i] if i < len(lev_comentarios) else None
        comentario = comentario or None

        uso = BacheLevaduraUso.query.filter_by(id_bache=bache.id, id_lote=lote.id).first()
        if not uso:
            uso = BacheLevaduraUso(
                id_bache=bache.id,
                id_lote=lote.id,
                fecha_inoculacion=datetime.utcnow(),
            )
            db.session.add(uso)

        uso.tipo_uso = tipo
        uso.generacion = gen
        uso.comentarios = comentario

def _usos_levadura_por_lote(bache_id: int) -> dict:
    """
    Retorna {id_lote: BacheLevaduraUso} para un bache.
    """
    usos = (
        BacheLevaduraUso.query
        .filter_by(id_bache=bache_id)
        .all()
    )
    return {u.id_lote: u for u in usos}

@baches_bp.route("/")
@login_required
def lista():
    page = request.args.get("page", 1, type=int)
    q = request.args.get("q", "", type=str).strip()

    query = Bache.query

    if q:
        query = query.filter(Bache.codigo_bache.ilike(f"%{q}%"))

    pagination = query.order_by(Bache.fecha_coccion.desc()).paginate(
        page=page, per_page=10, error_out=False
    )

    return render_template(
        "baches/lista.html",
        baches=pagination.items,
        pagination=pagination,
        q=q,
    )


@baches_bp.route("/nuevo", methods=["GET", "POST"])
@login_required
@role_required("ADMIN", "GESTOR")
def crear():
    recetas = Receta.query.order_by(Receta.nombre).all()
    lotes = (
        LoteMateriaPrima.query.join(MateriaPrima)
        .order_by(MateriaPrima.nombre, LoteMateriaPrima.codigo_lote)
        .all()
    )

    estados = [
        "PLANIFICADO",
        "EN_CURSO",
        "FERMENTANDO",
        "MADURANDO",
        "LISTO",
        "COMPLETADO",
        "DESCARTADO",
    ]
    unidades = ["KG", "G", "L", "ML", "UNIDAD"]

    if request.method == "POST":
        codigo_bache = request.form.get("codigo_bache")
        nombre_cerveza = request.form.get("nombre_cerveza")
        id_receta = request.form.get("id_receta") or None
        fecha_coccion = request.form.get("fecha_coccion")
        vol_obj = request.form.get("volumen_objetivo_litros") or None
        vol_fin = request.form.get("volumen_final_litros") or None
        dens_ini = request.form.get("densidad_inicial") or None
        ph_macerado = request.form.get("ph_macerado") or None
        ph_fin_hervido = request.form.get("ph_fin_hervido") or None
        temp_maceracion = request.form.get("temp_maceracion") or None
        temp_mashoff = request.form.get("temp_mashoff") or None
        estado = request.form.get("estado") or "PLANIFICADO"
        notas = request.form.get("notas") or None

        if not codigo_bache or not nombre_cerveza or not fecha_coccion:
            flash("Código, nombre de cerveza y fecha de cocción son obligatorios", "danger")
            return redirect(url_for("baches.crear"))

        bache = Bache(
            codigo_bache=codigo_bache,
            nombre_cerveza=nombre_cerveza,
            id_receta=int(id_receta) if id_receta else None,
            fecha_coccion=fecha_coccion,
            volumen_objetivo_litros=float(vol_obj) if vol_obj else None,
            volumen_final_litros=float(vol_fin) if vol_fin else None,
            densidad_inicial=float(dens_ini) if dens_ini else None,
            ph_macerado=float(ph_macerado) if ph_macerado else None,
            ph_fin_hervido=float(ph_fin_hervido) if ph_fin_hervido else None,
            temp_maceracion=float(temp_maceracion) if temp_maceracion else None,
            temp_mashoff=float(temp_mashoff) if temp_mashoff else None,
            estado=estado,
            notas=notas,
        )
        db.session.add(bache)
        db.session.flush()  # para tener bache.id

        # ---------- Materias primas asociadas ----------
        lote_ids = request.form.getlist("lote_id")
        cantidades = request.form.getlist("cantidad")
        unidades_form = request.form.getlist("unidad")
        etapas = request.form.getlist("etapa_proceso")
        tipos_aplic = request.form.getlist("tipo_aplicacion")
        tiempos_hervor = request.form.getlist("tiempo_hervor")
        dias_ferm = request.form.getlist("dias_fermentacion")

        for i in range(len(lote_ids)):
            lote_id = lote_ids[i]
            cant = cantidades[i] if i < len(cantidades) else ""
            unidad = unidades_form[i] if i < len(unidades_form) else ""
            etapa_proc = etapas[i] if i < len(etapas) else "OTRA"
            tipo_ap = tipos_aplic[i] if i < len(tipos_aplic) else "GENERAL"
            t_hervor = tiempos_hervor[i] if i < len(tiempos_hervor) else ""
            d_ferm = dias_ferm[i] if i < len(dias_ferm) else ""

            if not lote_id or not cant:
                continue

            bmp = BacheMateriaPrima(
                id_bache=bache.id,
                id_lote=int(lote_id),
                cantidad_usada=float(cant),
                unidad=unidad or "KG",
                etapa_proceso=etapa_proc or "OTRA",
                tipo_aplicacion=tipo_ap or "GENERAL",
                tiempo_minutos_desde_inicio_hervor=int(t_hervor) if t_hervor else None,
                dias_desde_inicio_fermentacion=int(d_ferm) if d_ferm else None,
            )
            db.session.add(bmp)

        # ---------- Uso de levadura (por filas donde el lote es LEVADURA) ----------
        lev_tipo_uso = request.form.getlist("lev_tipo_uso")
        lev_generacion = request.form.getlist("lev_generacion")
        lev_comentarios = request.form.getlist("lev_comentarios")

        _guardar_usos_levadura(bache, lote_ids, lev_tipo_uso, lev_generacion, lev_comentarios)

        db.session.commit()
        flash("Bache creado correctamente", "success")
        return redirect(url_for("baches.detalle", bache_id=bache.id))

    return render_template(
        "baches/formulario.html",
        accion="crear",
        bache=None,
        recetas=recetas,
        lotes=lotes,
        estados=estados,
        unidades=unidades,
    )


@baches_bp.route("/<int:bache_id>")
@login_required
def detalle(bache_id):
    bache = Bache.query.get_or_404(bache_id)
    ctx = _bache_detalle_context(bache)

    return render_template(
        "baches/detalle.html",
        bache=bache,
        **ctx
    )


@baches_bp.route("/<int:bache_id>/editar", methods=["GET", "POST"])
@login_required
@role_required("ADMIN", "GESTOR")
def editar(bache_id):
    bache = Bache.query.get_or_404(bache_id)
    recetas = Receta.query.order_by(Receta.nombre).all()
    lotes = (
        LoteMateriaPrima.query.join(MateriaPrima)
        .order_by(MateriaPrima.nombre, LoteMateriaPrima.codigo_lote)
        .all()
    )

    estados = [
        "PLANIFICADO",
        "EN_CURSO",
        "FERMENTANDO",
        "MADURANDO",
        "LISTO",
        "COMPLETADO",
        "DESCARTADO",
    ]
    unidades = ["KG", "G", "L", "ML", "UNIDAD"]

    if request.method == "POST":
        bache.codigo_bache = request.form.get("codigo_bache")
        bache.nombre_cerveza = request.form.get("nombre_cerveza")
        id_receta = request.form.get("id_receta") or None
        bache.id_receta = int(id_receta) if id_receta else None
        bache.fecha_coccion = request.form.get("fecha_coccion") or bache.fecha_coccion

        vol_obj = request.form.get("volumen_objetivo_litros") or None
        vol_fin = request.form.get("volumen_final_litros") or None
        dens_ini = request.form.get("densidad_inicial") or None
        ph_macerado = request.form.get("ph_macerado") or None
        ph_fin_hervido = request.form.get("ph_fin_hervido") or None
        temp_maceracion = request.form.get("temp_maceracion") or None
        temp_mashoff = request.form.get("temp_mashoff") or None
        bache.volumen_objetivo_litros = float(vol_obj) if vol_obj else None
        bache.volumen_final_litros = float(vol_fin) if vol_fin else None
        bache.densidad_inicial = float(dens_ini) if dens_ini else None
        bache.ph_macerado = float(ph_macerado) if ph_macerado else None
        bache.ph_fin_hervido = float(ph_fin_hervido) if ph_fin_hervido else None
        bache.temp_maceracion = float(temp_maceracion) if temp_maceracion else None
        bache.temp_mashoff = float(temp_mashoff) if temp_mashoff else None
        bache.estado = request.form.get("estado") or bache.estado
        bache.notas = request.form.get("notas") or None

        if not bache.codigo_bache or not bache.nombre_cerveza or not bache.fecha_coccion:
            flash("Código, nombre de cerveza y fecha de cocción son obligatorios", "danger")
            return redirect(url_for("baches.editar", bache_id=bache.id))

        # Limpiar MP y usos de levadura actuales y reinsertar desde el formulario
        BacheMateriaPrima.query.filter_by(id_bache=bache.id).delete()
        BacheLevaduraUso.query.filter_by(id_bache=bache.id).delete()

        lote_ids = request.form.getlist("lote_id")
        cantidades = request.form.getlist("cantidad")
        unidades_form = request.form.getlist("unidad")
        etapas = request.form.getlist("etapa_proceso")
        tipos_aplic = request.form.getlist("tipo_aplicacion")
        tiempos_hervor = request.form.getlist("tiempo_hervor")
        dias_ferm = request.form.getlist("dias_fermentacion")

        for i in range(len(lote_ids)):
            lote_id = lote_ids[i]
            cant = cantidades[i] if i < len(cantidades) else ""
            unidad = unidades_form[i] if i < len(unidades_form) else ""
            etapa_proc = etapas[i] if i < len(etapas) else "OTRA"
            tipo_ap = tipos_aplic[i] if i < len(tipos_aplic) else "GENERAL"
            t_hervor = tiempos_hervor[i] if i < len(tiempos_hervor) else ""
            d_ferm = dias_ferm[i] if i < len(dias_ferm) else ""

            if not lote_id or not cant:
                continue

            bmp = BacheMateriaPrima(
                id_bache=bache.id,
                id_lote=int(lote_id),
                cantidad_usada=float(cant),
                unidad=unidad or "KG",
                etapa_proceso=etapa_proc or "OTRA",
                tipo_aplicacion=tipo_ap or "GENERAL",
                tiempo_minutos_desde_inicio_hervor=int(t_hervor) if t_hervor else None,
                dias_desde_inicio_fermentacion=int(d_ferm) if d_ferm else None,
            )
            db.session.add(bmp)

        # ---------- Uso de levadura ----------
        lev_tipo_uso = request.form.getlist("lev_tipo_uso")
        lev_generacion = request.form.getlist("lev_generacion")
        lev_comentarios = request.form.getlist("lev_comentarios")
        _guardar_usos_levadura(bache, lote_ids, lev_tipo_uso, lev_generacion, lev_comentarios)

        # ============================
        # Guardar nuevas mediciones
        # ============================
        fechas = request.form.getlist("med_fecha[]")
        tipos = request.form.getlist("med_tipo[]")
        valores = request.form.getlist("med_valor[]")
        comentarios = request.form.getlist("med_comentario[]")

        for i in range(len(fechas)):
            if not fechas[i] or not valores[i]:
                continue

            medicion = MedicionBache(
                id_bache=bache.id,
                fecha=fechas[i],
                tipo=tipos[i],
                valor=float(valores[i]),
                comentario=comentarios[i] or None,
            )
            db.session.add(medicion)

        db.session.commit()
        flash("Bache actualizado correctamente", "success")
        return redirect(url_for("baches.detalle", bache_id=bache.id))

    # GET
    materias = (
        db.session.query(BacheMateriaPrima, LoteMateriaPrima, MateriaPrima)
        .join(LoteMateriaPrima, BacheMateriaPrima.id_lote == LoteMateriaPrima.id)
        .join(MateriaPrima, LoteMateriaPrima.id_materia_prima == MateriaPrima.id)
        .filter(BacheMateriaPrima.id_bache == bache.id)
        .all()
    )

    mediciones = (
        MedicionBache.query
        .filter_by(id_bache=bache.id)
        .order_by(MedicionBache.fecha.desc())
        .all()
    )

    usos_levadura_por_lote = _usos_levadura_por_lote(bache.id)

    return render_template(
        "baches/formulario.html",
        accion="editar",
        bache=bache,
        recetas=recetas,
        lotes=lotes,
        estados=estados,
        unidades=unidades,
        materias=materias,
        mediciones=mediciones,
        usos_levadura_por_lote=usos_levadura_por_lote,
    )


@baches_bp.route("/<int:bache_id>/eliminar", methods=["POST"])
@login_required
@role_required("ADMIN", "GESTOR")
def eliminar(bache_id):
    bache = Bache.query.get_or_404(bache_id)
    db.session.delete(bache)
    db.session.commit()
    flash("Bache eliminado correctamente", "success")
    return redirect(url_for("baches.lista"))


@baches_bp.route("/<int:bache_id>/exportar.pdf")
@login_required
def exportar_pdf(bache_id):
    bache = Bache.query.get_or_404(bache_id)
    ctx = _bache_detalle_context(bache)

    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    y = height - 40
    line_h = 14

    def draw_line(text, dy=1):
        nonlocal y
        c.drawString(40, y, text[:200])
        y -= line_h * dy
        if y < 60:
            c.showPage()
            y = height - 40

    c.setFont("Helvetica-Bold", 14)
    draw_line(f"Reporte de Bache: {bache.codigo_bache} - {bache.nombre_cerveza}", dy=1.5)
    c.setFont("Helvetica", 10)

    draw_line(f"Fecha cocción: {bache.fecha_coccion} | Estado: {bache.estado}")
    if bache.receta:
        draw_line(f"Receta: {bache.receta.nombre} ({bache.receta.estilo or '-'})")
    else:
        draw_line("Receta: -")
    draw_line(f"Volumen objetivo (L): {bache.volumen_objetivo_litros or '-'} | Volumen final (L): {bache.volumen_final_litros or '-'}")
    draw_line(f"Densidad inicial: {bache.densidad_inicial or '-'}")
    draw_line(f"Temp maceración: {bache.temp_maceracion or '-'} C | Temp mash-off: {bache.temp_mashoff or '-'} C")
    draw_line(f"pH macerado: {bache.ph_macerado or '-'} | pH fin hervido: {bache.ph_fin_hervido or '-'}")

    if bache.notas:
        draw_line("Notas:", dy=1.2)
        for chunk in str(bache.notas).splitlines():
            draw_line(f"  {chunk}")

    draw_line("", dy=1)
    c.setFont("Helvetica-Bold", 12)
    draw_line("Indicadores (calculados)", dy=1.2)
    c.setFont("Helvetica", 10)
    og = ctx["og"]
    fg = ctx["fg"]
    abv = ctx["abv"]
    atn = ctx["atenuacion"]

    draw_line(f"OG: {og:.3f}" if og else "OG: -")
    draw_line(f"FG (última densidad): {fg:.3f}" if fg else "FG (última densidad): -")
    draw_line(f"ABV aprox: {abv:.2f} %" if abv is not None else "ABV aprox: -")
    draw_line(f"Atenuación aparente: {atn:.1f} %" if atn is not None else "Atenuación aparente: -")

    draw_line("", dy=1)
    c.setFont("Helvetica-Bold", 12)
    draw_line("Últimas mediciones", dy=1.2)
    c.setFont("Helvetica", 10)

    def fmt_med(m):
        if not m:
            return "-"
        return f"{m.valor} ({m.fecha})" + (f" | {m.comentario}" if m.comentario else "")

    draw_line(f"Densidad: {fmt_med(ctx['ult_dens'])}")
    draw_line(f"Temperatura: {fmt_med(ctx['ult_temp'])}")
    draw_line(f"pH: {fmt_med(ctx['ult_ph'])}")

    draw_line("", dy=1)
    c.setFont("Helvetica-Bold", 11)
    draw_line("Materias primas usadas", dy=1)
    c.setFont("Helvetica", 9)

    for m, lote, mp in ctx["materias"]:
        uso = ctx["usos_levadura_por_lote"].get(lote.id)
        extra = ""
        if mp.tipo == "LEVADURA" and uso:
            if uso.tipo_uso == "REUTILIZADA":
                extra = f" | Uso levadura: REUTILIZADA | G:{uso.generacion}"
            else:
                extra = f" | Uso levadura: NUEVA"

        draw_line(
            f"- {mp.nombre} ({mp.tipo}) | Lote: {lote.codigo_lote} | "
            f"{m.cantidad_usada} {m.unidad} | Etapa: {m.etapa_proceso}"
            f"{extra}"
        )

    draw_line("", dy=1)
    c.setFont("Helvetica-Bold", 12)
    draw_line("Histórico de mediciones", dy=1.2)
    c.setFont("Helvetica", 9)

    for med in ctx["mediciones"]:
        draw_line(
            f"- {med.fecha} | {med.tipo} | {med.valor}"
            + (f" | {med.comentario}" if med.comentario else "")
        )

    c.showPage()
    c.save()

    buffer.seek(0)
    filename = f"bache_{bache.codigo_bache}.pdf"
    return send_file(buffer, mimetype="application/pdf", as_attachment=True, download_name=filename)