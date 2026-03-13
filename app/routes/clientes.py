from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required

from app.authz import role_required
from app.extensions import db
from app.models import Cliente


clientes_bp = Blueprint(
    "clientes",
    __name__,
    url_prefix="/clientes",
)


def _tipos_cliente():
    """
    Obtiene los valores del Enum tipo_cliente desde el modelo.
    """
    try:
        return Cliente.__table__.c.tipo.type.enums
    except Exception:
        return []


@clientes_bp.route("/")
@login_required
def lista():
    q = request.args.get("q", "", type=str).strip()
    activos = request.args.get("activos", "", type=str).strip()

    query = Cliente.query

    if q:
        query = query.filter(Cliente.nombre.ilike(f"%{q}%"))

    if activos == "si":
        query = query.filter(Cliente.activo.is_(True))
    elif activos == "no":
        query = query.filter(Cliente.activo.is_(False))

    clientes = query.order_by(Cliente.nombre.asc()).all()

    return render_template(
        "clientes/lista.html",
        clientes=clientes,
        q=q,
        activos=activos,
    )


@clientes_bp.route("/nuevo", methods=["GET", "POST"])
@login_required
@role_required("ADMIN", "GESTOR")
def crear():
    tipos = _tipos_cliente()

    if request.method == "POST":
        nombre = (request.form.get("nombre") or "").strip()
        tipo = request.form.get("tipo") or None
        contacto = (request.form.get("contacto") or "").strip() or None
        telefono = (request.form.get("telefono") or "").strip() or None
        direccion = (request.form.get("direccion") or "").strip() or None
        activo = request.form.get("activo") == "on"

        if not nombre:
            flash("El nombre es obligatorio.", "danger")
            return redirect(url_for("clientes.crear"))

        cliente = Cliente(
            nombre=nombre,
            tipo=tipo if tipo else None,
            contacto=contacto,
            telefono=telefono,
            direccion=direccion,
            activo=activo,
        )
        db.session.add(cliente)
        db.session.commit()

        flash("Cliente creado correctamente.", "success")
        return redirect(url_for("clientes.lista"))

    return render_template(
        "clientes/formulario.html",
        accion="crear",
        cliente=None,
        tipos=tipos,
    )


@clientes_bp.route("/<int:cliente_id>/editar", methods=["GET", "POST"])
@login_required
@role_required("ADMIN", "GESTOR")
def editar(cliente_id):
    cliente = Cliente.query.get_or_404(cliente_id)
    tipos = _tipos_cliente()

    if request.method == "POST":
        nombre = (request.form.get("nombre") or "").strip()
        tipo = request.form.get("tipo") or None
        contacto = (request.form.get("contacto") or "").strip() or None
        telefono = (request.form.get("telefono") or "").strip() or None
        direccion = (request.form.get("direccion") or "").strip() or None
        activo = request.form.get("activo") == "on"

        if not nombre:
            flash("El nombre es obligatorio.", "danger")
            return redirect(url_for("clientes.editar", cliente_id=cliente.id))

        cliente.nombre = nombre
        cliente.tipo = tipo if tipo else None
        cliente.contacto = contacto
        cliente.telefono = telefono
        cliente.direccion = direccion
        cliente.activo = activo

        db.session.commit()

        flash("Cliente actualizado correctamente.", "success")
        return redirect(url_for("clientes.lista"))

    return render_template(
        "clientes/formulario.html",
        accion="editar",
        cliente=cliente,
        tipos=tipos,
    )


@clientes_bp.route("/<int:cliente_id>/eliminar", methods=["POST"])
@login_required
@role_required("ADMIN", "GESTOR")
def eliminar(cliente_id):
    cliente = Cliente.query.get_or_404(cliente_id)

    db.session.delete(cliente)
    db.session.commit()

    flash("Cliente eliminado correctamente.", "success")
    return redirect(url_for("clientes.lista"))