"""Actualizar modelo de barriles

Revision ID: 293e7088b9fc
Revises: 08374152063a
Create Date: 2026-03-12 19:51:58.045929

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '293e7088b9fc'
down_revision = '08374152063a'
branch_labels = None
depends_on = None


from alembic import op
import sqlalchemy as sa


def upgrade():
    # 1) agregar nuevas columnas
    op.add_column(
        "barril",
        sa.Column("capacidad_litros", sa.Numeric(10, 2), nullable=True)
    )

    op.add_column(
        "movimiento_barril",
        sa.Column("id_usuario", sa.Integer(), nullable=True)
    )

    op.create_foreign_key(
        "movimiento_barril_id_usuario_fkey",
        "movimiento_barril",
        "usuario",
        ["id_usuario"],
        ["id_usuario"],
        ondelete="SET NULL",
    )

    # 2) eliminar dependencia vieja de barril -> tipo_barril
    op.drop_constraint("barril_id_tipo_barril_fkey", "barril", type_="foreignkey")
    op.drop_column("barril", "id_tipo_barril")

    # 3) eliminar tabla vieja
    op.drop_table("tipo_barril")

    # 4) si quieres, dejar capacidad_litros obligatoria después
    op.alter_column("barril", "capacidad_litros", nullable=False)

def downgrade():
    op.create_table(
        "tipo_barril",
        sa.Column("id_tipo_barril", sa.Integer(), primary_key=True),
        sa.Column("nombre", sa.String(length=100), nullable=False),
    )

    op.add_column(
        "barril",
        sa.Column("id_tipo_barril", sa.Integer(), nullable=True)
    )

    op.create_foreign_key(
        "barril_id_tipo_barril_fkey",
        "barril",
        "tipo_barril",
        ["id_tipo_barril"],
        ["id_tipo_barril"],
    )

    op.drop_constraint("movimiento_barril_id_usuario_fkey", "movimiento_barril", type_="foreignkey")
    op.drop_column("movimiento_barril", "id_usuario")
    op.drop_column("barril", "capacidad_litros")
