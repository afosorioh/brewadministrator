from flask import Blueprint, abort, flash, redirect, render_template, request, send_from_directory, url_for
from flask_babel import gettext as _
from flask_login import current_user, login_required

from app.authz import role_required
from app.extensions import db
from app.services.branding import (
    DEFAULT_VISUAL_CONFIGURATION, FONT_OPTIONS, IMAGE_FIELDS,
    InvalidBrandingImage, branding_directory, delete_branding_image,
    get_or_create_visual_configuration, get_visual_configuration,
    reset_visual_configuration, save_branding_image, validate_color, validate_font,
)

configuracion_visual_bp = Blueprint("configuracion_visual", __name__, url_prefix="/configuracion-visual")
COLOR_FIELDS = (
    "color_primario", "color_primario_oscuro", "color_acento",
    "color_fondo", "color_superficie", "color_encabezado",
    "color_texto", "color_texto_nav", "color_borde",
)
IMAGE_FORM_FIELDS = {
    "logo": "logo_archivo",
    "favicon": "favicon_archivo",
    "fondo-login": "fondo_login_archivo",
}


@configuracion_visual_bp.route("/", methods=["GET", "POST"])
@login_required
@role_required("ADMIN")
def formulario():
    configuration = get_or_create_visual_configuration()
    if request.method == "POST":
        if request.form.get("action") == "restore":
            old_images = [configuration.logo_archivo, configuration.favicon_archivo, configuration.fondo_login_archivo]
            reset_visual_configuration(configuration)
            configuration.actualizado_por = current_user.id
            db.session.commit()
            for filename in old_images:
                delete_branding_image(filename)
            flash(_("Se restauró el diseño predeterminado."), "success")
            return redirect(url_for("configuracion_visual.formulario"))

        try:
            form_values = _validated_form_values()
        except ValueError as error:
            flash(str(error), "danger")
            return redirect(url_for("configuracion_visual.formulario"))

        new_files = {}
        try:
            for kind, attribute in IMAGE_FORM_FIELDS.items():
                stored_name = save_branding_image(request.files.get(kind.replace("-", "_")), kind)
                if stored_name:
                    new_files[attribute] = stored_name
        except InvalidBrandingImage as error:
            for filename in new_files.values():
                delete_branding_image(filename)
            flash(str(error), "danger")
            return redirect(url_for("configuracion_visual.formulario"))

        old_files_to_delete = []
        for field, value in form_values.items():
            setattr(configuration, field, value)
        for kind, attribute in IMAGE_FORM_FIELDS.items():
            old_filename = getattr(configuration, attribute)
            if attribute in new_files:
                setattr(configuration, attribute, new_files[attribute])
                if old_filename:
                    old_files_to_delete.append(old_filename)
            elif request.form.get(f"eliminar_{attribute}") == "on":
                setattr(configuration, attribute, None)
                if old_filename:
                    old_files_to_delete.append(old_filename)

        configuration.actualizado_por = current_user.id
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            for filename in new_files.values():
                delete_branding_image(filename)
            raise
        for filename in old_files_to_delete:
            delete_branding_image(filename)
        flash(_("Configuración visual actualizada."), "success")
        return redirect(url_for("configuracion_visual.formulario"))

    return render_template(
        "configuracion_visual/formulario.html",
        configuration=configuration,
        defaults=DEFAULT_VISUAL_CONFIGURATION,
        font_options=FONT_OPTIONS,
    )


@configuracion_visual_bp.get("/archivo/<kind>")
def archivo(kind):
    specification = IMAGE_FIELDS.get(kind)
    if specification is None:
        abort(404)
    configuration = get_visual_configuration()
    filename = getattr(configuration, specification["attribute"])
    if not filename:
        abort(404)
    return send_from_directory(branding_directory(), filename, conditional=True, max_age=3600)


def _validated_form_values():
    nombre_aplicacion = request.form.get("nombre_aplicacion", "").strip()
    nombre_corto = request.form.get("nombre_corto", "").strip()
    lema = request.form.get("lema", "").strip()
    if not nombre_aplicacion or not nombre_corto:
        raise ValueError(_("El nombre de la aplicación y el nombre corto son obligatorios."))
    if len(nombre_aplicacion) > 120 or len(nombre_corto) > 60 or len(lema) > 180:
        raise ValueError(_("Uno de los textos supera la longitud permitida."))
    values = {
        "nombre_aplicacion": nombre_aplicacion,
        "nombre_corto": nombre_corto,
        "lema": lema,
        "fuente_cuerpo": validate_font(request.form.get("fuente_cuerpo")),
        "fuente_titulos": validate_font(request.form.get("fuente_titulos")),
    }
    for field in COLOR_FIELDS:
        values[field] = validate_color(request.form.get(field))
    return values
