import unittest
from pathlib import Path

from flask import Flask
from flask_babel import Babel, gettext


class CoreModulesInternationalizationTestCase(unittest.TestCase):
    def setUp(self):
        project_root = Path(__file__).resolve().parents[1]
        self.app = Flask(__name__, root_path=str(project_root / "app"))
        self.app.config["BABEL_TRANSLATION_DIRECTORIES"] = "translations"
        Babel(self.app, locale_selector=lambda: "en")

    def test_user_customer_and_recipe_catalog_entries(self):
        with self.app.test_request_context():
            self.assertEqual(gettext("Nuevo usuario"), "New user")
            self.assertEqual(gettext("Nuevo cliente"), "New customer")
            self.assertEqual(gettext("Nueva receta"), "New recipe")
            self.assertEqual(gettext("Taproom interno"), "In-house taproom")
            self.assertEqual(gettext("Gestor"), "Manager")

    def test_internal_codes_are_not_replaced_in_templates(self):
        project_root = Path(__file__).resolve().parents[1]
        customer_form = (
            project_root / "app" / "templates" / "clientes" / "formulario.html"
        ).read_text(encoding="utf-8")
        user_form = (
            project_root / "app" / "templates" / "usuarios" / "formulario.html"
        ).read_text(encoding="utf-8")

        self.assertIn('<option value="{{ t }}"', customer_form)
        self.assertIn('<option value="{{ r.id }}"', user_form)


if __name__ == "__main__":
    unittest.main()
