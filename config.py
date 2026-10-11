"""Configuración del servicio (B2).

Prioridad, de mayor a menor:
  1. variables de entorno  (DATABASE_URL=... uvicorn main:app)
  2. .env                   (local, NO se versiona)
  3. .env.example           (valores de ejemplo con los que el servicio arranca)

Así el contenedor arranca sin .env dentro de la imagen, y en local basta con
crear un .env para sobrescribir los valores de ejemplo.
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Si se listan varios archivos, los últimos tienen prioridad: .env pisa a .env.example.
    model_config = SettingsConfigDict(env_file=(".env.example", ".env"),
                                      env_file_encoding="utf-8", extra="ignore")

    database_url: str = "sqlite:///app.db"
    secreto_firma: str
    clave_api_reaseguro: str
    ruta_modelo: str = "modelo.pkl"
    umbral_alto_riesgo: float = 0.6


@lru_cache
def get_settings() -> Settings:
    """Lee la configuración una sola vez y la reutiliza en todas las peticiones."""
    return Settings()
