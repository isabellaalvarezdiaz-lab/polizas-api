"""Entorno de Alembic (B5): la URL sale de DATABASE_URL, igual que en la aplicación."""
import os

from alembic import context
from sqlalchemy import create_engine

import modelos  # noqa: F401  (registra las tablas en Base.metadata)
from config import get_settings
from database import Base

target_metadata = Base.metadata


def url_de_la_base() -> str:
    return os.environ.get("DATABASE_URL") or get_settings().database_url


def migrar_offline() -> None:
    context.configure(url=url_de_la_base(), target_metadata=target_metadata,
                      literal_binds=True, render_as_batch=True)
    with context.begin_transaction():
        context.run_migrations()


def migrar_online() -> None:
    engine = create_engine(url_de_la_base())
    with engine.connect() as conexion:
        context.configure(connection=conexion, target_metadata=target_metadata,
                          render_as_batch=True)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    migrar_offline()
else:
    migrar_online()
