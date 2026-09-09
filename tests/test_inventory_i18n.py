import ast
import unittest
from pathlib import Path

from flask import Flask
from flask_babel import Babel, gettext


class InventoryInternationalizationTestCase(unittest.TestCase):
    def setUp(self):
        self.project_root = Path(__file__).resolve().parents[1]
        self.route_path = (
            self.project_root / "app" / "routes" / "inventario.py"
        )
        self.service_path = (
            self.project_root
            / "app"
            / "services"
            / "chatbot_inventory_client.py"
        )
        self.templates_dir = (
            self.project_root / "app" / "templates" / "inventario"
        )
        self.app = Flask(__name__, root_path=str(self.project_root / "app"))
        self.app.config["BABEL_TRANSLATION_DIRECTORIES"] = "translations"
        Babel(self.app, locale_selector=lambda: "en")

    def test_inventory_catalog_entries(self):
        with self.app.test_request_context():
            self.assertEqual(
                gettext("Inventario de cervezas"),
                "Beer inventory",
            )
            self.assertEqual(gettext("Nuevo producto"), "New product")
            self.assertEqual(
                gettext("Producto creado correctamente."),
                "Product created successfully.",
            )
            self.assertEqual(
                gettext("¿Desactivar este producto?"),
                "Deactivate this product?",
            )
            self.assertEqual(
                gettext("Stock de %(product)s", product="American IPA"),
                "Stock for American IPA",
            )

    def test_direct_flash_messages_use_gettext_or_external_error(self):
        tree = ast.parse(self.route_path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not node.args:
                continue
            if not isinstance(node.func, ast.Name) or node.func.id != "flash":
                continue
            message = node.args[0]
            self.assertIsInstance(message, ast.Call)
            self.assertIsInstance(message.func, ast.Name)
            self.assertIn(message.func.id, {"_", "str"})

    def test_api_payload_and_filter_values_are_preserved(self):
        route = self.route_path.read_text(encoding="utf-8")
        service = self.service_path.read_text(encoding="utf-8")
        for key in (
            "name",
            "style",
            "description",
            "presentation",
            "volume_ml",
            "price",
            "stock_quantity",
            "active",
        ):
            self.assertIn(f'"{key}"', route + service)
        self.assertIn('active in ("true", "false")', service)
        self.assertIn('request.args.get("active", "true")', route)
        self.assertIn('request.form.get("active") == "on"', route)

    def test_remote_api_errors_are_preserved_with_translated_fallback(self):
        service = self.service_path.read_text(encoding="utf-8")
        self.assertIn('data.get("error")', service)
        self.assertIn('data.get("message")', service)
        self.assertIn('_("Error al consultar la API de inventario.")', service)

    def test_templates_translate_visible_interface_safely(self):
        listing = (self.templates_dir / "lista.html").read_text(
            encoding="utf-8"
        )
        form = (self.templates_dir / "formulario.html").read_text(
            encoding="utf-8"
        )
        for message in (
            "Inventario de cervezas",
            "Nuevo producto",
            "Activos",
            "Inactivos",
            "Filtrar",
            "Precio",
            "Presentación",
            "No hay productos.",
        ):
            self.assertIn(f"_('{message}')", listing)
        self.assertIn('_("¿Desactivar este producto?")|tojson', listing)
        self.assertNotIn("confirm('¿Desactivar", listing)
        self.assertIn("_('Editar producto') if product", form)
        self.assertIn("_('Nuevo producto')", form)

    def test_product_data_and_default_presentation_are_not_translated(self):
        listing = (self.templates_dir / "lista.html").read_text(
            encoding="utf-8"
        )
        form = (self.templates_dir / "formulario.html").read_text(
            encoding="utf-8"
        )
        for expression in ("p.name", "p.style", "p.presentation"):
            self.assertIn("{{ " + expression + " }}", listing)
        self.assertIn("product.description if product else ''", form)
        self.assertIn("product.presentation if product else 'Lata 330 ml'", form)


if __name__ == "__main__":
    unittest.main()
