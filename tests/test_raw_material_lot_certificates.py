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
from app.models import LoteMateriaPrima, MateriaPrima, Rol, Usuario


PDF_CONTENT = b"%PDF-1.4\nquality certificate\n%%EOF"
PNG_CONTENT = b"\x89PNG\r\n\x1a\nquality certificate"


class RawMaterialLotCertificatesTestCase(unittest.TestCase):
    def setUp(self):
        self.uploads = tempfile.TemporaryDirectory()
        self.app = create_app()
        self.app.config["QUALITY_CERTIFICATES_FOLDER"] = self.uploads.name
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
            materia = MateriaPrima(
                nombre="Amarillo",
                tipo="LUPULO",
                unidad_base="G",
            )
            db.session.add_all([user, materia])
            db.session.commit()
            self.mp_id = materia.id

        self.client.post(
            "/auth/login",
            data={"username": "andres", "password": "test-password"},
        )

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
        self.uploads.cleanup()

    def _crear_lote(self, archivo=None):
        data = {
            "codigo_lote": "AMA-2026",
            "cantidad_inicial": "1000",
        }
        if archivo:
            data["certificado_calidad"] = archivo
        return self.client.post(
            f"/materias_primas/{self.mp_id}/lotes/nuevo",
            data=data,
            content_type="multipart/form-data",
        )

    def test_certificate_is_saved_and_downloaded_with_original_name(self):
        response = self._crear_lote(
            (io.BytesIO(PDF_CONTENT), "certificado calidad.pdf")
        )

        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            lote = LoteMateriaPrima.query.one()
            self.assertEqual(
                lote.certificado_calidad_nombre,
                "certificado_calidad.pdf",
            )
            self.assertRegex(
                lote.certificado_calidad_archivo,
                r"^[0-9a-f]{32}\.pdf$",
            )
            stored_name = lote.certificado_calidad_archivo
            lote_id = lote.id

        stored_path = Path(self.uploads.name) / stored_name
        self.assertEqual(stored_path.read_bytes(), PDF_CONTENT)

        download = self.client.get(
            f"/materias_primas/{self.mp_id}/lotes/{lote_id}/certificado"
        )
        self.assertEqual(download.status_code, 200)
        self.assertEqual(download.data, PDF_CONTENT)
        self.assertIn(
            "certificado_calidad.pdf",
            download.headers["Content-Disposition"],
        )
        download.close()

    def test_detail_shows_the_certificate_download(self):
        self._crear_lote((io.BytesIO(PDF_CONTENT), "calidad.pdf"))

        response = self.client.get(f"/materias_primas/{self.mp_id}")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Descargar", response.data)
        self.assertIn(b"/certificado", response.data)

    def test_replacing_certificate_removes_the_previous_file(self):
        self._crear_lote((io.BytesIO(PDF_CONTENT), "original.pdf"))
        with self.app.app_context():
            lote = LoteMateriaPrima.query.one()
            lote_id = lote.id
            previous_name = lote.certificado_calidad_archivo

        response = self.client.post(
            f"/materias_primas/{self.mp_id}/lotes/{lote_id}/editar",
            data={
                "codigo_lote": "AMA-2026",
                "cantidad_inicial": "",
                "certificado_calidad": (
                    io.BytesIO(PNG_CONTENT),
                    "reemplazo.png",
                ),
            },
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse((Path(self.uploads.name) / previous_name).exists())
        with self.app.app_context():
            lote = db.session.get(LoteMateriaPrima, lote_id)
            self.assertEqual(lote.certificado_calidad_nombre, "reemplazo.png")
            self.assertTrue(
                (Path(self.uploads.name) / lote.certificado_calidad_archivo).exists()
            )

    def test_edit_without_file_keeps_the_current_certificate(self):
        self._crear_lote((io.BytesIO(PDF_CONTENT), "original.pdf"))
        with self.app.app_context():
            lote = LoteMateriaPrima.query.one()
            lote_id = lote.id
            stored_name = lote.certificado_calidad_archivo

        response = self.client.post(
            f"/materias_primas/{self.mp_id}/lotes/{lote_id}/editar",
            data={"codigo_lote": "AMA-2026", "cantidad_inicial": ""},
        )

        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            lote = db.session.get(LoteMateriaPrima, lote_id)
            self.assertEqual(lote.certificado_calidad_archivo, stored_name)
        self.assertTrue((Path(self.uploads.name) / stored_name).exists())

    def test_deleting_lot_removes_its_certificate(self):
        self._crear_lote((io.BytesIO(PDF_CONTENT), "calidad.pdf"))
        with self.app.app_context():
            lote = LoteMateriaPrima.query.one()
            lote_id = lote.id
            stored_name = lote.certificado_calidad_archivo

        response = self.client.post(
            f"/materias_primas/{self.mp_id}/lotes/{lote_id}/eliminar"
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse((Path(self.uploads.name) / stored_name).exists())
        with self.app.app_context():
            self.assertIsNone(db.session.get(LoteMateriaPrima, lote_id))

    def test_invalid_extension_or_content_is_rejected(self):
        invalid_files = (
            (b"executable", "certificado.exe"),
            (b"<html>not a pdf</html>", "certificado.pdf"),
        )

        for content, filename in invalid_files:
            with self.subTest(filename=filename):
                response = self._crear_lote((io.BytesIO(content), filename))
                self.assertEqual(response.status_code, 302)

        with self.app.app_context():
            self.assertEqual(LoteMateriaPrima.query.count(), 0)
        self.assertEqual(list(Path(self.uploads.name).glob("*")), [])

    def test_oversized_certificate_is_rejected_and_removed(self):
        self.app.config["QUALITY_CERTIFICATE_MAX_BYTES"] = 12

        response = self._crear_lote(
            (io.BytesIO(PDF_CONTENT), "demasiado_grande.pdf")
        )

        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            self.assertEqual(LoteMateriaPrima.query.count(), 0)
        self.assertEqual(list(Path(self.uploads.name).glob("*")), [])

    def test_certificate_download_requires_login(self):
        self._crear_lote((io.BytesIO(PDF_CONTENT), "calidad.pdf"))
        with self.app.app_context():
            lote = LoteMateriaPrima.query.one()
            lote_id = lote.id

        anonymous = self.app.test_client()
        response = anonymous.get(
            f"/materias_primas/{self.mp_id}/lotes/{lote_id}/certificado"
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn("/auth/login", response.headers["Location"])

    def test_migration_adds_certificate_columns(self):
        migration = (
            Path(__file__).resolve().parents[1]
            / "migrations"
            / "versions"
            / "f6d7c8b9a012_agregar_certificado_calidad_a_lotes.py"
        ).read_text(encoding="utf-8")

        self.assertIn('down_revision = "a41f6e2b9c30"', migration)
        self.assertIn('"certificado_calidad_archivo"', migration)
        self.assertIn('"certificado_calidad_nombre"', migration)


if __name__ == "__main__":
    unittest.main()
