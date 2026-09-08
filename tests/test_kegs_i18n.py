import ast
import re
import unittest
from pathlib import Path

from flask import Flask, render_template_string
from flask_babel import Babel, gettext


class KegsInternationalizationTestCase(unittest.TestCase):
    def setUp(self):
        self.project_root = Path(__file__).resolve().parents[1]
        self.app = Flask(__name__, root_path=str(self.project_root / "app"))
        self.app.config["BABEL_TRANSLATION_DIRECTORIES"] = "translations"
        Babel(self.app, locale_selector=lambda: "en")

    def test_keg_catalog_entries(self):
        with self.app.test_request_context():
            self.assertEqual(gettext("Barriles"), "Kegs")
            self.assertEqual(
                gettext("Alta individual de barril"),
                "Individual keg registration",
            )
            self.assertEqual(gettext("Llenado de barriles"), "Keg filling")
            self.assertEqual(gettext("Consultas de barriles"), "Keg reports")
            self.assertEqual(
                gettext(
                    "Barril %(keg_code)s dado de baja correctamente.",
                    keg_code="A001",
                ),
                "Keg A001 decommissioned successfully.",
            )

    def test_internal_codes_are_preserved(self):
        templates_dir = self.project_root / "app" / "templates" / "barriles"
        combined = "\n".join(
            template.read_text(encoding="utf-8")
            for template in templates_dir.glob("*.html")
        )

        for code in (
            "LIMPIO",
            "LLENO",
            "ENTREGADO",
            "SUCIO",
            "MANTENIMIENTO",
            "BAJA",
            "CLIENTE",
            "LATAS",
        ):
            self.assertIn(f'"{code}"', combined)

        self.assertIn('<option value="{{ e }}"', combined)
        self.assertIn('<option value="CLIENTE">', combined)
        self.assertIn('<option value="LATAS">', combined)

    def test_qr_reader_uses_safe_translated_messages(self):
        base = (
            self.project_root / "app" / "templates" / "base.html"
        ).read_text(encoding="utf-8")
        qr_script = (
            self.project_root / "app" / "static" / "js" / "barriles_qr.js"
        ).read_text(encoding="utf-8")

        self.assertIn("window.brewTranslations", base)
        for key in (
            "codeRead",
            "qrModalNotFound",
            "kegNotFound",
            "noCamera",
            "cameraStartError",
            "cameraAccessError",
        ):
            self.assertIn(f"{key}:", base)
            self.assertIn(f'textoInterfaz("{key}"', qr_script)

        self.assertIn("}|tojson", base)
        self.assertIn("text.split(token).join(String(value))", qr_script)
        self.assertNotRegex(qr_script, r'alert\(["\']')

    def test_gettext_calls_do_not_contain_unsafe_literal_percent_signs(self):
        templates_dir = self.project_root / "app" / "templates" / "barriles"
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
        route = self.project_root / "app" / "routes" / "barriles.py"
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

    def test_plural_messages_render_in_english(self):
        with self.app.test_request_context():
            rendered = render_template_string(
                "{{ ngettext('%(count)s día', '%(count)s días', count, "
                "count=count) }}",
                count=2,
            )
            self.assertEqual(rendered, "2 days")


if __name__ == "__main__":
    unittest.main()
