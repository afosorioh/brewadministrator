import sys
import types
import unittest
from datetime import datetime
from decimal import Decimal


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
from app.models import (
    Bache,
    ControladorTemperatura,
    LecturaTemperatura,
    Receta,
    Rol,
    Usuario,
)


class TemperatureHistoryBatchFilterTestCase(unittest.TestCase):
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

            ipa = Receta(nombre="IPA", estilo="American IPA")
            lager = Receta(nombre="Lager", estilo="Helles")
            db.session.add_all([user, ipa, lager])
            db.session.flush()

            batch_3 = Bache(
                codigo_bache="BATCH-003",
                nombre_cerveza="IPA",
                id_receta=ipa.id,
                fecha_coccion=datetime(2026, 9, 3).date(),
            )
            batch_2 = Bache(
                codigo_bache="BATCH-002",
                nombre_cerveza="Experimental",
                fecha_coccion=datetime(2026, 8, 2).date(),
            )
            unrelated_batch = Bache(
                codigo_bache="BATCH-004",
                nombre_cerveza="Lager",
                id_receta=lager.id,
                fecha_coccion=datetime(2026, 9, 4).date(),
            )
            db.session.add_all([batch_3, batch_2, unrelated_batch])
            db.session.flush()

            controller = ControladorTemperatura(
                codigo="fermentador-1",
                nombre="Fermentador 1",
                gateway_id="brewery-main-rpi",
                device_id=5,
                protocolo="sitrad",
                setpoint_min_c=Decimal("-10.0"),
                setpoint_max_c=Decimal("30.0"),
                activo=True,
            )
            other_controller = ControladorTemperatura(
                codigo="fermentador-2",
                nombre="Fermentador 2",
                gateway_id="brewery-main-rpi",
                device_id=6,
                protocolo="sitrad",
                setpoint_min_c=Decimal("-10.0"),
                setpoint_max_c=Decimal("30.0"),
                activo=True,
            )
            db.session.add_all([controller, other_controller])
            db.session.flush()

            db.session.add_all(
                [
                    self._reading(
                        "reading-003",
                        controller.id,
                        batch_3.id,
                        datetime(2026, 9, 9, 12, 0),
                        "12.3",
                    ),
                    self._reading(
                        "reading-002",
                        controller.id,
                        batch_2.id,
                        datetime(2026, 8, 9, 12, 0),
                        "18.7",
                    ),
                    self._reading(
                        "reading-other",
                        other_controller.id,
                        unrelated_batch.id,
                        datetime(2026, 9, 10, 12, 0),
                        "4.2",
                    ),
                ]
            )
            db.session.commit()

            self.controller_id = controller.id
            self.batch_3_id = batch_3.id
            self.unrelated_batch_id = unrelated_batch.id

        self.client.post(
            "/auth/login",
            data={"username": "andres", "password": "test-password"},
        )

    @staticmethod
    def _reading(reading_id, controller_id, batch_id, observed_at, temperature):
        return LecturaTemperatura(
            reading_id=reading_id,
            id_controlador=controller_id,
            id_bache=batch_id,
            observado_en=observed_at,
            temperatura_c=Decimal(temperature),
            setpoint_c=Decimal("14.0"),
            salida_activa=False,
            error_sensor=False,
        )

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def test_selector_lists_only_batches_linked_to_controller_readings(self):
        response = self.client.get(f"/temperatura/{self.controller_id}")
        html = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("BATCH-003 - American IPA", html)
        self.assertIn("BATCH-002 - Sin estilo", html)
        self.assertNotIn("BATCH-004 - Helles", html)
        self.assertLess(
            html.index("BATCH-003 - American IPA"),
            html.index("BATCH-002 - Sin estilo"),
        )

    def test_selected_batch_filters_chart_and_readings_table(self):
        response = self.client.get(
            f"/temperatura/{self.controller_id}?bache_id={self.batch_3_id}"
        )
        html = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn('value="{}"\n                selected'.format(self.batch_3_id), html)
        self.assertIn("12.3", html)
        self.assertNotIn("18.7", html)
        self.assertIn("Fecha y hora", html)

    def test_batch_from_another_controller_is_rejected(self):
        response = self.client.get(
            f"/temperatura/{self.controller_id}"
            f"?bache_id={self.unrelated_batch_id}",
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            b"El bache seleccionado no tiene lecturas para este controlador.",
            response.data,
        )

    def test_history_requires_authentication(self):
        anonymous = self.app.test_client()
        response = anonymous.get(f"/temperatura/{self.controller_id}")

        self.assertEqual(response.status_code, 302)
        self.assertIn("/auth/login", response.headers["Location"])


if __name__ == "__main__":
    unittest.main()
