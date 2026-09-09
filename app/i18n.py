from urllib.parse import urlsplit

from flask import Blueprint, abort, redirect, request, session, url_for
from flask_login import current_user

from app.extensions import db


SUPPORTED_LANGUAGES = ("es", "en")
LANGUAGE_LABELS = {
    "es": "Español",
    "en": "English",
}

locale_bp = Blueprint("locale", __name__)


def select_locale():
    """Select the interface language for the current request."""
    selected = session.get("language")
    if selected in SUPPORTED_LANGUAGES:
        return selected

    if current_user.is_authenticated:
        preferred = getattr(current_user, "idioma_preferido", None)
        if preferred in SUPPORTED_LANGUAGES:
            return preferred

    return request.accept_languages.best_match(
        SUPPORTED_LANGUAGES,
        default="es",
    )


def _is_safe_redirect(target):
    if not target:
        return False

    target_url = urlsplit(target)
    host_url = urlsplit(request.host_url)
    return (
        target_url.scheme in ("", "http", "https")
        and target_url.netloc in ("", host_url.netloc)
    )


@locale_bp.post("/language/<language>")
def change_language(language):
    if language not in SUPPORTED_LANGUAGES:
        abort(404)

    session["language"] = language

    if (
        current_user.is_authenticated
        and current_user.idioma_preferido != language
    ):
        current_user.idioma_preferido = language
        db.session.commit()

    next_page = request.form.get("next")
    if not _is_safe_redirect(next_page):
        next_page = url_for("index")

    return redirect(next_page)
