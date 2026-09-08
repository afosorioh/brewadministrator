import ast
import re
import unittest
from pathlib import Path

from flask import Flask, render_template_string
from flask_babel import Babel, gettext, pgettext


class TastingsInternationalizationTestCase(unittest.TestCase):
    def setUp(self):
        self.project_root = Path(__file__).resolve().parents[1]
        self.app = Flask(__name__, root_path=str(self.project_root / "app"))
        self.app.config["BABEL_TRANSLATION_DIRECTORIES"] = "translations"
        Babel(self.app, locale_selector=lambda: "en")

    def test_tasting_catalog_entries(self):
        with self.app.test_request_context():
            self.assertEqual(gettext("Sesiones de cata"), "Tasting sessions")
            self.assertEqual(gettext("Cata pública"), "Public tasting")
            self.assertEqual(gettext("Características de aroma"), "Aroma characteristics")
            self.assertEqual(gettext("Marrón"), "Brown")
            self.assertEqual(pgettext("sensory level", "Baja"), "Low")
            self.assertEqual(gettext("Baja"), "Decommissioned")
            self.assertEqual(
                gettext(
                    "El puntaje de %(dimension)s debe estar entre 1 y 5.",
                    dimension=gettext("Aroma"),
                ),
                "The Aroma rating must be between 1 and 5.",
            )

    def test_public_form_preserves_persisted_codes(self):
        form = (
            self.project_root / "app" / "templates" / "catas" / "publica_form.html"
        ).read_text(encoding="utf-8")

        for code in (
            "masculino",
            "femenino",
            "prefiero_no_indicar",
            "18_25",
            "66_mas",
            "colombiana",
            "extranjera",
            "citrico",
            "medicinal",
            "acido",
            "baja",
            "media",
            "alta",
            "bajo",
            "medio",
            "alto",
        ):
            self.assertRegex(form, rf'["\']{code}["\']')

        self.assertIn('value="masculino"', form)
        self.assertIn('value="18_25"', form)
        self.assertIn('value="colombiana"', form)
        self.assertIn('value="baja"', form)

    def test_statistics_translate_codes_at_presentation_layer(self):
        statistics = (
            self.project_root / "app" / "templates" / "catas" / "estadisticas.html"
        ).read_text(encoding="utf-8")

        self.assertIn("sexo_labels.get(item.label, item.label)", statistics)
        self.assertIn("edad_labels.get(item.label, item.label)", statistics)
        self.assertIn("nacionalidad_labels.get(item.label, item.label)", statistics)
        self.assertIn("color_labels.get(item.label, item.label)", statistics)
        self.assertIn("nivel_labels.get(item.label, item.label)", statistics)
        self.assertIn("descriptor_labels.get(item.label, item.label)", statistics)

    def test_inline_javascript_uses_json_serialized_translations(self):
        detail = (
            self.project_root / "app" / "templates" / "catas" / "detalle.html"
        ).read_text(encoding="utf-8")
        public_form = (
            self.project_root / "app" / "templates" / "catas" / "publica_form.html"
        ).read_text(encoding="utf-8")

        self.assertIn("const tastingI18n =", detail)
        self.assertIn("const colorLabels =", public_form)
        self.assertIn("}|tojson", detail)
        self.assertIn("}|tojson", public_form)
        self.assertNotIn('alert("Link copiado al portapapeles")', detail)
        self.assertNotIn('let texto = "Negro"', public_form)

    def test_validation_and_alert_messages_use_gettext(self):
        for filename in ("catas.py", "catas_publicas.py"):
            route = self.project_root / "app" / "routes" / filename
            tree = ast.parse(route.read_text(encoding="utf-8"))

            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                if not isinstance(node.func, ast.Attribute):
                    continue
                if node.func.attr != "append" or not node.args:
                    continue
                owner = node.func.value
                if not isinstance(owner, ast.Name):
                    continue
                if owner.id not in {"errores", "alertas"}:
                    continue
                message = node.args[0]
                self.assertIsInstance(message, ast.Call)
                self.assertIsInstance(message.func, ast.Name)
                self.assertEqual(message.func.id, "_")

    def test_flash_string_literals_are_wrapped_in_gettext(self):
        def assert_translated_literals(node, translated=False):
            if isinstance(node, ast.Call):
                is_gettext = isinstance(node.func, ast.Name) and node.func.id == "_"
                translated = translated or is_gettext
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                self.assertTrue(translated, f"Untranslated flash message: {node.value}")
            for child in ast.iter_child_nodes(node):
                assert_translated_literals(child, translated)

        for filename in ("catas.py", "catas_publicas.py"):
            route = self.project_root / "app" / "routes" / filename
            tree = ast.parse(route.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                if not isinstance(node.func, ast.Name) or node.func.id != "flash":
                    continue
                self.assertTrue(node.args)
                assert_translated_literals(node.args[0])

    def test_gettext_calls_do_not_contain_unsafe_literal_percent_signs(self):
        templates_dir = self.project_root / "app" / "templates" / "catas"
        gettext_call = re.compile(r'_\((["\'])(.*?)\1')

        for template in templates_dir.glob("*.html"):
            for match in gettext_call.finditer(template.read_text(encoding="utf-8")):
                message = match.group(2)
                unsafe = re.search(r"%(?!\(|%)", message)
                self.assertIsNone(
                    unsafe,
                    f"Unsafe percent sign in {template.name}: {message}",
                )

    def test_plural_messages_render_in_english(self):
        with self.app.test_request_context():
            rendered = render_template_string(
                "{{ ngettext('%(count)s mención', '%(count)s menciones', count, "
                "count=count) }}",
                count=2,
            )
            self.assertEqual(rendered, "2 mentions")


if __name__ == "__main__":
    unittest.main()
