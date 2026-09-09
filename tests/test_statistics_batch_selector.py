import sys
import types
import unittest
from datetime import date


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
from app.models import Bache, Receta, Rol, Usuario


class StatisticsBatchSelectorTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.client = self.app.test_client()

        with self.app.app_context():
            db.create_all()
            role = Rol(nombre="ADMIN")
            db.session.add(role)
            db.session.flush()

            user = Usuario(
                username="andres",
                id_rol=role.id,
                activo=True,
                idioma_preferido="es",
            )
            user.set_password("test-password")
            db.session.add(user)

            ipa = Receta(nombre="IPA", estilo="American IPA")
            db.session.add(ipa)
            db.session.flush()

            db.session.add_all(
                [
                    Bache(
                        codigo_bache="BATCH-003",
                        nombre_cerveza="IPA",
                        id_receta=ipa.id,
                        fecha_coccion=date(2026, 9, 8),
                    ),
                    Bache(
                        codigo_bache="BATCH-002",
                        nombre_cerveza="Experimental",
                        fecha_coccion=date(2026, 8, 17),
                    ),
                    Bache(
                        codigo_bache="BATCH-001",
                        nombre_cerveza="IPA",
                        id_receta=ipa.id,
                        fecha_coccion=date(2026, 7, 2),
                    ),
                ]
            )
            db.session.commit()

        self.client.post(
            "/auth/login",
            data={"username": "andres", "password": "test-password"},
        )

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def test_selector_lists_batches_with_style_and_formatted_date(self):
        response = self.client.get("/estadisticas/bache")
        html = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("BATCH-003 (American IPA-08/09/2026)", html)
        self.assertIn("BATCH-002 (Sin estilo-17/08/2026)", html)
        self.assertLess(html.index("BATCH-003 ("), html.index("BATCH-002 ("))
        self.assertLess(html.index("BATCH-002 ("), html.index("BATCH-001 ("))

    def test_selector_url_opens_the_selected_batch(self):
        response = self.client.get(
            "/estadisticas/bache?codigo_bache=BATCH-003"
        )
        html = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("BATCH-003 – IPA", html)
        self.assertIn("selected", html)


if __name__ == "__main__":
    unittest.main()
