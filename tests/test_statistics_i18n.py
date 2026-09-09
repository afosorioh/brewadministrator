import ast
import unittest
from pathlib import Path

from flask import Flask
from flask_babel import Babel, gettext


class StatisticsInternationalizationTestCase(unittest.TestCase):
    def setUp(self):
        self.project_root = Path(__file__).resolve().parents[1]
        self.route_path = (
            self.project_root / "app" / "routes" / "estadisticas.py"
        )
        self.template_path = (
            self.project_root
            / "app"
            / "templates"
            / "estadisticas"
            / "bache.html"
        )
        self.app = Flask(__name__, root_path=str(self.project_root / "app"))
        self.app.config["BABEL_TRANSLATION_DIRECTORIES"] = "translations"
        Babel(self.app, locale_selector=lambda: "en")

    def test_statistics_catalog_entries(self):
        with self.app.test_request_context():
            self.assertEqual(
                gettext("Estadísticas por bache"),
                "Batch statistics",
            )
            self.assertEqual(gettext("Atenuación"), "Attenuation")
            self.assertEqual(gettext("Gráfica"), "Chart")
            self.assertEqual(gettext("Seleccionar bache"), "Select batch")
            self.assertEqual(gettext("Sin estilo"), "No style")
            self.assertEqual(
                gettext("No se encontró el bache."),
                "The batch was not found.",
            )
            self.assertEqual(
                gettext(
                    "Fecha y hora (%(timezone)s)",
                    timezone="America/Bogota",
                ),
                "Date and time (America/Bogota)",
            )

    def test_server_messages_and_chart_labels_use_gettext(self):
        tree = ast.parse(self.route_path.read_text(encoding="utf-8"))
        expected = {
            "No se encontró el bache.",
            "Densidad (SG)",
            "Temperatura (°C)",
            "Fecha y hora (%(timezone)s)",
        }
        translated = set()

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if not isinstance(node.func, ast.Name) or node.func.id != "_":
                continue
            if node.args and isinstance(node.args[0], ast.Constant):
                translated.add(node.args[0].value)

        self.assertTrue(expected.issubset(translated))

    def test_measurement_codes_are_preserved(self):
        route = self.route_path.read_text(encoding="utf-8")
        for code in ("PH", "TEMPERATURA", "DENSIDAD"):
            self.assertIn(f'"{code}"', route)
            self.assertNotIn(f'_({code!r})', route)

    def test_batch_statuses_are_translated_only_for_display(self):
        template = self.template_path.read_text(encoding="utf-8")
        for code in (
            "PLANIFICADO",
            "EN_CURSO",
            "FERMENTANDO",
            "MADURANDO",
            "LISTO",
            "COMPLETADO",
            "DESCARTADO",
        ):
            self.assertIn(f'"{code}"', template)
        self.assertIn(
            "batch_status_labels.get(bache.estado, bache.estado)",
            template,
        )

    def test_statistics_template_uses_gettext_for_visible_labels(self):
        template = self.template_path.read_text(encoding="utf-8")
        for message in (
            "Estadísticas por bache",
            "Código de bache",
            "Seleccionar bache",
            "Seleccione un bache",
            "Sin estilo",
            "Buscar",
            "Fecha cocción",
            "Estado",
            "Indicadores",
            "Atenuación",
            "Últimas mediciones",
            "Densidad",
            "Temperatura",
            "Gráfica",
            "Gráfica de mediciones del bache",
        ):
            self.assertIn(f"_('{message}')", template)

    def test_batch_selector_format_and_navigation(self):
        template = self.template_path.read_text(encoding="utf-8")

        self.assertIn("for item in baches", template)
        self.assertIn("item.receta.estilo", template)
        self.assertIn("item.fecha_coccion.strftime('%d/%m/%Y')", template)
        self.assertIn("codigo_bache=item.codigo_bache", template)
        self.assertIn("window.location.href = this.value", template)

    def test_batches_are_loaded_in_descending_code_order(self):
        route = self.route_path.read_text(encoding="utf-8")

        self.assertIn("joinedload(Bache.receta)", route)
        self.assertIn("order_by(Bache.codigo_bache.desc())", route)


if __name__ == "__main__":
    unittest.main()
