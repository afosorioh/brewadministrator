import re
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from flask import current_app
from flask_babel import gettext as _
from PIL import Image, UnidentifiedImageError

from app.extensions import db
from app.models import ConfiguracionVisual


DEFAULT_VISUAL_CONFIGURATION = {
    "nombre_aplicacion": "Cervecería",
    "nombre_corto": "Cervecería",
    "lema": "",
    "color_primario": "#54301A",
    "color_primario_oscuro": "#3E2313",
    "color_acento": "#E9DED3",
    "color_fondo": "#F3EEE7",
    "color_superficie": "#FFFFFF",
    "color_encabezado": "#EFE5DA",
    "color_texto": "#24150C",
    "color_texto_nav": "#F7F1EA",
    "color_borde": "#D8C8B8",
    "fuente_cuerpo": "system",
    "fuente_titulos": "system",
}
FONT_OPTIONS = {
    "system": ("Sistema / Bootstrap", "system-ui, -apple-system, \"Segoe UI\", sans-serif"),
    "inter": ("Inter", "Inter, system-ui, sans-serif"),
    "roboto": ("Roboto", "Roboto, Arial, sans-serif"),
    "lato": ("Lato", "Lato, Arial, sans-serif"),
    "montserrat": ("Montserrat", "Montserrat, Arial, sans-serif"),
    "open-sans": ("Open Sans", "\"Open Sans\", Arial, sans-serif"),
}
IMAGE_FIELDS = {
    "logo": {"attribute": "logo_archivo", "extensions": {".png": "PNG", ".webp": "WEBP"}, "maximum_bytes": 2 * 1024 * 1024},
    "favicon": {"attribute": "favicon_archivo", "extensions": {".png": "PNG", ".ico": "ICO"}, "maximum_bytes": 1 * 1024 * 1024},
    "fondo-login": {"attribute": "fondo_login_archivo", "extensions": {".jpg": "JPEG", ".jpeg": "JPEG", ".png": "PNG", ".webp": "WEBP"}, "maximum_bytes": 5 * 1024 * 1024},
}
COLOR_PATTERN = re.compile(r"^#[0-9A-Fa-f]{6}$")


class InvalidBrandingImage(ValueError):
    pass


def branding_directory():
    return Path(current_app.config["BRANDING_FOLDER"])


def get_visual_configuration():
    configuration = db.session.get(ConfiguracionVisual, 1)
    if configuration is not None:
        return configuration
    return SimpleNamespace(
        id=1, logo_archivo=None, favicon_archivo=None,
        fondo_login_archivo=None, actualizado_por=None, actualizado_en=None,
        **DEFAULT_VISUAL_CONFIGURATION,
    )


def get_or_create_visual_configuration():
    configuration = db.session.get(ConfiguracionVisual, 1)
    if configuration is None:
        configuration = ConfiguracionVisual(id=1, **DEFAULT_VISUAL_CONFIGURATION)
        db.session.add(configuration)
        db.session.commit()
    return configuration


def reset_visual_configuration(configuration):
    for field, value in DEFAULT_VISUAL_CONFIGURATION.items():
        setattr(configuration, field, value)
    configuration.logo_archivo = None
    configuration.favicon_archivo = None
    configuration.fondo_login_archivo = None


def branding_css_values(configuration):
    values = {}
    for field, fallback in DEFAULT_VISUAL_CONFIGURATION.items():
        value = getattr(configuration, field, fallback)
        if field.startswith("color_"):
            values[field] = value if COLOR_PATTERN.fullmatch(value or "") else fallback
    body_key = getattr(configuration, "fuente_cuerpo", "system")
    heading_key = getattr(configuration, "fuente_titulos", "system")
    values["fuente_cuerpo"] = FONT_OPTIONS.get(body_key, FONT_OPTIONS["system"])[1]
    values["fuente_titulos"] = FONT_OPTIONS.get(heading_key, FONT_OPTIONS["system"])[1]
    return values


def validate_color(value):
    normalized = (value or "").strip().upper()
    if not COLOR_PATTERN.fullmatch(normalized):
        raise ValueError(_("El color debe tener el formato hexadecimal #RRGGBB."))
    return normalized


def validate_font(value):
    if value not in FONT_OPTIONS:
        raise ValueError(_("La tipografía seleccionada no es válida."))
    return value


def save_branding_image(file_storage, kind):
    if not file_storage or not file_storage.filename:
        return None
    specification = IMAGE_FIELDS[kind]
    extension = Path(file_storage.filename).suffix.lower()
    expected_format = specification["extensions"].get(extension)
    if expected_format is None:
        raise InvalidBrandingImage(_("El formato de la imagen no está permitido para este campo."))
    maximum_bytes = min(specification["maximum_bytes"], current_app.config["BRANDING_IMAGE_MAX_BYTES"])
    stream = file_storage.stream
    stream.seek(0, 2)
    size = stream.tell()
    stream.seek(0)
    if size <= 0 or size > maximum_bytes:
        raise InvalidBrandingImage(_("La imagen está vacía o supera el tamaño máximo permitido."))
    try:
        with Image.open(stream) as image:
            detected_format = image.format
            image.verify()
    except (UnidentifiedImageError, OSError, SyntaxError):
        raise InvalidBrandingImage(_("El archivo adjunto no contiene una imagen válida."))
    if detected_format != expected_format:
        raise InvalidBrandingImage(_("El contenido de la imagen no coincide con su extensión."))
    stream.seek(0)
    stored_name = f"{kind}-{uuid4().hex}{extension}"
    directory = branding_directory()
    directory.mkdir(parents=True, exist_ok=True)
    file_storage.save(directory / stored_name)
    return stored_name


def delete_branding_image(stored_name):
    if not stored_name:
        return
    safe_name = Path(stored_name).name
    try:
        (branding_directory() / safe_name).unlink(missing_ok=True)
    except OSError:
        current_app.logger.exception("Could not delete branding image %s", safe_name)
