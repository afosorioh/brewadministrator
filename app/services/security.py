from app import db
from app.models import Rol

def ensure_roles():
    for name in ["ADMIN", "GESTOR", "SUPERVISOR"]:
        if not Rol.query.filter_by(nombre=name).first():
            db.session.add(Rol(nombre=name))
    db.session.commit()