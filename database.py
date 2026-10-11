"""Conexión a la base de datos (B2, B3, B4)."""
from collections.abc import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from config import get_settings


class Base(DeclarativeBase):
    pass


def crear_engine(url: str):
    """Crea el motor. En SQLite activa las claves foráneas en cada conexión."""
    es_sqlite = url.startswith("sqlite")
    engine = create_engine(url, connect_args={"check_same_thread": False} if es_sqlite else {})

    if es_sqlite:
        @event.listens_for(engine, "connect")
        def _activar_claves_foraneas(conexion_dbapi, _registro):
            cursor = conexion_dbapi.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


# El motor sí es único (es el pool de conexiones); las sesiones NO.
engine = crear_engine(get_settings().database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """Una sesión NUEVA por petición: se abre aquí, la ruta la usa, y se cierra
    en el finally aunque la petición haya fallado (H14)."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
