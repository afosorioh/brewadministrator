"""Convertir movimientos historicos de barriles de Bogota a UTC.

Revision ID: c52a8e1f9d43
Revises: b31f2c8d4a70
Create Date: 2026-08-26 09:00:00
"""

from datetime import timezone
from zoneinfo import ZoneInfo

from alembic import op
import sqlalchemy as sa


revision = "c52a8e1f9d43"
down_revision = "b31f2c8d4a70"
branch_labels = None
depends_on = None


BOGOTA_TIMEZONE = ZoneInfo("America/Bogota")


movimiento_barril = sa.table(
    "movimiento_barril",
    sa.column("id_movimiento", sa.Integer),
    sa.column("fecha_hora", sa.DateTime),
)


def _bogota_to_utc_naive(value):
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=BOGOTA_TIMEZONE)
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _utc_to_bogota_naive(value):
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(BOGOTA_TIMEZONE).replace(tzinfo=None)


def _convert_rows(converter):
    connection = op.get_bind()
    rows = connection.execute(
        sa.select(
            movimiento_barril.c.id_movimiento,
            movimiento_barril.c.fecha_hora,
        )
    ).all()

    for row in rows:
        if row[1] is None:
            continue
        connection.execute(
            movimiento_barril.update()
            .where(movimiento_barril.c.id_movimiento == row[0])
            .values(fecha_hora=converter(row[1]))
        )


def upgrade():
    _convert_rows(_bogota_to_utc_naive)


def downgrade():
    _convert_rows(_utc_to_bogota_naive)
