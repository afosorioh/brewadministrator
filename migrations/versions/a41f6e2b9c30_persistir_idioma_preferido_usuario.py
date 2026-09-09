"""Persistir idioma preferido por usuario.

Revision ID: a41f6e2b9c30
Revises: b31d87f49a20
Create Date: 2026-09-09 14:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "a41f6e2b9c30"
down_revision = "b31d87f49a20"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("usuario") as batch_op:
        batch_op.add_column(
            sa.Column(
                "idioma_preferido",
                sa.String(length=5),
                nullable=False,
                server_default="es",
            )
        )
        batch_op.create_check_constraint(
            "ck_usuario_idioma_preferido",
            "idioma_preferido IN ('es', 'en')",
        )


def downgrade():
    with op.batch_alter_table("usuario") as batch_op:
        batch_op.drop_constraint(
            "ck_usuario_idioma_preferido", type_="check"
        )
        batch_op.drop_column("idioma_preferido")
