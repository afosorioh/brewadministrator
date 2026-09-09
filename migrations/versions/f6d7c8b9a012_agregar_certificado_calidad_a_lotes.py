"""Agregar certificado de calidad a lotes de materia prima.

Revision ID: f6d7c8b9a012
Revises: a41f6e2b9c30
Create Date: 2026-09-10 10:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "f6d7c8b9a012"
down_revision = "a41f6e2b9c30"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("lote_materia_prima") as batch_op:
        batch_op.add_column(
            sa.Column(
                "certificado_calidad_archivo",
                sa.String(length=80),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column(
                "certificado_calidad_nombre",
                sa.String(length=255),
                nullable=True,
            )
        )


def downgrade():
    with op.batch_alter_table("lote_materia_prima") as batch_op:
        batch_op.drop_column("certificado_calidad_nombre")
        batch_op.drop_column("certificado_calidad_archivo")
