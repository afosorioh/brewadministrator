import sys
import types
import unittest


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


class LanguageSelectionTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.client = self.app.test_client()

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


if __name__ == "__main__":
    unittest.main()
