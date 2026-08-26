"""Convertir fechas historicas de baches de Bogota a UTC.

Revision ID: b31f2c8d4a70
Revises: 7c91e5a2b640
Create Date: 2026-08-25 19:00:00
"""

from datetime import timezone
from zoneinfo import ZoneInfo

from alembic import op
import sqlalchemy as sa


revision = "b31f2c8d4a70"
down_revision = "7c91e5a2b640"
branch_labels = None
depends_on = None


BOGOTA_TIMEZONE = ZoneInfo("America/Bogota")


medicion_bache = sa.table(
    "medicion_bache",
    sa.column("id_medicion", sa.Integer),
    sa.column("fecha", sa.DateTime),
)

bache_levadura_uso = sa.table(
    "bache_levadura_uso",
    sa.column("id_bache_levadura", sa.Integer),
    sa.column("fecha_inoculacion", sa.DateTime),
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


def _convert_rows(table, primary_key, datetime_column, converter):
    connection = op.get_bind()
    rows = connection.execute(
        sa.select(primary_key, datetime_column)
    ).all()

    for row in rows:
        value = row[1]
        if value is None:
            continue
        connection.execute(
            table.update()
            .where(primary_key == row[0])
            .values({datetime_column.name: converter(value)})
        )


def upgrade():
    _convert_rows(
        medicion_bache,
        medicion_bache.c.id_medicion,
        medicion_bache.c.fecha,
        _bogota_to_utc_naive,
    )
    _convert_rows(
        bache_levadura_uso,
        bache_levadura_uso.c.id_bache_levadura,
        bache_levadura_uso.c.fecha_inoculacion,
        _bogota_to_utc_naive,
    )


def downgrade():
    _convert_rows(
        medicion_bache,
        medicion_bache.c.id_medicion,
        medicion_bache.c.fecha,
        _utc_to_bogota_naive,
    )
    _convert_rows(
        bache_levadura_uso,
        bache_levadura_uso.c.id_bache_levadura,
        bache_levadura_uso.c.fecha_inoculacion,
        _utc_to_bogota_naive,
    )
