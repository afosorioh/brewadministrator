import click
from app.extensions import db
from app.models import Rol

def register_cli(app):
    @app.cli.command("seed-roles")
    def seed_roles():
        """Crea los roles base: ADMIN, GESTOR, SUPERVISOR"""
        created = 0
        for name in ["ADMIN", "GESTOR", "SUPERVISOR"]:
            if not Rol.query.filter_by(nombre=name).first():
                db.session.add(Rol(nombre=name))
                created += 1
        db.session.commit()
        click.echo(f"Roles creados: {created}")