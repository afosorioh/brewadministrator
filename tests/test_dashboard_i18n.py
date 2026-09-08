import unittest
from datetime import date
from pathlib import Path

from flask import Flask, render_template_string
from flask_babel import Babel


class DashboardInternationalizationTestCase(unittest.TestCase):
    def test_flask_babel_dateformat_filter_renders_a_date(self):
        app = Flask(__name__)
        Babel(app)

        with app.test_request_context():
            rendered = render_template_string(
                "{{ value|dateformat('medium') }}",
                value=date(2026, 9, 7),
            )

        self.assertIn("2026", rendered)

    def test_dashboard_uses_the_registered_date_filter(self):
        project_root = Path(__file__).resolve().parents[1]
        template = (
            project_root / "app" / "templates" / "dashboard" / "inicio.html"
        ).read_text(encoding="utf-8")

        self.assertIn("today|dateformat('medium')", template)
        self.assertNotIn("format_date(today", template)


if __name__ == "__main__":
    unittest.main()
