from datetime import date, datetime
import re

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user

from app.authz import role_required
from app.extensions import db
from app.models import Barril, MovimientoBarril, Bache, Cliente


barriles_bp = Blueprint(
    "barriles",
    __name__,
    url_prefix="/barriles",
)


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
        fecha_hora=datetime.utcnow(),
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

    query = Barril.query

    if q:
        query = query.filter(Barril.codigo_barril.ilike(f"%{q}%"))

    if estado:
        query = query.filter(Barril.estado_actual == estado)

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

        capacidad_mostrar = barril.capacidad_litros
        estilo_mostrar = ""
        bache_mostrar = ""

        if (
            barril.estado_actual == "LLENO"
            and ultimo_movimiento
            and ultimo_movimiento.tipo_movimiento == "LLENO"
            and ultimo_movimiento.bache
        ):
            capacidad_mostrar = ultimo_movimiento.volumen_litros or barril.capacidad_litros
            bache_mostrar = ultimo_movimiento.bache.codigo_bache or ""

            if ultimo_movimiento.bache.receta and ultimo_movimiento.bache.receta.estilo:
                estilo_mostrar = ultimo_movimiento.bache.receta.estilo
            else:
                estilo_mostrar = ultimo_movimiento.bache.nombre_cerveza or ""

        barriles_data.append({
            "id": barril.id,
            "codigo_barril": barril.codigo_barril,
            "capacidad_mostrar": capacidad_mostrar,
            "fecha_ultimo_estado": ultimo_movimiento.fecha_hora if ultimo_movimiento else None,
            "estado_actual": barril.estado_actual,
            "estilo_mostrar": estilo_mostrar,
            "bache_mostrar": bache_mostrar,
        })

    return render_template(
        "barriles/lista.html",
        barriles=barriles_data,
        pagination=pagination,
        q=q,
        estado=estado,
        estados=estados,
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
            fecha_ingreso=fecha_ingreso if fecha_ingreso else date.today(),
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
                fecha_ingreso=fecha_ingreso if fecha_ingreso else date.today(),
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
            fecha_hora=datetime.utcnow(),
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
        id_cliente = request.form.get("id_cliente") or None
        comentario = request.form.get("comentario") or None

        if not id_barril or not id_cliente:
            flash("Barril y cliente son obligatorios.", "danger")
            return redirect(url_for("barriles.entrega"))

        barril = Barril.query.get(id_barril)
        cliente = Cliente.query.get(id_cliente)

        if not barril:
            flash("El barril seleccionado no existe.", "danger")
            return redirect(url_for("barriles.entrega"))

        if not cliente:
            flash("El cliente seleccionado no existe.", "danger")
            return redirect(url_for("barriles.entrega"))

        if barril.estado_actual != "LLENO":
            flash("Solo se pueden entregar barriles en estado LLENO.", "danger")
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

        movimiento = MovimientoBarril(
            id_barril=barril.id,
            fecha_hora=datetime.utcnow(),
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
            fecha_hora=datetime.utcnow(),
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
            fecha_hora=datetime.utcnow(),
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