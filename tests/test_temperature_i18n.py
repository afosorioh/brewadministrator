import ast
import re
import unittest
from pathlib import Path

from flask import Flask, render_template_string
from flask_babel import Babel, gettext


class TemperatureInternationalizationTestCase(unittest.TestCase):
    def setUp(self):
        self.project_root = Path(__file__).resolve().parents[1]
        self.app = Flask(__name__, root_path=str(self.project_root / "app"))
        self.app.config["BABEL_TRANSLATION_DIRECTORIES"] = "translations"
        Babel(self.app, locale_selector=lambda: "en")

    def test_temperature_catalog_entries(self):
        with self.app.test_request_context():
            self.assertEqual(
                gettext("Monitoreo de temperatura"),
                "Temperature monitoring",
            )
            self.assertEqual(gettext("Nuevo controlador"), "New controller")
            self.assertEqual(gettext("Refrigeración activa"), "Cooling active")
            self.assertEqual(gettext("Fallido"), "Failed")
            self.assertEqual(
                gettext("Filtrar historial por bache"),
                "Filter history by batch",
            )
            self.assertEqual(gettext("Todos los baches"), "All batches")
            self.assertEqual(gettext("Fecha y hora"), "Date and time")
            self.assertEqual(
                gettext(
                    "Por seguridad, cada comando puede cambiar como máximo "
                    "%(delta)s °C.",
                    delta="5.0",
                ),
                "For safety, each command can change the setpoint by at most 5.0 °C.",
            )

    def test_internal_protocol_and_command_codes_are_preserved(self):
        route = (
            self.project_root / "app" / "routes" / "temperatura.py"
        ).read_text(encoding="utf-8")
        templates_dir = self.project_root / "app" / "templates" / "temperatura"
        combined = "\n".join(
            template.read_text(encoding="utf-8")
            for template in templates_dir.glob("*.html")
        )

        for code in (
            "sitrad",
            "modbus",
            "pending",
            "delivered",
            "completed",
            "failed",
            "set_setpoint",
        ):
            self.assertIn(f'"{code}"', route + combined)

        self.assertIn('value="sitrad"', combined)
        self.assertIn('value="modbus"', combined)
        self.assertIn("command_status_labels.get(command.estado, command.estado)", combined)

    def test_batch_status_codes_are_translated_only_for_display(self):
        form = (
            self.project_root
            / "app"
            / "templates"
            / "temperatura"
            / "formulario.html"
        ).read_text(encoding="utf-8")

        for code in (
            "PLANIFICADO",
            "EN_CURSO",
            "FERMENTANDO",
            "MADURANDO",
            "LISTO",
            "COMPLETADO",
            "DESCARTADO",
        ):
            self.assertIn(f'"{code}"', form)
        self.assertIn("batch_status_labels.get(batch.estado, batch.estado)", form)

    def test_chart_and_confirmation_translations_are_json_serialized(self):
        templates_dir = self.project_root / "app" / "templates" / "temperatura"
        detail = (templates_dir / "detalle.html").read_text(encoding="utf-8")
        form = (templates_dir / "formulario.html").read_text(encoding="utf-8")

        self.assertIn("_('Temperatura °C')|tojson", detail)
        self.assertIn("_('Setpoint °C')|tojson", detail)
        self.assertIn("_('Fecha y hora')|tojson", detail)
        self.assertIn("_('Temperatura (°C)')|tojson", detail)
        self.assertIn("|tojson", form)
        self.assertNotIn("confirm('¿Eliminar", form)
        self.assertIn("autoSkip: true", detail)
        self.assertIn("maxTicksLimit: 12", detail)
        self.assertNotIn("tickLabels", detail)

    def test_validation_messages_and_direct_flashes_use_gettext(self):
        route = self.project_root / "app" / "routes" / "temperatura.py"
        tree = ast.parse(route.read_text(encoding="utf-8"))

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not node.args:
                continue
            if isinstance(node.func, ast.Name) and node.func.id == "ValueError":
                message = node.args[0]
                self.assertIsInstance(message, ast.Call)
                self.assertIsInstance(message.func, ast.Name)
                self.assertEqual(message.func.id, "_")
            if isinstance(node.func, ast.Name) and node.func.id == "flash":
                message = node.args[0]
                self.assertIsInstance(message, ast.Call)
                self.assertIsInstance(message.func, ast.Name)
                self.assertIn(message.func.id, {"_", "str"})

    def test_gettext_calls_do_not_contain_unsafe_literal_percent_signs(self):
        templates_dir = self.project_root / "app" / "templates" / "temperatura"
        gettext_call = re.compile(r'_\((["\'])(.*?)\1')

        for template in templates_dir.glob("*.html"):
            for match in gettext_call.finditer(template.read_text(encoding="utf-8")):
                message = match.group(2)
                unsafe = re.search(r"%(?!\(|%)", message)
                self.assertIsNone(
                    unsafe,
                    f"Unsafe percent sign in {template.name}: {message}",
                )

    def test_plural_messages_render_in_english(self):
        with self.app.test_request_context():
            rendered = render_template_string(
                "{{ ngettext('%(count)s segundo', '%(count)s segundos', count, "
                "count=count) }}",
                count=2,
            )
            self.assertEqual(rendered, "2 seconds")

    def test_history_batch_filter_preserves_display_only_labels(self):
        route = (
            self.project_root / "app" / "routes" / "temperatura.py"
        ).read_text(encoding="utf-8")
        detail = (
            self.project_root
            / "app"
            / "templates"
            / "temperatura"
            / "detalle.html"
        ).read_text(encoding="utf-8")

        self.assertIn("_batches_with_readings", route)
        self.assertIn("LecturaTemperatura.id_controlador == controller_id", route)
        self.assertIn("readings_query.filter_by(id_bache=selected_batch.id)", route)
        self.assertIn('name="bache_id"', detail)
        self.assertIn("batch.codigo_bache }} - {{ batch_style", detail)
        self.assertIn('onchange="this.form.submit()"', detail)


if __name__ == "__main__":
    unittest.main()
