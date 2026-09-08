import ast
import re
import unittest
from pathlib import Path

from flask import Flask, render_template_string
from flask_babel import Babel, gettext


class BatchesInternationalizationTestCase(unittest.TestCase):
    def setUp(self):
        self.project_root = Path(__file__).resolve().parents[1]
        self.app = Flask(__name__, root_path=str(self.project_root / "app"))
        self.app.config["BABEL_TRANSLATION_DIRECTORIES"] = "translations"
        Babel(self.app, locale_selector=lambda: "en")

    def test_batch_catalog_entries(self):
        with self.app.test_request_context():
            self.assertEqual(gettext("Nuevo bache"), "New batch")
            self.assertEqual(gettext("Fermentando"), "Fermenting")
            self.assertEqual(gettext("Guía de receta"), "Recipe guide")
            self.assertEqual(gettext("Viabilidad"), "Viability")
            self.assertEqual(
                gettext(
                    "No existe el lote con ID %(lot_id)s.",
                    lot_id=12,
                ),
                "Lot with ID 12 does not exist.",
            )

    def test_jinja_placeholder_message_renders(self):
        with self.app.test_request_context():
            rendered = render_template_string(
                '{{ _("Mostrando %(shown)s de %(total)s resultados", '
                "shown=2, total=8) }}"
            )
            self.assertEqual(rendered, "Showing 2 of 8 results")

    def test_internal_codes_are_preserved_and_javascript_is_safe(self):
        form = (
            self.project_root / "app" / "templates" / "baches" / "formulario.html"
        ).read_text(encoding="utf-8")
        detail = (
            self.project_root / "app" / "templates" / "baches" / "detalle.html"
        ).read_text(encoding="utf-8")
        listing = (
            self.project_root / "app" / "templates" / "baches" / "lista.html"
        ).read_text(encoding="utf-8")

        for code in (
            "PLANIFICADO",
            "FERMENTANDO",
            "DRY_HOP",
            "VIABILIDAD",
            "REUTILIZADA",
        ):
            self.assertIn(f'"{code}"', form)

        self.assertIn('<option value="{{ e }}"', form)
        self.assertIn('<option value="{{ val }}"', form)
        self.assertIn("const batchI18n =", form)
        self.assertIn("|tojson", form)
        self.assertIn("|tojson", listing)
        self.assertIn("tipo_mp_labels.get(mp.tipo, mp.tipo)", detail)

    def test_gettext_calls_do_not_contain_unsafe_literal_percent_signs(self):
        templates_dir = self.project_root / "app" / "templates" / "baches"
        gettext_call = re.compile(r'_\((["\'])(.*?)\1')

        for template in templates_dir.glob("*.html"):
            for match in gettext_call.finditer(template.read_text(encoding="utf-8")):
                message = match.group(2)
                unsafe = re.search(r"%(?!\(|%)", message)
                self.assertIsNone(
                    unsafe,
                    f"Unsafe percent sign in {template.name}: {message}",
                )

    def test_direct_flash_messages_use_gettext(self):
        route = self.project_root / "app" / "routes" / "baches.py"
        tree = ast.parse(route.read_text(encoding="utf-8"))

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if not isinstance(node.func, ast.Name) or node.func.id != "flash":
                continue
            self.assertTrue(node.args)
            message = node.args[0]
            if isinstance(message, ast.Call):
                self.assertIsInstance(message.func, ast.Name)
                self.assertEqual(message.func.id, "_")
            else:
                self.assertIsInstance(message, ast.Name)
                self.assertIn(message.id, {"error_mp", "error_stock", "error_med"})


if __name__ == "__main__":
    unittest.main()
