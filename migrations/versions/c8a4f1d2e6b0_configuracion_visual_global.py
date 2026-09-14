"""Crear configuración visual global con el tema actual.

Revision ID: c8a4f1d2e6b0
Revises: f6d7c8b9a012
Create Date: 2026-09-14 18:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = "c8a4f1d2e6b0"
down_revision = "f6d7c8b9a012"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "configuracion_visual",
        sa.Column("id_configuracion", sa.SmallInteger(), nullable=False),
        sa.Column("nombre_aplicacion", sa.String(120), nullable=False, server_default="Cervecería"),
        sa.Column("nombre_corto", sa.String(60), nullable=False, server_default="Cervecería"),
        sa.Column("lema", sa.String(180), nullable=True),
        sa.Column("color_primario", sa.String(7), nullable=False, server_default="#54301A"),
        sa.Column("color_primario_oscuro", sa.String(7), nullable=False, server_default="#3E2313"),
        sa.Column("color_acento", sa.String(7), nullable=False, server_default="#E9DED3"),
        sa.Column("color_fondo", sa.String(7), nullable=False, server_default="#F3EEE7"),
        sa.Column("color_superficie", sa.String(7), nullable=False, server_default="#FFFFFF"),
        sa.Column("color_encabezado", sa.String(7), nullable=False, server_default="#EFE5DA"),
        sa.Column("color_texto", sa.String(7), nullable=False, server_default="#24150C"),
        sa.Column("color_texto_nav", sa.String(7), nullable=False, server_default="#F7F1EA"),
        sa.Column("color_borde", sa.String(7), nullable=False, server_default="#D8C8B8"),
        sa.Column("fuente_cuerpo", sa.String(30), nullable=False, server_default="system"),
        sa.Column("fuente_titulos", sa.String(30), nullable=False, server_default="system"),
        sa.Column("logo_archivo", sa.String(80), nullable=True),
        sa.Column("favicon_archivo", sa.String(80), nullable=True),
        sa.Column("fondo_login_archivo", sa.String(80), nullable=True),
        sa.Column("actualizado_por", sa.Integer(), nullable=True),
        sa.Column("actualizado_en", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("id_configuracion = 1", name="ck_configuracion_visual_unica"),
        sa.ForeignKeyConstraint(["actualizado_por"], ["usuario.id_usuario"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id_configuracion"),
    )
    op.bulk_insert(
        sa.table(
            "configuracion_visual",
            sa.column("id_configuracion", sa.SmallInteger()),
            sa.column("nombre_aplicacion", sa.String()),
            sa.column("nombre_corto", sa.String()),
            sa.column("lema", sa.String()),
            sa.column("color_primario", sa.String()),
            sa.column("color_primario_oscuro", sa.String()),
            sa.column("color_acento", sa.String()),
            sa.column("color_fondo", sa.String()),
            sa.column("color_superficie", sa.String()),
            sa.column("color_encabezado", sa.String()),
            sa.column("color_texto", sa.String()),
            sa.column("color_texto_nav", sa.String()),
            sa.column("color_borde", sa.String()),
            sa.column("fuente_cuerpo", sa.String()),
            sa.column("fuente_titulos", sa.String()),
        ),
        [{
            "id_configuracion": 1,
            "nombre_aplicacion": "Cervecería",
            "nombre_corto": "Cervecería",
            "lema": "",
            "color_primario": "#54301A",
            "color_primario_oscuro": "#3E2313",
            "color_acento": "#E9DED3",
            "color_fondo": "#F3EEE7",
            "color_superficie": "#FFFFFF",
            "color_encabezado": "#EFE5DA",
            "color_texto": "#24150C",
            "color_texto_nav": "#F7F1EA",
            "color_borde": "#D8C8B8",
            "fuente_cuerpo": "system",
            "fuente_titulos": "system",
        }],
    )


def downgrade():
    op.drop_table("configuracion_visual")
