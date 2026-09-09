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
from app.extensions import db
from app.models import MateriaPrima, Rol, Usuario


class RawMaterialSearchTestCase(unittest.TestCase):
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
                idioma_preferido="en",
            )
            user.set_password("test-password")
            db.session.add(user)

            db.session.add_all(
                [
                    MateriaPrima(nombre="Amarillo", tipo="LUPULO", unidad_base="G"),
                    MateriaPrima(
                        nombre="Amarillo Gold",
                        tipo="LUPULO",
                        unidad_base="G",
                    ),
                    MateriaPrima(nombre="Avena", tipo="MALTA", unidad_base="KG"),
                    MateriaPrima(
                        nombre="Amarillo Malt",
                        tipo="MALTA",
                        unidad_base="KG",
                    ),
                    MateriaPrima(nombre="100% Malt", tipo="MALTA", unidad_base="KG"),
                    MateriaPrima(nombre="100X Malt", tipo="MALTA", unidad_base="KG"),
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

    def test_search_starts_with_name_case_insensitively(self):
        response = self.client.get("/materias_primas/buscar?q=AMA")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Amarillo", response.data)
        self.assertIn(b"Amarillo Gold", response.data)
        self.assertNotIn(b"Avena", response.data)

    def test_more_characters_refine_results(self):
        response = self.client.get(
            "/materias_primas/buscar?q=Amarillo%20G"
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Amarillo Gold", response.data)
        self.assertNotIn(b">Amarillo<", response.data)

    def test_percent_and_underscore_are_literal_search_characters(self):
        response = self.client.get("/materias_primas/buscar?q=100%25")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"100% Malt", response.data)
        self.assertNotIn(b"100X Malt", response.data)

    def test_fewer_than_three_characters_do_not_run_search(self):
        response = self.client.get("/materias_primas/buscar?q=Am")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Enter at least 3 characters to search.", response.data)
        self.assertNotIn(b"Amarillo", response.data)

    def test_search_requires_authentication(self):
        anonymous_client = self.app.test_client()
        response = anonymous_client.get("/materias_primas/buscar?q=Ama")

        self.assertEqual(response.status_code, 302)
        self.assertIn("/auth/login", response.headers["Location"])

    def test_list_filters_by_selected_type(self):
        response = self.client.get("/materias_primas/?tipo=MALTA")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Avena", response.data)
        self.assertIn(b"Amarillo Malt", response.data)
        self.assertNotIn(b">Amarillo<", response.data)
        self.assertIn(b'value="MALTA" selected', response.data)

    def test_name_search_respects_selected_type(self):
        response = self.client.get(
            "/materias_primas/buscar?q=Ama&tipo=MALTA"
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Amarillo Malt", response.data)
        self.assertNotIn(b">Amarillo<", response.data)
        self.assertNotIn(b"Amarillo Gold", response.data)

    def test_invalid_type_does_not_filter_the_list(self):
        response = self.client.get("/materias_primas/?tipo=INVALIDO")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Avena", response.data)
        self.assertIn(b">Amarillo<", response.data)


if __name__ == "__main__":
    unittest.main()
