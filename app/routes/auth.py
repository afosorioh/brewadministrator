from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_user, logout_user, login_required, current_user
from app.extensions import db
from app.models import Usuario, Rol
from app.services.security import ensure_roles

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("materias_primas.lista"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        user = Usuario.query.filter_by(username=username).first()
        if not user or not user.activo or not user.check_password(password):
            flash("Credenciales inválidas o usuario inactivo.", "danger")
            return redirect(url_for("auth.login"))

        login_user(user)
        flash("Bienvenido.", "success")
        next_page = request.args.get("next")
        if next_page:
            return redirect(next_page)
        return redirect(url_for("baches.lista"))

    return render_template("auth/login.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Sesión cerrada.", "info")
    return redirect(url_for("auth.login"))


@auth_bp.route("/setup-admin", methods=["GET", "POST"])
def setup_admin():
    # 1) Solo si está permitido
    if not current_app.config.get("ALLOW_BOOTSTRAP", True):
        flash("Bootstrap deshabilitado.", "danger")
        return redirect(url_for("auth.login"))

    # 2) Solo si NO existe un admin
    ensure_roles()
    admin_role = Rol.query.filter_by(nombre="ADMIN").first()
    admin_exists = Usuario.query.filter_by(id_rol=admin_role.id).count() > 0
    if admin_exists:
        flash("Ya existe un ADMIN. No se puede usar setup-admin.", "warning")
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        token = request.form.get("token", "")
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        password2 = request.form.get("password2", "")

        expected = current_app.config.get("BOOTSTRAP_ADMIN_TOKEN", "")
        if not expected or token != expected:
            flash("Token inválido.", "danger")
            return redirect(url_for("auth.setup_admin"))

        if not username or not password:
            flash("Username y contraseña son obligatorios.", "danger")
            return redirect(url_for("auth.setup_admin"))

        if password != password2:
            flash("Las contraseñas no coinciden.", "danger")
            return redirect(url_for("auth.setup_admin"))

        if Usuario.query.filter_by(username=username).first():
            flash("Ese username ya existe.", "danger")
            return redirect(url_for("auth.setup_admin"))

        admin = Usuario(username=username, id_rol=admin_role.id, activo=True)
        admin.set_password(password)
        db.session.add(admin)
        db.session.commit()

        flash("ADMIN creado. Ya puedes iniciar sesión.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/setup_admin.html")