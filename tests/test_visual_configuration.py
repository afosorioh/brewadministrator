import base64
import io
import sys
import tempfile
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
from app.models import ConfiguracionVisual, Rol, Usuario

PNG_TEST_IMAGE = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAYAAABytg0kAAAAFElEQVR4nGMMMZD6"
    "z8DAwMDEAAUAGEIBoRXrN/8AAAAASUVORK5CYII="
)


class VisualConfigurationTestCase(unittest.TestCase):
    def setUp(self):
        self.uploads = tempfile.TemporaryDirectory()
        self.app = create_app()
        self.app.config["BRANDING_FOLDER"] = self.uploads.name
        self.client = self.app.test_client()
        with self.app.app_context():
            db.create_all()
            admin_role = Rol(nombre="ADMIN")
            gestor_role = Rol(nombre="GESTOR")
            db.session.add_all([admin_role, gestor_role])
            db.session.flush()
            admin = Usuario(username="admin", id_rol=admin_role.id, activo=True, idioma_preferido="es")
            gestor = Usuario(username="gestor", id_rol=gestor_role.id, activo=True, idioma_preferido="es")
            admin.set_password("test-password")
            gestor.set_password("test-password")
            db.session.add_all([admin, gestor])
            db.session.commit()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
        self.uploads.cleanup()

    def login(self, username="admin"):
        return self.client.post("/auth/login", data={"username": username, "password": "test-password"})

    def valid_form(self, **overrides):
        values = {
            "nombre_aplicacion": "Cervecería", "nombre_corto": "Cervecería", "lema": "",
            "color_primario": "#54301A", "color_primario_oscuro": "#3E2313",
            "color_acento": "#E9DED3", "color_fondo": "#F3EEE7",
            "color_superficie": "#FFFFFF", "color_encabezado": "#EFE5DA",
            "color_texto": "#24150C", "color_texto_nav": "#F7F1EA",
            "color_borde": "#D8C8B8", "fuente_cuerpo": "system",
            "fuente_titulos": "system", "action": "save",
        }
        values.update(overrides)
        return values

    def test_defaults_match_existing_theme_and_hide_absent_images(self):
        self.login()
        html = self.client.get("/configuracion-visual/").get_data(as_text=True)
        self.assertIn("#54301A", html)
        self.assertIn("#3E2313", html)
        self.assertIn("#F3EEE7", html)
        self.assertNotIn("branding-current-image", html)
        login = self.app.test_client().get("/auth/login").get_data(as_text=True)
        self.assertNotIn("login-brand-logo", login)
        self.assertNotIn('rel="icon"', login)

    def test_only_admin_can_manage_global_theme(self):
        self.assertEqual(self.app.test_client().get("/configuracion-visual/").status_code, 302)
        self.login("gestor")
        self.assertEqual(self.client.get("/configuracion-visual/").status_code, 403)
        self.assertEqual(self.client.post("/configuracion-visual/", data=self.valid_form()).status_code, 403)

    def test_admin_updates_global_identity_colors_and_fonts(self):
        self.login()
        response = self.client.post("/configuracion-visual/", data=self.valid_form(
            nombre_aplicacion="Cervecería Libre", nombre_corto="Libre",
            lema="Tómate la libertad de probarla", color_primario="#112233",
            fuente_cuerpo="inter", fuente_titulos="montserrat",
        ))
        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            configuration = db.session.get(ConfiguracionVisual, 1)
            self.assertEqual(configuration.nombre_corto, "Libre")
            self.assertEqual(configuration.color_primario, "#112233")
            self.assertEqual(configuration.fuente_titulos, "montserrat")
        login = self.app.test_client().get("/auth/login").get_data(as_text=True)
        self.assertIn("Cervecería Libre", login)
        self.assertIn("Tómate la libertad de probarla", login)
        self.assertIn("--brand-primary: #112233", login)

    def test_invalid_color_is_rejected(self):
        self.login()
        response = self.client.post("/configuracion-visual/", data=self.valid_form(
            color_primario="red; body{display:none}"
        ), follow_redirects=True)
        self.assertIn("El color debe tener el formato hexadecimal #RRGGBB.", response.get_data(as_text=True))
        with self.app.app_context():
            self.assertEqual(db.session.get(ConfiguracionVisual, 1).color_primario, "#54301A")

    def test_logo_is_served_and_can_be_removed(self):
        self.login()
        data = self.valid_form()
        data["logo"] = (io.BytesIO(PNG_TEST_IMAGE), "logo.png")
        self.assertEqual(self.client.post(
            "/configuracion-visual/", data=data, content_type="multipart/form-data"
        ).status_code, 302)
        with self.app.app_context():
            filename = db.session.get(ConfiguracionVisual, 1).logo_archivo
            self.assertRegex(filename, r"^logo-[0-9a-f]{32}\.png$")
        self.assertTrue((Path(self.uploads.name) / filename).exists())
        public_logo = self.app.test_client().get("/configuracion-visual/archivo/logo")
        self.assertEqual(public_logo.status_code, 200)
        public_logo.close()
        self.client.post("/configuracion-visual/", data=self.valid_form(eliminar_logo_archivo="on"))
        self.assertFalse((Path(self.uploads.name) / filename).exists())

    def test_restore_recovers_original_values_and_deletes_images(self):
        self.login()
        data = self.valid_form(nombre_corto="Libre", color_primario="#112233")
        data["logo"] = (io.BytesIO(PNG_TEST_IMAGE), "logo.png")
        self.client.post("/configuracion-visual/", data=data, content_type="multipart/form-data")
        with self.app.app_context():
            filename = db.session.get(ConfiguracionVisual, 1).logo_archivo
        self.client.post("/configuracion-visual/", data={"action": "restore"})
        with self.app.app_context():
            configuration = db.session.get(ConfiguracionVisual, 1)
            self.assertEqual(configuration.nombre_corto, "Cervecería")
            self.assertEqual(configuration.color_primario, "#54301A")
            self.assertIsNone(configuration.logo_archivo)
        self.assertFalse((Path(self.uploads.name) / filename).exists())

    def test_module_renders_in_english(self):
        self.login()
        self.client.post("/language/en", data={"next": "/configuracion-visual/"})
        html = self.client.get("/configuracion-visual/").get_data(as_text=True)
        self.assertIn("Visual settings", html)
        self.assertIn("These changes are global and affect all users.", html)
        self.assertIn("System / Bootstrap", html)

    def test_migration_seeds_one_global_configuration(self):
        migration = (Path(__file__).resolve().parents[1] / "migrations" / "versions" /
                     "c8a4f1d2e6b0_configuracion_visual_global.py").read_text(encoding="utf-8")
        self.assertIn('down_revision = "f6d7c8b9a012"', migration)
        self.assertIn('"id_configuracion": 1', migration)
        self.assertIn('"color_primario": "#54301A"', migration)


if __name__ == "__main__":
    unittest.main()
