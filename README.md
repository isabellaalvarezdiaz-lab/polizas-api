# polizas-api

Servicio de gestión de pólizas de la Aseguradora Santo Tomás. Registra pólizas
y los siniestros que se les declaran, resume la cartera y puntúa el riesgo de
cada póliza con un modelo, guardando cada predicción.

## Instalación

Requiere Python 3.11.

```bash
python -m venv .venv
source .venv/Scripts/activate      # Windows (Git Bash)
# source .venv/bin/activate        # Linux / macOS
pip install -r requirements.txt
```

## Configuración

La configuración se lee de variables de entorno, de `.env` y, si falta, de
`.env.example`, en ese orden de prioridad. Para usar valores propios:

```bash
cp .env.example .env    # y cambie los valores
```

`.env` no se versiona. `DATABASE_URL` decide qué base usa el servicio.

## Puesta en marcha (local)

```bash
alembic upgrade head                          # crea el esquema en la base de DATABASE_URL
uvicorn main:app --host 127.0.0.1 --port 8000
```

`--reload` solo para desarrollo; nunca en producción.
Documentación interactiva: http://127.0.0.1:8000/docs

## En contenedor

```bash
docker build -t polizas-api .
docker run -p 8000:8000 polizas-api
curl localhost:8000/health
```

El contenedor aplica las migraciones al arrancar y guarda la base en
`/app/data/app.db`. `docker restart` conserva los datos; borrar el contenedor y
crear otro desde la misma imagen empieza con una base vacía.

## Endpoints

| Método | Ruta | Qué hace |
|---|---|---|
| GET | `/health` | 200 si el servicio y la base responden |
| POST | `/polizas` | Crea una póliza, con sus siniestros si ya tiene (201 · 409 si el número existe · 422) |
| GET | `/polizas` | Lista las pólizas con sus siniestros |
| GET | `/polizas/{id}` | Consulta una póliza (404 si no existe) |
| PUT | `/polizas/{id}` | Actualiza solo los campos enviados (404 · 422) |
| POST | `/polizas/{id}/siniestros` | Declara un siniestro (201 · 404 · 422) |
| GET | `/siniestros` | Lista los siniestros con el número de su póliza |
| GET | `/resumen` | Siniestros y monto total por póliza |
| POST | `/score` | Puntúa el riesgo de una póliza y guarda la predicción (404 · 422) |
| GET | `/predicciones` | Histórico de predicciones con el número de la póliza |

## Pruebas

```bash
pytest
```

Los tests usan bases temporales: no modifican la base de la aplicación y pasan
igual si se corren dos veces seguidas.

## Utilidades

- `sembrar_datos.py` crea pólizas de ejemplo a través de la API.
- `contar_consultas.py` cuenta las sentencias SQL que emite cada endpoint (Parte C).
