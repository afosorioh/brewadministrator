import sys
import types
import unittest
from pathlib import Path


if "config" not in sys.modules:
    config_module = types.ModuleType("config")

    class TestConfig:
        SECRET_KEY = "test-secret-key"
        SQLALCHEMY_DATABASE_URI = "sqlite://"
        SQLALCHEMY_TRACK_MODIFICATIONS = False
        TESTING = True
        TIMEZONE = "America/Bogota"

    config_module.Config = TestConfig
    sys.modules["config"] = config_module

from app import create_app
from app.extensions import db
from app.models import Rol, Usuario


class LanguageSelectionTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.client = self.app.test_client()

        with self.app.app_context():
            db.create_all()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def create_user(self, language="es"):
        with self.app.app_context():
            role = Rol(nombre="ADMIN")
            db.session.add(role)
            db.session.flush()
            user = Usuario(
                username="andres",
                id_rol=role.id,
                activo=True,
                idioma_preferido=language,
            )
            user.set_password("test-password")
            db.session.add(user)
            db.session.commit()

    def test_spanish_is_the_default_language(self):
        response = self.client.get("/auth/login")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'<html lang="es">', response.data)
        self.assertIn("Iniciar sesión".encode(), response.data)

    def test_user_can_change_language_to_english(self):
        response = self.client.post(
            "/language/en",
            data={"next": "/auth/login"},
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'<html lang="en">', response.data)
        self.assertIn(b"Sign in", response.data)
        self.assertIn(b"Password", response.data)

    def test_language_is_kept_in_the_session(self):
        self.client.post("/language/en", data={"next": "/auth/login"})
        response = self.client.get("/auth/login")

        self.assertIn(b'<html lang="en">', response.data)

    def test_unsupported_language_returns_not_found(self):
        response = self.client.post(
            "/language/fr",
            data={"next": "/auth/login"},
        )

        self.assertEqual(response.status_code, 404)

    def test_external_redirect_is_rejected(self):
        response = self.client.post(
            "/language/en",
            data={"next": "https://example.com/steal-session"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/")

    def test_authenticated_language_change_is_saved_in_database(self):
        self.create_user()
        self.client.post(
            "/auth/login",
            data={"username": "andres", "password": "test-password"},
        )

        response = self.client.post(
            "/language/en",
            data={"next": "/dashboard/"},
        )

        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            user = Usuario.query.filter_by(username="andres").one()
            self.assertEqual(user.idioma_preferido, "en")

    def test_login_restores_language_from_database(self):
        self.create_user(language="en")

        response = self.client.post(
            "/auth/login",
            data={"username": "andres", "password": "test-password"},
        )

        self.assertEqual(response.status_code, 302)
        with self.client.session_transaction() as browser_session:
            self.assertEqual(browser_session["language"], "en")

    def test_anonymous_language_change_remains_session_only(self):
        self.create_user()

        self.client.post("/language/en", data={"next": "/auth/login"})

        with self.app.app_context():
            user = Usuario.query.filter_by(username="andres").one()
            self.assertEqual(user.idioma_preferido, "es")

    def test_language_migration_defaults_existing_users_to_spanish(self):
        project_root = Path(__file__).resolve().parents[1]
        migration = (
            project_root
            / "migrations"
            / "versions"
            / "a41f6e2b9c30_persistir_idioma_preferido_usuario.py"
        ).read_text(encoding="utf-8")

        self.assertIn('down_revision = "b31d87f49a20"', migration)
        self.assertIn('server_default="es"', migration)
        self.assertIn("idioma_preferido IN ('es', 'en')", migration)


if __name__ == "__main__":
    unittest.main()
