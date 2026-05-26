# app/routes/inventario.py

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user

from app.services.chatbot_inventory_client import (
    list_products,
    get_product,
    create_product,
    update_product,
    update_stock,
    delete_product,
    ChatbotInventoryError,
)

def _payload_from_form():
    return {
        "name": request.form.get("name"),
        "style": request.form.get("style"),
        "description": request.form.get("description"),
        "presentation": request.form.get("presentation"),
        "volume_ml": request.form.get("volume_ml") or None,
        "price": request.form.get("price"),
        "stock_quantity": request.form.get("stock_quantity") or 0,
        "active": request.form.get("active") == "on",
    }

inventario_bp = Blueprint("inventario", __name__, url_prefix="/inventario")


def admin_required():
    if not current_user.is_authenticated or current_user.rol.nombre != "ADMIN":
        flash("No tienes permisos para gestionar inventario.", "danger")
        return False
    return True


@inventario_bp.route("/")
@login_required
def lista():
    if not admin_required():
        return redirect(url_for("baches.lista"))

    active = request.args.get("active", "true")

    try:
        data = list_products(active=active)
        products = data.get("items", [])
    except ChatbotInventoryError as e:
        flash(str(e), "danger")
        products = []

    return render_template(
        "inventario/lista.html",
        products=products,
        active=active,
    )

@inventario_bp.route("/nuevo", methods=["GET", "POST"])
@login_required
def nuevo():
    if not admin_required():
        return redirect(url_for("baches.lista"))

    if request.method == "POST":
        try:
            create_product(_payload_from_form())
            flash("Producto creado correctamente.", "success")
            return redirect(url_for("inventario.lista"))
        except ChatbotInventoryError as e:
            flash(str(e), "danger")

    return render_template("inventario/formulario.html", product=None)

@inventario_bp.route("/<int:product_id>/editar", methods=["GET", "POST"])
@login_required
def editar(product_id):
    if not admin_required():
        return redirect(url_for("baches.lista"))

    try:
        product = get_product(product_id)
    except ChatbotInventoryError as e:
        flash(str(e), "danger")
        return redirect(url_for("inventario.lista"))

    if request.method == "POST":
        try:
            update_product(product_id, _payload_from_form())
            flash("Producto actualizado correctamente.", "success")
            return redirect(url_for("inventario.lista"))
        except ChatbotInventoryError as e:
            flash(str(e), "danger")

    return render_template("inventario/formulario.html", product=product)


@inventario_bp.route("/<int:product_id>/stock", methods=["POST"])
@login_required
def stock(product_id):
    if not admin_required():
        return redirect(url_for("baches.lista"))

    try:
        update_stock(product_id, request.form.get("stock_quantity"))
        flash("Stock actualizado correctamente.", "success")
    except ChatbotInventoryError as e:
        flash(str(e), "danger")

    return redirect(url_for("inventario.lista"))


@inventario_bp.route("/<int:product_id>/borrar", methods=["POST"])
@login_required
def borrar(product_id):
    if not admin_required():
        return redirect(url_for("baches.lista"))

    try:
        delete_product(product_id)
        flash("Producto desactivado correctamente.", "success")
    except ChatbotInventoryError as e:
        flash(str(e), "danger")

    return redirect(url_for("inventario.lista"))