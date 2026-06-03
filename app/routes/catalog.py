# app/routes/catalog.py

import csv
import io
from flask import Blueprint, Response, current_app

from app.services.chatbot_inventory_client import (
    list_products,
    ChatbotInventoryError,
)


catalog_bp = Blueprint("catalog", __name__, url_prefix="/catalog")


def _safe_text(value, default=""):
    if value is None:
        return default
    return str(value).strip()


def _safe_float(value, default=0.0):
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return default


def _build_description(product):
    description = _safe_text(product.get("description"))
    style = _safe_text(product.get("style"))
    presentation = _safe_text(product.get("presentation"))

    parts = []

    if description:
        parts.append(description)

    if style:
        parts.append(f"Estilo: {style}")

    if presentation:
        parts.append(f"Presentación: {presentation}")

    return " | ".join(parts) or "Cerveza artesanal Cervecería Libre"


def _build_image_link(product):
    image_url = _safe_text(product.get("image_url"))

    if image_url:
        return image_url

    product_id = product.get("id")

    return f"https://gestion.cervecerialibre.com/static/catalog/{product_id}.jpg"


def _build_product_link(product):
    product_id = product.get("id")

    return f"https://gestion.cervecerialibre.com/catalog/product/{product_id}"


@catalog_bp.route("/feed.csv", methods=["GET"])
def catalog_feed_csv():
    """
    Feed público CSV para importar productos al Catálogo de Meta / WhatsApp.

    URL pública:
    https://gestion.cervecerialibre.com/catalog/feed.csv
    """

    try:
        data = list_products(active="true")
        products = data.get("items", [])
    except ChatbotInventoryError as e:
        current_app.logger.error(f"Error consultando inventario chatbot: {e}")
        products = []

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "id",
        "title",
        "description",
        "availability",
        "condition",
        "price",
        "link",
        "image_link",
        "brand",
    ])

    for product in products:
        stock = _safe_float(product.get("stock_quantity"))
        price = _safe_float(product.get("price"))

        if stock <= 0:
            continue

        if price <= 0:
            continue

        product_id = product.get("id")
        name = _safe_text(product.get("name"))

        if not product_id or not name:
            continue

        writer.writerow([
            product_id,
            name,
            _build_description(product),
            "in stock",
            "new",
            f"{price:.2f} COP",
            _build_product_link(product),
            _build_image_link(product),
            "Cervecería Libre",
        ])

    csv_content = output.getvalue()

    return Response(
        csv_content,
        mimetype="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": "inline; filename=cerveceria_libre_catalog.csv"
        }
    )