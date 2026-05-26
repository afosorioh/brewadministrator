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