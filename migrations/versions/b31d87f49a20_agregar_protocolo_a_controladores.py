"""agregar protocolo a controladores de temperatura

Revision ID: b31d87f49a20
Revises: 7c91e5a2b640
Create Date: 2026-09-02 10:00:00
"""
from alembic import op
import sqlalchemy as sa


revision = "b31d87f49a20"
down_revision = "7c91e5a2b640"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("controlador_temperatura") as batch_op:
        batch_op.add_column(
            sa.Column(
                "protocolo",
                sa.String(length=10),
                nullable=False,
                server_default="sitrad",
            )
        )
        batch_op.create_check_constraint(
            "ck_controlador_temperatura_protocolo",
            "protocolo IN ('sitrad', 'modbus')",
        )


def downgrade():
    with op.batch_alter_table("controlador_temperatura") as batch_op:
        batch_op.drop_constraint(
            "ck_controlador_temperatura_protocolo", type_="check"
        )
        batch_op.drop_column("protocolo")
