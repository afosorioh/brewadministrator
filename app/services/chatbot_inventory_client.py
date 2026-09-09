import requests
from flask import current_app
from flask_babel import gettext as _


class ChatbotInventoryError(Exception):
    pass


def _headers():
    return {
        "X-API-Key": current_app.config["CHATBOT_API_KEY"],
        "Content-Type": "application/json",
    }


def _base_url():
    return current_app.config["CHATBOT_API_BASE_URL"].rstrip("/")


def _handle_response(response):
    try:
        data = response.json()
    except Exception:
        data = {}

    if not response.ok:
        msg = (
            data.get("error")
            or data.get("message")
            or _("Error al consultar la API de inventario.")
        )
        raise ChatbotInventoryError(msg)

    return data


def list_products(active=None):
    params = {}
    if active in ("true", "false"):
        params["active"] = active

    r = requests.get(
        f"{_base_url()}/products",
        headers=_headers(),
        params=params,
        timeout=10,
    )
    return _handle_response(r)


def get_product(product_id):
    r = requests.get(
        f"{_base_url()}/products/{product_id}",
        headers=_headers(),
        timeout=10,
    )
    return _handle_response(r)


def create_product(payload):
    r = requests.post(
        f"{_base_url()}/products",
        headers=_headers(),
        json=payload,
        timeout=10,
    )
    return _handle_response(r)


def update_product(product_id, payload):
    r = requests.put(
        f"{_base_url()}/products/{product_id}",
        headers=_headers(),
        json=payload,
        timeout=10,
    )
    return _handle_response(r)


def update_stock(product_id, stock_quantity):
    r = requests.patch(
        f"{_base_url()}/products/{product_id}/stock",
        headers=_headers(),
        json={"stock_quantity": stock_quantity},
        timeout=10,
    )
    return _handle_response(r)


def delete_product(product_id):
    r = requests.delete(
        f"{_base_url()}/products/{product_id}",
        headers=_headers(),
        timeout=10,
    )
    return _handle_response(r)
