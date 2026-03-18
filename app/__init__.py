from flask import Flask, redirect, url_for
from config import Config
from app.extensions import db, login_manager
from flask_migrate import Migrate
from flask_login import current_user
migrate = Migrate()



def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)


    # Inicializar extensiones
    db.init_app(app)
    migrate.init_app(app, db)

    login_manager.init_app(app)
     
    login_manager.login_view = "auth.login"

    from app import models

    from app.models import Usuario

    @login_manager.user_loader
    def load_user(user_id):
        return Usuario.query.get(int(user_id))

    # Registrar blueprints
    from app.routes.auth import auth_bp
    from app.routes.usuarios import usuarios_bp
    from app.routes.baches import baches_bp
    from app.routes.materias_primas import materias_primas_bp
    from app.routes.recetas import recetas_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(usuarios_bp)
    app.register_blueprint(baches_bp)
    app.register_blueprint(materias_primas_bp)
    app.register_blueprint(recetas_bp)

    from app.cli import register_cli
    register_cli(app)

    from app.routes.estadisticas import estadisticas_bp
    app.register_blueprint(estadisticas_bp)

    from app.routes.barriles import barriles_bp
    app.register_blueprint(barriles_bp)

    from app.routes.clientes import clientes_bp
    app.register_blueprint(clientes_bp)

    from app.routes.catas import bp as catas_bp
    app.register_blueprint(catas_bp)

    @app.route("/")
    def index():
        if current_user.is_authenticated:
            return redirect(url_for("baches.lista"))
        return redirect(url_for("auth.login"))
    
    return app