import sys
import types
import unittest
from datetime import date, datetime


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
from app.models import Bache, MedicionBache, Rol, Usuario


class BatchDetailChartTestCase(unittest.TestCase):
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

            batch = Bache(
                codigo_bache="BATCH-001",
                nombre_cerveza="IPA",
                fecha_coccion=date(2026, 9, 8),
                densidad_inicial=1.055,
            )
            db.session.add(batch)
            db.session.flush()

            db.session.add_all(
                [
                    MedicionBache(
                        id_bache=batch.id,
                        fecha=datetime(2026, 9, 9, 12, 0),
                        tipo="PH",
                        valor=4.5,
                    ),
                    MedicionBache(
                        id_bache=batch.id,
                        fecha=datetime(2026, 9, 10, 12, 0),
                        tipo="DENSIDAD",
                        valor=1.020,
                    ),
                    MedicionBache(
                        id_bache=batch.id,
                        fecha=datetime(2026, 9, 10, 12, 0),
                        tipo="TEMPERATURA",
                        valor=18.0,
                    ),
                ]
            )
            db.session.commit()
            self.batch_id = batch.id

        self.client.post(
            "/auth/login",
            data={"username": "andres", "password": "test-password"},
        )

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def test_detail_includes_the_measurements_chart(self):
        response = self.client.get(f"/baches/{self.batch_id}")
        html = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("Gráfica", html)
        self.assertIn(f'/baches/{self.batch_id}/grafica.png', html)
        self.assertNotIn('/estadisticas/bache', html)

    def test_chart_endpoint_returns_a_png(self):
        response = self.client.get(f"/baches/{self.batch_id}/grafica.png")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "image/png")
        self.assertTrue(response.data.startswith(b"\x89PNG\r\n\x1a\n"))

    def test_independent_statistics_module_is_removed(self):
        response = self.client.get("/estadisticas/bache")

        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
