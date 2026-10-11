# --- Etapa 1: instala las dependencias en un entorno virtual aparte -----------
FROM python:3.11.9-slim-bookworm AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Dependencias primero: si solo cambia el código, esta capa sale del caché.
COPY requirements.txt .
RUN pip install -r requirements.txt


# --- Etapa 2: imagen final, solo con lo necesario para correr ------------------
FROM python:3.11.9-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    DATABASE_URL=sqlite:////app/data/app.db

# Usuario sin privilegios de administrador.
RUN useradd --create-home --uid 1000 appuser

WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
# .dockerignore deja fuera .env, *.db, .venv, .git y los tests.
COPY . .

# Carpeta para la base SQLite, propiedad del usuario que corre el servicio.
RUN mkdir -p /app/data && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

# La imagen slim no trae curl: el chequeo se hace con Python.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import sys, urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3).status == 200 else 1)"

# Crea el esquema con las migraciones y arranca el servicio.
# --host 0.0.0.0 para que responda desde fuera del contenedor (H12); sin --reload.
# `exec` hace que uvicorn reemplace al shell y reciba las señales de apagado.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn main:app --host 0.0.0.0 --port 8000"]
