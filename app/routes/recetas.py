from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.extensions import db
from app.models import Receta

from flask_login import login_required
from app.authz import role_required

recetas_bp = Blueprint(
    "recetas",
    __name__,
    url_prefix="/recetas"
)


@recetas_bp.route("/")
@login_required
def lista():
    recetas = Receta.query.order_by(Receta.nombre).all()
    return render_template("recetas/lista.html", recetas=recetas)


@recetas_bp.route("/nueva", methods=["GET", "POST"])
@login_required
@role_required("ADMIN", "GESTOR")
def crear():
    if request.method == "POST":
        nombre = request.form.get("nombre")
        estilo = request.form.get("estilo") or None
        descripcion = request.form.get("descripcion") or None
        volumen = request.form.get("volumen_estandar_litros") or None

        if not nombre:
            flash("El nombre de la receta es obligatorio", "danger")
            return redirect(url_for("recetas.crear"))

        receta = Receta(
            nombre=nombre,
            estilo=estilo,
            descripcion=descripcion,
            volumen_estandar_litros=float(volumen) if volumen else None,
        )

        db.session.add(receta)
        db.session.commit()

        flash("Receta creada correctamente", "success")
        return redirect(url_for("recetas.detalle", receta_id=receta.id))

    return render_template("recetas/formulario.html", receta=None, accion="crear")


@recetas_bp.route("/<int:receta_id>")
def detalle(receta_id):
    receta = Receta.query.get_or_404(receta_id)
    return render_template("recetas/detalle.html", receta=receta)


@recetas_bp.route("/<int:receta_id>/editar", methods=["GET", "POST"])
@login_required
@role_required("ADMIN", "GESTOR")
def editar(receta_id):
    receta = Receta.query.get_or_404(receta_id)

    if request.method == "POST":
        receta.nombre = request.form.get("nombre")
        receta.estilo = request.form.get("estilo") or None
        receta.descripcion = request.form.get("descripcion") or None

        volumen = request.form.get("volumen_estandar_litros") or None
        receta.volumen_estandar_litros = float(volumen) if volumen else None

        if not receta.nombre:
            flash("El nombre es obligatorio", "danger")
            return redirect(url_for("recetas.editar", receta_id=receta.id))

        db.session.commit()
        flash("Receta actualizada correctamente", "success")
        return redirect(url_for("recetas.detalle", receta_id=receta.id))

    return render_template("recetas/formulario.html", receta=receta, accion="editar")


@recetas_bp.route("/<int:receta_id>/eliminar", methods=["POST"])
@login_required
@role_required("ADMIN", "GESTOR")
def eliminar(receta_id):
    receta = Receta.query.get_or_404(receta_id)

    # Verificar si está en uso por algún bache
    if receta.baches.count() > 0:
        flash("No se puede eliminar la receta porque está asociada a baches.", "danger")
        return redirect(url_for("recetas.detalle", receta_id=receta.id))

    db.session.delete(receta)
    db.session.commit()
    flash("Receta eliminada correctamente", "success")
    return redirect(url_for("recetas.lista"))