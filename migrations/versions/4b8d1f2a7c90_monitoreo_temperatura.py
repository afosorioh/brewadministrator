"""monitoreo y control de temperatura

Revision ID: 4b8d1f2a7c90
Revises: e08df6768747
Create Date: 2026-08-21 18:00:00
"""
from alembic import op
import sqlalchemy as sa


revision = "4b8d1f2a7c90"
down_revision = "e08df6768747"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "controlador_temperatura",
        sa.Column("id_controlador", sa.Integer(), nullable=False),
        sa.Column("codigo", sa.String(length=80), nullable=False),
        sa.Column("nombre", sa.String(length=120), nullable=False),
        sa.Column("gateway_id", sa.String(length=80), nullable=False),
        sa.Column("device_id", sa.SmallInteger(), nullable=False),
        sa.Column("setpoint_min_c", sa.Numeric(precision=5, scale=1), nullable=False),
        sa.Column("setpoint_max_c", sa.Numeric(precision=5, scale=1), nullable=False),
        sa.Column("activo", sa.Boolean(), nullable=False),
        sa.Column("temperatura_actual_c", sa.Numeric(precision=5, scale=1)),
        sa.Column("setpoint_actual_c", sa.Numeric(precision=5, scale=1)),
        sa.Column("salida_activa", sa.Boolean()),
        sa.Column("error_sensor", sa.Boolean()),
        sa.Column("firmware_version", sa.SmallInteger()),
        sa.Column("ultima_lectura_en", sa.DateTime()),
        sa.Column("creado_en", sa.DateTime(), nullable=False),
        sa.Column("actualizado_en", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id_controlador"),
        sa.UniqueConstraint("codigo"),
        sa.UniqueConstraint(
            "gateway_id", "device_id", name="uq_controlador_gateway_device"
        ),
    )
    op.create_index(
        "ix_controlador_temperatura_gateway_id",
        "controlador_temperatura", ["gateway_id"]
    )

    op.create_table(
        "lectura_temperatura",
        sa.Column("reading_id", sa.String(length=36), nullable=False),
        sa.Column("id_controlador", sa.Integer(), nullable=False),
        sa.Column("observado_en", sa.DateTime(), nullable=False),
        sa.Column("recibido_en", sa.DateTime(), nullable=False),
        sa.Column("temperatura_c", sa.Numeric(precision=5, scale=1), nullable=False),
        sa.Column("setpoint_c", sa.Numeric(precision=5, scale=1), nullable=False),
        sa.Column("salida_activa", sa.Boolean(), nullable=False),
        sa.Column("error_sensor", sa.Boolean(), nullable=False),
        sa.Column("firmware_version", sa.SmallInteger()),
        sa.ForeignKeyConstraint(
            ["id_controlador"], ["controlador_temperatura.id_controlador"],
            ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("reading_id"),
    )
    op.create_index(
        "ix_lectura_temperatura_id_controlador",
        "lectura_temperatura", ["id_controlador"]
    )
    op.create_index(
        "ix_lectura_temperatura_observado_en",
        "lectura_temperatura", ["observado_en"]
    )

    op.create_table(
        "comando_controlador_temperatura",
        sa.Column("command_id", sa.String(length=36), nullable=False),
        sa.Column("id_controlador", sa.Integer(), nullable=False),
        sa.Column("gateway_id", sa.String(length=80), nullable=False),
        sa.Column("accion", sa.String(length=40), nullable=False),
        sa.Column("valor", sa.Numeric(precision=5, scale=1), nullable=False),
        sa.Column("setpoint_esperado_c", sa.Numeric(precision=5, scale=1), nullable=False),
        sa.Column("estado", sa.String(length=20), nullable=False),
        sa.Column("mensaje", sa.Text()),
        sa.Column("creado_en", sa.DateTime(), nullable=False),
        sa.Column("entregado_en", sa.DateTime()),
        sa.Column("confirmado_en", sa.DateTime()),
        sa.Column("creado_por", sa.Integer()),
        sa.ForeignKeyConstraint(
            ["creado_por"], ["usuario.id_usuario"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["id_controlador"], ["controlador_temperatura.id_controlador"],
            ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("command_id"),
    )
    op.create_index(
        "ix_comando_controlador_temperatura_gateway_id",
        "comando_controlador_temperatura", ["gateway_id"]
    )
    op.create_index(
        "ix_comando_controlador_temperatura_id_controlador",
        "comando_controlador_temperatura", ["id_controlador"]
    )
    op.create_index(
        "ix_comando_controlador_temperatura_estado",
        "comando_controlador_temperatura", ["estado"]
    )


def downgrade():
    op.drop_index(
        "ix_comando_controlador_temperatura_estado",
        table_name="comando_controlador_temperatura"
    )
    op.drop_index(
        "ix_comando_controlador_temperatura_id_controlador",
        table_name="comando_controlador_temperatura"
    )
    op.drop_index(
        "ix_comando_controlador_temperatura_gateway_id",
        table_name="comando_controlador_temperatura"
    )
    op.drop_table("comando_controlador_temperatura")
    op.drop_index(
        "ix_lectura_temperatura_observado_en", table_name="lectura_temperatura"
    )
    op.drop_index(
        "ix_lectura_temperatura_id_controlador", table_name="lectura_temperatura"
    )
    op.drop_table("lectura_temperatura")
    op.drop_index(
        "ix_controlador_temperatura_gateway_id",
        table_name="controlador_temperatura"
    )
    op.drop_table("controlador_temperatura")
