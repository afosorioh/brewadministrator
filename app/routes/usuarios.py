from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from app.authz import role_required
from app.extensions import db
from app.models import Usuario, Rol

usuarios_bp = Blueprint("usuarios", __name__, url_prefix="/usuarios")

@usuarios_bp.route("/")
@login_required
@role_required("ADMIN")
def lista():
    usuarios = Usuario.query.order_by(Usuario.username).all()
    return render_template("usuarios/lista.html", usuarios=usuarios)

@usuarios_bp.route("/nuevo", methods=["GET","POST"])
@login_required
@role_required("ADMIN")
def crear():
    roles = Rol.query.order_by(Rol.nombre).all()
    if request.method == "POST":
        username = request.form.get("username","").strip()
        password = request.form.get("password","")
        password2 = request.form.get("password2","")
        id_rol = request.form.get("id_rol")
        activo = request.form.get("activo") == "on"

        if not username or not password or not id_rol:
            flash("Usuario, contraseña y rol son obligatorios.", "danger")
            return redirect(url_for("usuarios.crear"))

        if password != password2:
            flash("Las contraseñas no coinciden.", "danger")
            return redirect(url_for("usuarios.crear"))

        if Usuario.query.filter_by(username=username).first():
            flash("Ese username ya existe.", "danger")
            return redirect(url_for("usuarios.crear"))

        u = Usuario(username=username, id_rol=int(id_rol), activo=activo)
        u.set_password(password)
        db.session.add(u)
        db.session.commit()
        flash("Usuario creado.", "success")
        return redirect(url_for("usuarios.lista"))

    return render_template("usuarios/formulario.html", usuario=None, roles=roles, accion="crear")

@usuarios_bp.route("/<int:user_id>/editar", methods=["GET","POST"])
@login_required
@role_required("ADMIN")
def editar(user_id):
    u = Usuario.query.get_or_404(user_id)
    roles = Rol.query.order_by(Rol.nombre).all()

    if request.method == "POST":
        u.username = request.form.get("username","").strip()
        u.id_rol = int(request.form.get("id_rol"))
        u.activo = request.form.get("activo") == "on"

        new_password = request.form.get("new_password","")
        new_password2 = request.form.get("new_password2","")
        if new_password or new_password2:
            if new_password != new_password2:
                flash("Las nuevas contraseñas no coinciden.", "danger")
                return redirect(url_for("usuarios.editar", user_id=u.id))
            u.set_password(new_password)

        db.session.commit()
        flash("Usuario actualizado.", "success")
        return redirect(url_for("usuarios.lista"))

    return render_template("usuarios/formulario.html", usuario=u, roles=roles, accion="editar")