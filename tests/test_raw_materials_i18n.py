import ast
import unittest
from pathlib import Path

from flask import Flask, render_template_string
from flask_babel import Babel, gettext


class RawMaterialsInternationalizationTestCase(unittest.TestCase):
    def setUp(self):
        self.project_root = Path(__file__).resolve().parents[1]
        self.app = Flask(__name__, root_path=str(self.project_root / "app"))
        self.app.config["BABEL_TRANSLATION_DIRECTORIES"] = "translations"
        Babel(self.app, locale_selector=lambda: "en")

    def test_raw_material_catalog_entries(self):
        with self.app.test_request_context():
            self.assertEqual(gettext("Materias primas"), "Raw materials")
            self.assertEqual(gettext("Nueva materia prima"), "New raw material")
            self.assertEqual(gettext("Detalles de levadura"), "Yeast details")
            self.assertEqual(gettext("Floculación baja"), "Low")
            self.assertEqual(gettext("Lotes de esta materia prima"), "Lots for this raw material")
            self.assertEqual(gettext("La cantidad debe ser mayor que cero."), "The quantity must be greater than zero.")

    def test_internal_codes_and_safe_confirmations_are_preserved(self):
        materials_dir = self.project_root / "app" / "templates" / "materias_primas"
        form = (materials_dir / "formulario.html").read_text(encoding="utf-8")
        listing = (materials_dir / "lista.html").read_text(encoding="utf-8")
        detail = (materials_dir / "detalle.html").read_text(encoding="utf-8")

        for code in ("MALTA", "LUPULO", "LEVADURA", "OTRO"):
            self.assertIn(f'"{code}"', form)
        self.assertIn('<option value="{{ t }}"', form)
        self.assertIn('<option value="{{ val }}"', form)
        self.assertIn('|tojson', listing)
        self.assertIn('|tojson', detail)

    def test_percent_labels_render_in_english(self):
        labels = {
            "Atenuación mínima (%%)": "Minimum attenuation (%)",
            "Atenuación máxima (%%)": "Maximum attenuation (%)",
            "Alfa ácidos (%%)": "Alpha acids (%)",
            "Beta ácidos (%%)": "Beta acids (%)",
            "Cohumulona (%%)": "Cohumulone (%)",
            "Proteínas (%%)": "Protein (%)",
            "Uso máximo recomendado en molienda (%%)": (
                "Maximum recommended use in the grain bill (%)"
            ),
        }

        with self.app.test_request_context():
            for message, expected in labels.items():
                with self.subTest(message=message):
                    rendered = render_template_string(
                        '{{ _(message) }}',
                        message=message,
                    )
                    self.assertEqual(rendered, expected)

    def test_every_flash_message_uses_gettext(self):
        route = self.project_root / "app" / "routes" / "materias_primas.py"
        tree = ast.parse(route.read_text(encoding="utf-8"))

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if not isinstance(node.func, ast.Name) or node.func.id != "flash":
                continue
            self.assertTrue(node.args, "flash() must include a message")
            message = node.args[0]
            self.assertIsInstance(message, ast.Call)
            self.assertIsInstance(message.func, ast.Name)
            self.assertEqual(message.func.id, "_")


if __name__ == "__main__":
    unittest.main()
