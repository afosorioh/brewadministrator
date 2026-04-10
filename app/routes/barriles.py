from app.utils.datetime_utils import now_bogota, today_bogota
from datetime import datetime
import re

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from sqlalchemy import func, and_
from sqlalchemy.orm import aliased

from app.authz import role_required
from app.extensions import db
from app.models import Barril, MovimientoBarril, Bache, Cliente, Receta

barriles_bp = Blueprint(
    "barriles",
    __name__,
    url_prefix="/barriles",
)

def _parse_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def _estado_badge_class(estado: str) -> str:
    mapa = {
        "LIMPIO": "success",
        "LLENO": "primary",
        "ENTREGADO": "warning text-dark",
        "SUCIO": "danger",
        "MANTENIMIENTO": "secondary",
        "BAJA": "dark",
    }
    return mapa.get(estado, "secondary")

def _parse_codigo_barril(codigo: str):
    """
    Separa prefijo y parte numérica.
    Ej: A001 -> ('A', 1, 3)
        B050 -> ('B', 50, 3)
    """
    if not codigo:
        return None

    match = re.fullmatch(r"([A-Za-z]+)(\d+)", codigo.strip())
    if not match:
        return None

    prefijo = match.group(1)
    numero_str = match.group(2)
    return prefijo, int(numero_str), len(numero_str)


def _registrar_movimiento_alta(barril, comentario="Alta inicial"):
    movimiento = MovimientoBarril(
        id_barril=barril.id,
        fecha_hora=now_bogota(),
        tipo_movimiento="ALTA",
        id_usuario=current_user.id if current_user.is_authenticated else None,
        comentario=comentario,
    )
    db.session.add(movimiento)

@barriles_bp.route("/")
@login_required
def lista():
    page = request.args.get("page", 1, type=int)
    q = request.args.get("q", "", type=str).strip()
    estado = request.args.get("estado", "", type=str).strip()
    codigo_bache = request.args.get("codigo_bache", "", type=str).strip()
    fecha_inicio = request.args.get("fecha_inicio", "", type=str).strip()
    fecha_fin = request.args.get("fecha_fin", "", type=str).strip()

    query = Barril.query

    if q:
        query = query.filter(Barril.codigo_barril.ilike(f"%{q}%"))

    if estado:
        query = query.filter(Barril.estado_actual == estado)

    if codigo_bache or fecha_inicio or fecha_fin:
        query = (
            query
            .join(MovimientoBarril, MovimientoBarril.id_barril == Barril.id)
            .outerjoin(Bache, Bache.id == MovimientoBarril.id_bache)
        )

        if codigo_bache:
            query = query.filter(Bache.codigo_bache.ilike(f"%{codigo_bache}%"))

        if fecha_inicio:
            query = query.filter(func.date(MovimientoBarril.fecha_hora) >= fecha_inicio)

        if fecha_fin:
            query = query.filter(func.date(MovimientoBarril.fecha_hora) <= fecha_fin)

        query = query.distinct()

    pagination = query.order_by(Barril.codigo_barril.asc()).paginate(
        page=page,
        per_page=20,
        error_out=False,
    )

    estados = ["LIMPIO", "LLENO", "ENTREGADO", "SUCIO", "MANTENIMIENTO", "BAJA"]

    barriles_data = []
    for barril in pagination.items:
        ultimo_movimiento = (
            MovimientoBarril.query
            .filter_by(id_barril=barril.id)
            .order_by(MovimientoBarril.fecha_hora.desc())
            .first()
        )

        ultimo_llenado = (
            MovimientoBarril.query
            .filter_by(id_barril=barril.id, tipo_movimiento="LLENO")
            .order_by(MovimientoBarril.fecha_hora.desc())
            .first()
        )

        ultima_entrega = (
            MovimientoBarril.query
            .filter_by(id_barril=barril.id, tipo_movimiento="ENTREGADO")
            .order_by(MovimientoBarril.fecha_hora.desc())
            .first()
        )

        capacidad_mostrar = barril.capacidad_litros
        estilo_mostrar = ""
        bache_mostrar = ""
        litros_llenado = ""
        ubicacion = ""

        if barril.estado_actual == "LLENO" and ultimo_llenado:
            capacidad_mostrar = ultimo_llenado.volumen_litros or barril.capacidad_litros
            litros_llenado = ultimo_llenado.volumen_litros or ""

            if ultimo_llenado.bache:
                bache_mostrar = ultimo_llenado.bache.codigo_bache or ""
                if ultimo_llenado.bache.receta and ultimo_llenado.bache.receta.estilo:
                    estilo_mostrar = ultimo_llenado.bache.receta.estilo
                else:
                    estilo_mostrar = ultimo_llenado.bache.nombre_cerveza or ""

        elif barril.estado_actual == "ENTREGADO" and ultima_entrega:
            litros_llenado = ultima_entrega.volumen_litros or ""

            if ultima_entrega.bache:
                bache_mostrar = ultima_entrega.bache.codigo_bache or ""
                if ultima_entrega.bache.receta and ultima_entrega.bache.receta.estilo:
                    estilo_mostrar = ultima_entrega.bache.receta.estilo
                else:
                    estilo_mostrar = ultima_entrega.bache.nombre_cerveza or ""

            if ultima_entrega.cliente:
                ubicacion = ultima_entrega.cliente.nombre or ""

        barriles_data.append({
            "id": barril.id,
            "codigo_barril": barril.codigo_barril,
            "capacidad_mostrar": capacidad_mostrar,
            "fecha_ultimo_estado": ultimo_movimiento.fecha_hora if ultimo_movimiento else None,
            "estado_actual": barril.estado_actual,
            "estilo_mostrar": estilo_mostrar,
            "bache_mostrar": bache_mostrar,
            "litros_llenado": litros_llenado,
            "ubicacion": ubicacion,
        })

    return render_template(
        "barriles/lista.html",
        barriles=barriles_data,
        pagination=pagination,
        q=q,
        estado=estado,
        estados=estados,
        codigo_bache=codigo_bache,
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
    )


@barriles_bp.route("/nuevo", methods=["GET", "POST"])
@login_required
@role_required("ADMIN", "GESTOR")
def crear():
    if request.method == "POST":
        codigo_barril = (request.form.get("codigo_barril") or "").strip().upper()
        capacidad_litros = request.form.get("capacidad_litros") or None
        fecha_ingreso = request.form.get("fecha_ingreso") or None
        notas = request.form.get("notas") or None

        if not codigo_barril or not capacidad_litros:
            flash("Código y capacidad son obligatorios.", "danger")
            return redirect(url_for("barriles.crear"))

        existente = Barril.query.filter_by(codigo_barril=codigo_barril).first()
        if existente:
            flash("Ya existe un barril con ese código.", "danger")
            return redirect(url_for("barriles.crear"))

        barril = Barril(
            codigo_barril=codigo_barril,
            capacidad_litros=float(capacidad_litros),
            fecha_ingreso=fecha_ingreso if fecha_ingreso else today_bogota(),
            estado_actual="LIMPIO",
            notas=notas,
        )
        db.session.add(barril)
        db.session.flush()

        _registrar_movimiento_alta(barril, comentario="Alta individual de barril")

        db.session.commit()
        flash("Barril creado correctamente.", "success")
        return redirect(url_for("barriles.detalle", barril_id=barril.id))

    return render_template("barriles/form_individual.html")


@barriles_bp.route("/nuevo-lote", methods=["GET", "POST"])
@login_required
@role_required("ADMIN", "GESTOR")
def crear_lote():
    if request.method == "POST":
        codigo_inicio = (request.form.get("codigo_inicio") or "").strip().upper()
        codigo_fin = (request.form.get("codigo_fin") or "").strip().upper()
        capacidad_litros = request.form.get("capacidad_litros") or None
        fecha_ingreso = request.form.get("fecha_ingreso") or None
        notas = request.form.get("notas") or None

        if not codigo_inicio or not codigo_fin or not capacidad_litros:
            flash("Código inicio, código fin y capacidad son obligatorios.", "danger")
            return redirect(url_for("barriles.crear_lote"))

        inicio = _parse_codigo_barril(codigo_inicio)
        fin = _parse_codigo_barril(codigo_fin)

        if not inicio or not fin:
            flash("Los códigos deben tener formato tipo A001, B050, etc.", "danger")
            return redirect(url_for("barriles.crear_lote"))

        prefijo_i, numero_i, ancho_i = inicio
        prefijo_f, numero_f, ancho_f = fin

        if prefijo_i != prefijo_f or ancho_i != ancho_f:
            flash("El rango debe usar el mismo prefijo y el mismo formato numérico.", "danger")
            return redirect(url_for("barriles.crear_lote"))

        if numero_f < numero_i:
            flash("El código final no puede ser menor que el inicial.", "danger")
            return redirect(url_for("barriles.crear_lote"))

        codigos = [
            f"{prefijo_i}{str(n).zfill(ancho_i)}"
            for n in range(numero_i, numero_f + 1)
        ]

        existentes = {
            b.codigo_barril
            for b in Barril.query.filter(Barril.codigo_barril.in_(codigos)).all()
        }

        if existentes:
            flash(
                f"Ya existen estos códigos y no se creó el lote: {', '.join(sorted(existentes))}",
                "danger",
            )
            return redirect(url_for("barriles.crear_lote"))

        creados = []
        for codigo in codigos:
            barril = Barril(
                codigo_barril=codigo,
                capacidad_litros=float(capacidad_litros),
                fecha_ingreso=fecha_ingreso if fecha_ingreso else today_bogota(),
                estado_actual="LIMPIO",
                notas=notas,
            )
            db.session.add(barril)
            db.session.flush()

            _registrar_movimiento_alta(
                barril,
                comentario=f"Alta por lote: {codigo_inicio} a {codigo_fin}",
            )
            creados.append(codigo)

        db.session.commit()
        flash(f"Se crearon {len(creados)} barriles correctamente.", "success")
        return redirect(url_for("barriles.lista"))

    return render_template("barriles/form_lote.html")


@barriles_bp.route("/<int:barril_id>")
@login_required
def detalle(barril_id):
    barril = Barril.query.get_or_404(barril_id)

    movimientos = (
        MovimientoBarril.query
        .filter_by(id_barril=barril.id)
        .order_by(MovimientoBarril.fecha_hora.desc())
        .all()
    )

    ultimo_entregado = (
        MovimientoBarril.query
        .filter_by(id_barril=barril.id, tipo_movimiento="ENTREGADO")
        .order_by(MovimientoBarril.fecha_hora.desc())
        .first()
    )

    cliente_actual = None
    cerveza_actual = None

    if barril.estado_actual == "ENTREGADO" and ultimo_entregado:
        if ultimo_entregado.cliente:
            cliente_actual = ultimo_entregado.cliente.nombre

        if ultimo_entregado.bache:
            cerveza_actual = ultimo_entregado.bache.nombre_cerveza

    return render_template(
        "barriles/detalle.html",
        barril=barril,
        movimientos=movimientos,
        cliente_actual=cliente_actual,
        cerveza_actual=cerveza_actual,
    )

@barriles_bp.route("/llenado", methods=["GET", "POST"])
@login_required
@role_required("ADMIN", "GESTOR")
def llenado():
    barriles = (
        Barril.query
        .filter(Barril.estado_actual == "LIMPIO")
        .order_by(Barril.codigo_barril.asc())
        .all()
    )

    baches = (
        Bache.query
        .order_by(Bache.fecha_coccion.desc(), Bache.codigo_bache.asc())
        .all()
    )

    if request.method == "POST":
        id_barril = request.form.get("id_barril") or None
        id_bache = request.form.get("id_bache") or None
        volumen_litros = request.form.get("volumen_litros") or None
        comentario = request.form.get("comentario") or None

        if not id_barril or not id_bache or not volumen_litros:
            flash("Barril, bache y volumen son obligatorios.", "danger")
            return redirect(url_for("barriles.llenado"))

        barril = Barril.query.get(id_barril)
        bache = Bache.query.get(id_bache)

        if not barril:
            flash("El barril seleccionado no existe.", "danger")
            return redirect(url_for("barriles.llenado"))

        if not bache:
            flash("El bache seleccionado no existe.", "danger")
            return redirect(url_for("barriles.llenado"))

        if barril.estado_actual != "LIMPIO":
            flash("Solo se pueden llenar barriles en estado LIMPIO.", "danger")
            return redirect(url_for("barriles.llenado"))

        try:
            volumen = float(volumen_litros)
        except ValueError:
            flash("El volumen debe ser numérico.", "danger")
            return redirect(url_for("barriles.llenado"))

        if volumen <= 0:
            flash("El volumen debe ser mayor que cero.", "danger")
            return redirect(url_for("barriles.llenado"))

        if float(barril.capacidad_litros) < volumen:
            flash(
                f"El volumen no puede superar la capacidad del barril ({barril.capacidad_litros} L).",
                "danger",
            )
            return redirect(url_for("barriles.llenado"))

        movimiento = MovimientoBarril(
            id_barril=barril.id,
            fecha_hora=now_bogota(),
            tipo_movimiento="LLENO",
            id_bache=bache.id,
            id_cliente=None,
            id_usuario=current_user.id,
            volumen_litros=volumen,
            comentario=comentario,
        )
        db.session.add(movimiento)

        barril.estado_actual = "LLENO"

        db.session.commit()

        flash("Llenado de barril registrado correctamente.", "success")
        return redirect(url_for("barriles.detalle", barril_id=barril.id))

    return render_template(
        "barriles/llenado.html",
        barriles=barriles,
        baches=baches,
    )

@barriles_bp.route("/entrega", methods=["GET", "POST"])
@login_required
@role_required("ADMIN", "GESTOR")
def entrega():
    barriles = (
        Barril.query
        .filter(Barril.estado_actual == "LLENO")
        .order_by(Barril.codigo_barril.asc())
        .all()
    )

    clientes = (
        Cliente.query
        .filter(Cliente.activo.is_(True))
        .order_by(Cliente.nombre.asc())
        .all()
    )

    if request.method == "POST":
        id_barril = request.form.get("id_barril") or None
        destino = (request.form.get("destino") or "CLIENTE").strip().upper()
        id_cliente = request.form.get("id_cliente") or None
        comentario = request.form.get("comentario") or None

        if not id_barril:
            flash("Debes seleccionar un barril.", "danger")
            return redirect(url_for("barriles.entrega"))

        barril = Barril.query.get(id_barril)

        if not barril:
            flash("El barril seleccionado no existe.", "danger")
            return redirect(url_for("barriles.entrega"))

        if barril.estado_actual != "LLENO":
            flash("Solo se pueden procesar barriles en estado LLENO.", "danger")
            return redirect(url_for("barriles.entrega"))

        ultimo_llenado = (
            MovimientoBarril.query
            .filter_by(id_barril=barril.id, tipo_movimiento="LLENO")
            .order_by(MovimientoBarril.fecha_hora.desc())
            .first()
        )

        if not ultimo_llenado:
            flash("No se encontró un movimiento de llenado previo para este barril.", "danger")
            return redirect(url_for("barriles.entrega"))

        if destino == "CLIENTE":
            if not id_cliente:
                flash("Debes seleccionar un cliente.", "danger")
                return redirect(url_for("barriles.entrega"))

            cliente = Cliente.query.get(id_cliente)
            if not cliente:
                flash("El cliente seleccionado no existe.", "danger")
                return redirect(url_for("barriles.entrega"))

            movimiento = MovimientoBarril(
                id_barril=barril.id,
                fecha_hora=now_bogota(),
                tipo_movimiento="ENTREGADO",
                id_bache=ultimo_llenado.id_bache,
                id_cliente=cliente.id,
                id_usuario=current_user.id,
                volumen_litros=ultimo_llenado.volumen_litros,
                comentario=comentario,
            )
            db.session.add(movimiento)

            barril.estado_actual = "ENTREGADO"

            db.session.commit()

            flash("Entrega de barril registrada correctamente.", "success")
            return redirect(url_for("barriles.detalle", barril_id=barril.id))

        elif destino == "LATAS":
            movimiento = MovimientoBarril(
                id_barril=barril.id,
                fecha_hora=now_bogota(),
                tipo_movimiento="LATAS",
                id_bache=ultimo_llenado.id_bache,
                id_cliente=None,
                id_usuario=current_user.id,
                volumen_litros=ultimo_llenado.volumen_litros,
                comentario=comentario,
            )
            db.session.add(movimiento)

            barril.estado_actual = "SUCIO"

            db.session.commit()

            flash("Salida a latas registrada correctamente. El barril quedó en estado SUCIO.", "success")
            return redirect(url_for("barriles.detalle", barril_id=barril.id))

        else:
            flash("Destino no válido.", "danger")
            return redirect(url_for("barriles.entrega"))

    return render_template(
        "barriles/entrega.html",
        barriles=barriles,
        clientes=clientes,
    )

@barriles_bp.route("/devolucion", methods=["GET", "POST"])
@login_required
@role_required("ADMIN", "GESTOR")
def devolucion():
    barriles = (
        Barril.query
        .filter(Barril.estado_actual == "ENTREGADO")
        .order_by(Barril.codigo_barril.asc())
        .all()
    )

    if request.method == "POST":
        id_barril = request.form.get("id_barril") or None
        comentario = request.form.get("comentario") or None

        if not id_barril:
            flash("Debes seleccionar un barril.", "danger")
            return redirect(url_for("barriles.devolucion"))

        barril = Barril.query.get(id_barril)

        if not barril:
            flash("El barril seleccionado no existe.", "danger")
            return redirect(url_for("barriles.devolucion"))

        if barril.estado_actual != "ENTREGADO":
            flash("Solo se pueden devolver barriles en estado ENTREGADO.", "danger")
            return redirect(url_for("barriles.devolucion"))

        ultima_entrega = (
            MovimientoBarril.query
            .filter_by(id_barril=barril.id, tipo_movimiento="ENTREGADO")
            .order_by(MovimientoBarril.fecha_hora.desc())
            .first()
        )

        if not ultima_entrega:
            flash("No se encontró una entrega previa para este barril.", "danger")
            return redirect(url_for("barriles.devolucion"))

        movimiento = MovimientoBarril(
            id_barril=barril.id,
            fecha_hora=now_bogota(),
            tipo_movimiento="DEVUELTO",
            id_bache=ultima_entrega.id_bache,
            id_cliente=ultima_entrega.id_cliente,
            id_usuario=current_user.id,
            volumen_litros=ultima_entrega.volumen_litros,
            comentario=comentario,
        )
        db.session.add(movimiento)

        barril.estado_actual = "SUCIO"

        db.session.commit()

        flash("Devolución de barril registrada correctamente.", "success")
        return redirect(url_for("barriles.detalle", barril_id=barril.id))

    return render_template(
        "barriles/devolucion.html",
        barriles=barriles,
    )

@barriles_bp.route("/lavado", methods=["GET", "POST"])
@login_required
@role_required("ADMIN", "GESTOR")
def lavado():
    barriles = (
        Barril.query
        .filter(Barril.estado_actual == "SUCIO")
        .order_by(Barril.codigo_barril.asc())
        .all()
    )

    if request.method == "POST":
        id_barril = request.form.get("id_barril") or None
        comentario = request.form.get("comentario") or None

        if not id_barril:
            flash("Debes seleccionar un barril.", "danger")
            return redirect(url_for("barriles.lavado"))

        barril = Barril.query.get(id_barril)

        if not barril:
            flash("El barril seleccionado no existe.", "danger")
            return redirect(url_for("barriles.lavado"))

        if barril.estado_actual != "SUCIO":
            flash("Solo se pueden lavar barriles en estado SUCIO.", "danger")
            return redirect(url_for("barriles.lavado"))

        ultimo_movimiento = (
            MovimientoBarril.query
            .filter_by(id_barril=barril.id)
            .order_by(MovimientoBarril.fecha_hora.desc())
            .first()
        )

        movimiento = MovimientoBarril(
            id_barril=barril.id,
            fecha_hora=now_bogota(),
            tipo_movimiento="LAVADO",
            id_bache=ultimo_movimiento.id_bache if ultimo_movimiento else None,
            id_cliente=ultimo_movimiento.id_cliente if ultimo_movimiento else None,
            id_usuario=current_user.id,
            volumen_litros=ultimo_movimiento.volumen_litros if ultimo_movimiento else None,
            comentario=comentario,
        )
        db.session.add(movimiento)

        barril.estado_actual = "LIMPIO"

        db.session.commit()

        flash("Lavado de barril registrado correctamente.", "success")
        return redirect(url_for("barriles.detalle", barril_id=barril.id))

    return render_template(
        "barriles/lavado.html",
        barriles=barriles,
    )

@barriles_bp.route("/consultas")
@login_required
def consultas():
    estados_orden = ["LIMPIO", "LLENO", "ENTREGADO", "SUCIO", "MANTENIMIENTO", "BAJA"]

    fecha_desde_str = (request.args.get("fecha_desde") or "").strip()
    fecha_hasta_str = (request.args.get("fecha_hasta") or "").strip()
    cliente_id = request.args.get("cliente_id", type=int)
    estilo = (request.args.get("estilo") or "").strip()

    fecha_desde = _parse_date(fecha_desde_str)
    fecha_hasta = _parse_date(fecha_hasta_str)

    clientes = (
        Cliente.query
        .filter(Cliente.activo.is_(True))
        .order_by(Cliente.nombre.asc())
        .all()
    )

    estilos_disponibles = [
        row[0]
        for row in db.session.query(Receta.estilo)
        .filter(Receta.estilo.isnot(None), Receta.estilo != "")
        .distinct()
        .order_by(Receta.estilo.asc())
        .all()
    ]

    # ==========================================================
    # 1) GRAFICA: barriles por estado x tamaño
    # ==========================================================
    query_resumen = (
        db.session.query(
            Barril.estado_actual.label("estado"),
            Barril.capacidad_litros.label("capacidad"),
            func.count(Barril.id).label("cantidad"),
        )
        .group_by(Barril.estado_actual, Barril.capacidad_litros)
        .order_by(Barril.capacidad_litros.asc(), Barril.estado_actual.asc())
    )

    resumen_estado_tamano = query_resumen.all()

    capacidades = sorted(
        {float(r.capacidad) for r in resumen_estado_tamano if r.capacidad is not None}
    )

    grafica_labels = estados_orden
    grafica_datasets = []

    for capacidad in capacidades:
        data = []
        for estado_item in estados_orden:
            cantidad = next(
                (
                    int(r.cantidad)
                    for r in resumen_estado_tamano
                    if float(r.capacidad) == capacidad and r.estado == estado_item
                ),
                0,
            )
            data.append(cantidad)

        grafica_datasets.append({
            "label": f"{capacidad:.0f} L" if capacidad == int(capacidad) else f"{capacidad} L",
            "data": data,
        })

    # ==========================================================
    # 2) SUBQUERY: última entrega por barril
    # ==========================================================
    subq_ultima_entrega = (
        db.session.query(
            MovimientoBarril.id_barril.label("id_barril"),
            func.max(MovimientoBarril.fecha_hora).label("max_fecha"),
        )
        .filter(MovimientoBarril.tipo_movimiento == "ENTREGADO")
        .group_by(MovimientoBarril.id_barril)
        .subquery()
    )

    mov_entrega = aliased(MovimientoBarril)
    bache_entrega = aliased(Bache)
    receta_entrega = aliased(Receta)
    cliente_entrega = aliased(Cliente)

    query_entregados = (
        db.session.query(
            cliente_entrega.nombre.label("cliente"),
            Barril.capacidad_litros.label("capacidad"),
            func.coalesce(receta_entrega.estilo, bache_entrega.nombre_cerveza, "SIN ESTILO").label("estilo"),
            func.count(Barril.id).label("cantidad"),
        )
        .join(subq_ultima_entrega, subq_ultima_entrega.c.id_barril == Barril.id)
        .join(
            mov_entrega,
            and_(
                mov_entrega.id_barril == subq_ultima_entrega.c.id_barril,
                mov_entrega.fecha_hora == subq_ultima_entrega.c.max_fecha,
                mov_entrega.tipo_movimiento == "ENTREGADO",
            ),
        )
        .outerjoin(cliente_entrega, cliente_entrega.id == mov_entrega.id_cliente)
        .outerjoin(bache_entrega, bache_entrega.id == mov_entrega.id_bache)
        .outerjoin(receta_entrega, receta_entrega.id == bache_entrega.id_receta)
        .filter(Barril.estado_actual == "ENTREGADO")
    )

    if fecha_desde:
        query_entregados = query_entregados.filter(func.date(mov_entrega.fecha_hora) >= fecha_desde)

    if fecha_hasta:
        query_entregados = query_entregados.filter(func.date(mov_entrega.fecha_hora) <= fecha_hasta)

    if cliente_id:
        query_entregados = query_entregados.filter(mov_entrega.id_cliente == cliente_id)

    if estilo:
        query_entregados = query_entregados.filter(
            func.coalesce(receta_entrega.estilo, bache_entrega.nombre_cerveza) == estilo
        )

    entregados_por_cliente_estilo = (
        query_entregados
        .group_by(
            cliente_entrega.nombre,
            Barril.capacidad_litros,
            func.coalesce(receta_entrega.estilo, bache_entrega.nombre_cerveza, "SIN ESTILO"),
        )
        .order_by(
            cliente_entrega.nombre.asc(),
            Barril.capacidad_litros.asc(),
            func.count(Barril.id).desc(),
            func.coalesce(receta_entrega.estilo, bache_entrega.nombre_cerveza, "SIN ESTILO").asc(),
        )
        .all()
    )

    # ==========================================================
    # 3) SUBQUERY: último llenado por barril
    # ==========================================================
    subq_ultimo_llenado = (
        db.session.query(
            MovimientoBarril.id_barril.label("id_barril"),
            func.max(MovimientoBarril.fecha_hora).label("max_fecha"),
        )
        .filter(MovimientoBarril.tipo_movimiento == "LLENO")
        .group_by(MovimientoBarril.id_barril)
        .subquery()
    )

    mov_llenado = aliased(MovimientoBarril)
    bache_llenado = aliased(Bache)
    receta_llenado = aliased(Receta)

    query_llenos = (
        db.session.query(
            Barril.capacidad_litros.label("capacidad"),
            mov_llenado.volumen_litros.label("volumen"),
            func.coalesce(receta_llenado.estilo, bache_llenado.nombre_cerveza, "SIN ESTILO").label("estilo"),
            func.count(Barril.id).label("cantidad"),
        )
        .join(subq_ultimo_llenado, subq_ultimo_llenado.c.id_barril == Barril.id)
        .join(
            mov_llenado,
            and_(
                mov_llenado.id_barril == subq_ultimo_llenado.c.id_barril,
                mov_llenado.fecha_hora == subq_ultimo_llenado.c.max_fecha,
                mov_llenado.tipo_movimiento == "LLENO",
            ),
        )
        .outerjoin(bache_llenado, bache_llenado.id == mov_llenado.id_bache)
        .outerjoin(receta_llenado, receta_llenado.id == bache_llenado.id_receta)
        .filter(Barril.estado_actual == "LLENO")
    )

    if fecha_desde:
        query_llenos = query_llenos.filter(func.date(mov_llenado.fecha_hora) >= fecha_desde)

    if fecha_hasta:
        query_llenos = query_llenos.filter(func.date(mov_llenado.fecha_hora) <= fecha_hasta)

    if estilo:
        query_llenos = query_llenos.filter(
            func.coalesce(receta_llenado.estilo, bache_llenado.nombre_cerveza) == estilo
        )

    llenos_por_estilo = (
        query_llenos
        .group_by(
            Barril.capacidad_litros,
            mov_llenado.volumen_litros,
            func.coalesce(receta_llenado.estilo, bache_llenado.nombre_cerveza, "SIN ESTILO")
        )
        .order_by(
            Barril.capacidad_litros.asc(),
            mov_llenado.volumen_litros.desc(),
            func.count(Barril.id).desc()
        )
        .all()
    )

    llenos_por_capacidad = []
    capacidad_actual = None
    grupo_actual = []

    for row in llenos_por_estilo:
        if row.capacidad != capacidad_actual:
            if grupo_actual:
                llenos_por_capacidad.append({
                    "capacidad": capacidad_actual,
                    "filas": grupo_actual,
                    "rowspan": len(grupo_actual),
                })
            capacidad_actual = row.capacidad
            grupo_actual = [row]
        else:
            grupo_actual.append(row)

    if grupo_actual:
        llenos_por_capacidad.append({
            "capacidad": capacidad_actual,
            "filas": grupo_actual,
            "rowspan": len(grupo_actual),
        })

    # ==========================================================
    # 4) TABLA EXTRA: rotación de barriles
    #    Cantidad de entregas + última entrega + última devolución
    # ==========================================================
    subq_entregas_count = (
        db.session.query(
            MovimientoBarril.id_barril.label("id_barril"),
            func.count(MovimientoBarril.id).label("total_entregas"),
            func.max(MovimientoBarril.fecha_hora).label("ultima_entrega"),
        )
        .filter(MovimientoBarril.tipo_movimiento == "ENTREGADO")
        .group_by(MovimientoBarril.id_barril)
        .subquery()
    )

    subq_devolucion_max = (
        db.session.query(
            MovimientoBarril.id_barril.label("id_barril"),
            func.max(MovimientoBarril.fecha_hora).label("ultima_devolucion"),
        )
        .filter(MovimientoBarril.tipo_movimiento == "DEVUELTO")
        .group_by(MovimientoBarril.id_barril)
        .subquery()
    )

    rotacion_barriles = (
        db.session.query(
            Barril.id.label("id"),
            Barril.codigo_barril.label("codigo_barril"),
            Barril.capacidad_litros.label("capacidad_litros"),
            Barril.estado_actual.label("estado_actual"),
            func.coalesce(subq_entregas_count.c.total_entregas, 0).label("total_entregas"),
            subq_entregas_count.c.ultima_entrega.label("ultima_entrega"),
            subq_devolucion_max.c.ultima_devolucion.label("ultima_devolucion"),
        )
        .outerjoin(subq_entregas_count, subq_entregas_count.c.id_barril == Barril.id)
        .outerjoin(subq_devolucion_max, subq_devolucion_max.c.id_barril == Barril.id)
        .order_by(func.coalesce(subq_entregas_count.c.total_entregas, 0).desc(), Barril.codigo_barril.asc())
        .limit(25)
        .all()
    )

    # ==========================================================
    # 5) TABLA EXTRA: entregados pendientes de devolución
    # ==========================================================
    mov_entrega_det = aliased(MovimientoBarril)
    bache_entrega_det = aliased(Bache)
    receta_entrega_det = aliased(Receta)
    cliente_entrega_det = aliased(Cliente)

    query_pendientes = (
        db.session.query(
            Barril.id.label("id"),
            Barril.codigo_barril.label("codigo_barril"),
            Barril.capacidad_litros.label("capacidad_litros"),
            mov_entrega_det.fecha_hora.label("fecha_entrega"),
            cliente_entrega_det.nombre.label("cliente"),
            bache_entrega_det.codigo_bache.label("codigo_bache"),
            func.coalesce(receta_entrega_det.estilo, bache_entrega_det.nombre_cerveza, "SIN ESTILO").label("estilo"),
        )
        .join(subq_ultima_entrega, subq_ultima_entrega.c.id_barril == Barril.id)
        .join(
            mov_entrega_det,
            and_(
                mov_entrega_det.id_barril == subq_ultima_entrega.c.id_barril,
                mov_entrega_det.fecha_hora == subq_ultima_entrega.c.max_fecha,
                mov_entrega_det.tipo_movimiento == "ENTREGADO",
            ),
        )
        .outerjoin(cliente_entrega_det, cliente_entrega_det.id == mov_entrega_det.id_cliente)
        .outerjoin(bache_entrega_det, bache_entrega_det.id == mov_entrega_det.id_bache)
        .outerjoin(receta_entrega_det, receta_entrega_det.id == bache_entrega_det.id_receta)
        .filter(Barril.estado_actual == "ENTREGADO")
    )

    if fecha_desde:
        query_pendientes = query_pendientes.filter(func.date(mov_entrega_det.fecha_hora) >= fecha_desde)

    if fecha_hasta:
        query_pendientes = query_pendientes.filter(func.date(mov_entrega_det.fecha_hora) <= fecha_hasta)

    if cliente_id:
        query_pendientes = query_pendientes.filter(mov_entrega_det.id_cliente == cliente_id)

    if estilo:
        query_pendientes = query_pendientes.filter(
            func.coalesce(receta_entrega_det.estilo, bache_entrega_det.nombre_cerveza) == estilo
        )

    pendientes_devolucion_raw = (
        query_pendientes
        .order_by(mov_entrega_det.fecha_hora.asc())
        .all()
    )

    hoy = today_bogota()
    pendientes_devolucion = []
    for row in pendientes_devolucion_raw:
        dias_fuera = None
        if row.fecha_entrega:
            dias_fuera = (hoy - row.fecha_entrega.date()).days

        pendientes_devolucion.append({
            "id": row.id,
            "codigo_barril": row.codigo_barril,
            "capacidad_litros": row.capacidad_litros,
            "fecha_entrega": row.fecha_entrega,
            "cliente": row.cliente,
            "codigo_bache": row.codigo_bache,
            "estilo": row.estilo,
            "dias_fuera": dias_fuera,
        })

    # ==========================================================
    # 6) TARJETAS RESUMEN
    # ==========================================================
    total_barriles = Barril.query.count()
    total_limpios = Barril.query.filter(Barril.estado_actual == "LIMPIO").count()
    total_llenos = Barril.query.filter(Barril.estado_actual == "LLENO").count()
    total_entregados = Barril.query.filter(Barril.estado_actual == "ENTREGADO").count()
    total_sucios = Barril.query.filter(Barril.estado_actual == "SUCIO").count()

    return render_template(
        "barriles/consultas.html",
        grafica_labels=grafica_labels,
        grafica_datasets=grafica_datasets,
        entregados_por_cliente_estilo=entregados_por_cliente_estilo,
        llenos_por_estilo=llenos_por_estilo,
        llenos_por_capacidad=llenos_por_capacidad, 
        rotacion_barriles=rotacion_barriles,
        pendientes_devolucion=pendientes_devolucion,
        clientes=clientes,
        estilos_disponibles=estilos_disponibles,
        fecha_desde=fecha_desde_str,
        fecha_hasta=fecha_hasta_str,
        cliente_id=cliente_id,
        estilo=estilo,
        total_barriles=total_barriles,
        total_limpios=total_limpios,
        total_llenos=total_llenos,
        total_entregados=total_entregados,
        total_sucios=total_sucios,
        estado_badge_map={
            "LIMPIO": "success",
            "LLENO": "primary",
            "ENTREGADO": "warning text-dark",
            "SUCIO": "danger",
            "MANTENIMIENTO": "secondary",
            "BAJA": "dark",
        },
    )

@barriles_bp.route("/<int:barril_id>/baja", methods=["POST"])
@login_required
@role_required("ADMIN", "GESTOR")
def baja(barril_id):
    barril = Barril.query.get_or_404(barril_id)

    if barril.estado_actual == "BAJA":
        flash("El barril ya se encuentra en estado BAJA.", "warning")
        return redirect(url_for("barriles.lista"))

    # Registrar movimiento (importante para auditoría)
    movimiento = MovimientoBarril(
        id_barril=barril.id,
        fecha_hora=now_bogota(),
        tipo_movimiento="BAJA",
        id_usuario=current_user.id,
        comentario="Baja manual del barril (dañado o perdido)",
    )
    db.session.add(movimiento)

    # Cambiar estado
    barril.estado_actual = "BAJA"

    db.session.commit()

    flash(f"Barril {barril.codigo_barril} dado de baja correctamente.", "success")
    return redirect(url_for("barriles.lista"))