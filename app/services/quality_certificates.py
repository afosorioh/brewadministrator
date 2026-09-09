from pathlib import Path
from uuid import uuid4

from flask import current_app
from flask_babel import gettext as _
from werkzeug.utils import secure_filename


ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}
CHUNK_SIZE = 64 * 1024


class InvalidQualityCertificate(ValueError):
    pass


def certificate_directory():
    return Path(current_app.config["QUALITY_CERTIFICATES_FOLDER"])


def maximum_certificate_size_mb():
    return current_app.config["QUALITY_CERTIFICATE_MAX_BYTES"] // (1024 * 1024)


def save_quality_certificate(file_storage):
    if not file_storage or not file_storage.filename:
        return None

    original_name = secure_filename(file_storage.filename)
    extension = Path(original_name).suffix.lower()

    if not original_name or extension not in ALLOWED_EXTENSIONS:
        raise InvalidQualityCertificate(
            _("El certificado debe ser un archivo PDF, JPG o PNG.")
        )

    stored_name = f"{uuid4().hex}{extension}"
    directory = certificate_directory()
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / stored_name
    maximum_size = current_app.config["QUALITY_CERTIFICATE_MAX_BYTES"]
    total = 0
    beginning = b""

    try:
        with destination.open("xb") as output:
            while True:
                chunk = file_storage.stream.read(CHUNK_SIZE)
                if not chunk:
                    break
                if len(beginning) < 1024:
                    beginning += chunk[: 1024 - len(beginning)]
                total += len(chunk)
                if total > maximum_size:
                    raise InvalidQualityCertificate(
                        _(
                            "El certificado supera el tamaño máximo de %(size)s MB.",
                            size=maximum_size // (1024 * 1024),
                        )
                    )
                output.write(chunk)

        content_is_valid = (
            extension == ".pdf" and b"%PDF-" in beginning
        ) or (
            extension in {".jpg", ".jpeg"}
            and beginning.startswith(b"\xff\xd8\xff")
        ) or (
            extension == ".png"
            and beginning.startswith(b"\x89PNG\r\n\x1a\n")
        )

        if total == 0 or not content_is_valid:
            raise InvalidQualityCertificate(
                _("El contenido del certificado no coincide con el tipo de archivo.")
            )
    except Exception:
        destination.unlink(missing_ok=True)
        raise

    return stored_name, original_name


def delete_quality_certificate(stored_name):
    if stored_name:
        safe_name = Path(stored_name).name
        try:
            (certificate_directory() / safe_name).unlink(missing_ok=True)
        except OSError:
            current_app.logger.exception(
                "Could not delete quality certificate file %s",
                safe_name,
            )
