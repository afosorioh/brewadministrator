"""asociar lecturas de temperatura con bache

Revision ID: 7c91e5a2b640
Revises: 4b8d1f2a7c90
Create Date: 2026-08-22 09:00:00
"""
from alembic import op
import sqlalchemy as sa


revision = "7c91e5a2b640"
down_revision = "4b8d1f2a7c90"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("controlador_temperatura") as batch_op:
        batch_op.add_column(sa.Column("id_bache_actual", sa.Integer(), nullable=True))
        batch_op.create_index(
            "ix_controlador_temperatura_id_bache_actual", ["id_bache_actual"]
        )
        batch_op.create_foreign_key(
            "fk_controlador_temperatura_bache_actual",
            "bache",
            ["id_bache_actual"],
            ["id_bache"],
            ondelete="SET NULL",
        )

    with op.batch_alter_table("lectura_temperatura") as batch_op:
        batch_op.add_column(sa.Column("id_bache", sa.Integer(), nullable=True))
        batch_op.create_index("ix_lectura_temperatura_id_bache", ["id_bache"])
        batch_op.create_foreign_key(
            "fk_lectura_temperatura_bache",
            "bache",
            ["id_bache"],
            ["id_bache"],
            ondelete="SET NULL",
        )


def downgrade():
    with op.batch_alter_table("lectura_temperatura") as batch_op:
        batch_op.drop_constraint(
            "fk_lectura_temperatura_bache", type_="foreignkey"
        )
        batch_op.drop_index("ix_lectura_temperatura_id_bache")
        batch_op.drop_column("id_bache")

    with op.batch_alter_table("controlador_temperatura") as batch_op:
        batch_op.drop_constraint(
            "fk_controlador_temperatura_bache_actual", type_="foreignkey"
        )
        batch_op.drop_index("ix_controlador_temperatura_id_bache_actual")
        batch_op.drop_column("id_bache_actual")
