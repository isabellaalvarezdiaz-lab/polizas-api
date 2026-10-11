"""Esquema inicial: pólizas, siniestros y predicciones.

Revision ID: 0001
Revises:
Create Date: 2026-10-11
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "polizas",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("numero", sa.String(20), nullable=False),
        sa.Column("asegurado", sa.String(80), nullable=False),
        sa.Column("tipo", sa.String(10), nullable=False),
        sa.Column("prima", sa.Float(), nullable=False),
        sa.Column("fecha_inicio", sa.Date(), nullable=False),
        sa.Column("fecha_fin", sa.Date(), nullable=False),
        sa.Column("token_firma", sa.String(64), nullable=False),
        sa.UniqueConstraint("numero", name="uq_polizas_numero"),
    )
    op.create_table(
        "siniestros",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("poliza_id", sa.Integer(),
                  sa.ForeignKey("polizas.id", ondelete="CASCADE"), nullable=False),
        sa.Column("fecha", sa.Date(), nullable=False),
        sa.Column("monto", sa.Float(), nullable=False),
        sa.Column("descripcion", sa.String(200), nullable=False),
        sa.Column("estado", sa.String(10), nullable=False),
    )
    op.create_index("ix_siniestros_poliza_id", "siniestros", ["poliza_id"])
    op.create_table(
        "predicciones",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("poliza_id", sa.Integer(),
                  sa.ForeignKey("polizas.id", ondelete="CASCADE"), nullable=False),
        sa.Column("puntaje", sa.Float(), nullable=False),
        sa.Column("alto_riesgo", sa.Boolean(), nullable=False),
        sa.Column("creado_en", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_predicciones_poliza_id", "predicciones", ["poliza_id"])


def downgrade() -> None:
    op.drop_index("ix_predicciones_poliza_id", table_name="predicciones")
    op.drop_table("predicciones")
    op.drop_index("ix_siniestros_poliza_id", table_name="siniestros")
    op.drop_table("siniestros")
    op.drop_table("polizas")
