# polizas-api

Servicio de gestión de pólizas de la Aseguradora Santo Tomás. Registra pólizas
y los siniestros que se les declaran, resume la cartera y puntúa el riesgo de
cada póliza con un modelo, guardando cada predicción.

Versión corregida de `polizas-api-v0` (Taller del Corte II, Grupo 3). Los
defectos encontrados y su corrección están en `HALLAZGOS.md`.

## Instalación

Requiere **Python 3.11** y, para el contenedor, **Docker**. Los comandos están
escritos para Git Bash (Windows) o una terminal de Linux/macOS.

```bash
git clone https://github.com/isabellaalvarezdiaz-lab/polizas-api.git
cd polizas-api
python -m venv .venv
source .venv/Scripts/activate      # Windows (Git Bash)
# source .venv/bin/activate        # Linux / macOS
pip install -r requirements.txt
```

Todas las dependencias tienen la versión fijada en `requirements.txt`. El
modelo entrenado (`modelo.pkl`) se serializó con `scikit-learn==1.9.1`, la
misma versión que se instala.

## Configuración

La configuración se lee de variables de entorno, después de `.env` y, si no
existe, de `.env.example`, que trae valores de ejemplo para poder arrancar sin
configurar nada. **No hay secretos en el código.** Este paso es opcional: el
servicio arranca sin `.env`. Solo si quiere usar valores propios:

```bash
cp .env.example .env    # y cambie los valores
```

| Variable | Para qué sirve | Valor de ejemplo |
|---|---|---|
| `DATABASE_URL` | Base de datos que usa el servicio | `sqlite:///app.db` |
| `SECRETO_FIRMA` | Secreto con el que se firma cada póliza | `cambia-este-secreto-de-firma` |
| `CLAVE_API_REASEGURO` | Clave del servicio de reaseguro | `cambia-esta-clave-de-reaseguro` |
| `RUTA_MODELO` | Archivo del modelo de riesgo | `modelo.pkl` |
| `UMBRAL_ALTO_RIESGO` | Puntaje a partir del cual una póliza es de alto riesgo | `0.6` |

`.env` y las bases de datos (`*.db`) no se versionan.

## Puesta en marcha (local, con uvicorn)

La base de datos **no se crea sola**: el esquema se crea con las migraciones de
Alembic.

```bash
alembic upgrade head
uvicorn main:app --host 127.0.0.1 --port 8000
```

- `alembic upgrade head` crea las tablas en la base que indica `DATABASE_URL`
  (por defecto `app.db`). La base empieza vacía.
- `uvicorn` debe mostrar `Uvicorn running on http://127.0.0.1:8000`. Mientras
  el servicio está arriba, **esa terminal queda ocupada**: los comandos
  siguientes van en **otra terminal**, abierta en la misma carpeta.
- `--reload` solo se usa en desarrollo, nunca en producción.
- Documentación interactiva: http://127.0.0.1:8000/docs

Comprobación, en la otra terminal:

```bash
curl localhost:8000/health
# {"estado":"ok","base_de_datos":"ok"}
```

Para cargar datos de ejemplo (opcional), también en la otra terminal y con el
entorno activado:

```bash
source .venv/Scripts/activate      # Windows (Git Bash); verá (.venv) al inicio del prompt
# source .venv/bin/activate        # Linux / macOS
python sembrar_datos.py --polizas 12
```

Para apagar el servicio, vuelva a la terminal de `uvicorn` y presione
**Ctrl+C**. Apáguelo antes de usar Docker, porque ocupa el puerto 8000.

## En contenedor (Docker)

Los comandos de Docker se corren **uno por uno**, en la misma terminal (Git
Bash en Windows), dentro de la carpeta del proyecto. Antes, abra **Docker
Desktop** y apague cualquier `uvicorn` local con **Ctrl+C**: Docker necesita el
puerto 8000. No hace falta tener el entorno `.venv` activado, porque el
contenedor trae su propio Python.

```bash
docker build -t polizas-api .
docker run -d --name polizas -p 8000:8000 polizas-api
# espere unos segundos a que arranque
curl localhost:8000/health
# {"estado":"ok","base_de_datos":"ok"}
```

`docker build` construye la imagen (la primera vez tarda unos minutos) y
`docker run -d` arranca el contenedor en segundo plano, así que la terminal
queda libre para seguir escribiendo.

Al arrancar, el contenedor aplica las migraciones (`alembic upgrade head`) y
después levanta el servicio en `0.0.0.0:8000`, para que responda desde fuera
del contenedor. La imagen:

- es multietapa, sobre `python:3.11.9-slim-bookworm`;
- corre con un usuario sin privilegios (`appuser`);
- tiene `HEALTHCHECK` contra `/health` (`docker ps` muestra `healthy`);
- no lleva `.env` ni bases de datos (los excluye `.dockerignore`);
- guarda la base SQLite en `/app/data/app.db`, dentro del contenedor.

Si el puerto 8000 está ocupado (por ejemplo, por un `uvicorn` local), deténgalo
o use otro puerto del host: `-p 8001:8000`.

## Demostración: qué pasa con los datos

Los pasos de la demostración en vivo, en este orden. Antes de empezar, Docker
Desktop debe estar abierto y no debe haber un `uvicorn` local corriendo. Copie
un comando a la vez; las líneas que empiezan con `#` muestran lo que debe
salir. Después de cada `docker run` o `docker restart`, espere unos segundos a
que el servicio arranque (`docker ps` muestra `healthy`).

```bash
# 1. Construir la imagen y arrancar un contenedor
docker build -t polizas-api .
docker run -d --name polizas -p 8000:8000 polizas-api

# 2. Salud
curl -s localhost:8000/health
# {"estado":"ok","base_de_datos":"ok"}

# 3. Crear una póliza: responde 201
curl -s -w "\n%{http_code}\n" -X POST localhost:8000/polizas \
  -H "Content-Type: application/json" \
  -d '{"numero": "POL-2026-09001", "asegurado": "ana rueda", "tipo": "auto", "prima": 1250000,
       "fecha_inicio": "2026-01-15", "fecha_fin": "2027-01-14"}'
# {"id":1,"numero":"POL-2026-09001","asegurado":"Ana Rueda",...}
# 201

# 4. Reiniciar el MISMO contenedor y listar
docker restart polizas
curl -s localhost:8000/polizas
# [{"id":1,"numero":"POL-2026-09001",...}]    <- la póliza sigue ahí

# 5. Borrar el contenedor, crear otro desde la misma imagen y listar
docker rm -f polizas
docker run -d --name polizas -p 8000:8000 polizas-api
curl -s localhost:8000/polizas
# []                                          <- la base está vacía
```

**Por qué pasa eso:**

| Caso | Datos | Explicación |
|---|---|---|
| `docker restart` | **Se conservan** | Reiniciar detiene y vuelve a arrancar el **mismo** contenedor. Su sistema de archivos, incluida la base `/app/data/app.db`, sigue intacto. La migración no borra nada: la base ya está en la última versión. |
| Borrar el contenedor y crear otro | **Se pierden** | La base vivía en la capa de escritura de ese contenedor, y `docker rm` la borra. El contenedor nuevo arranca desde la **imagen**, que no trae base de datos (`.dockerignore` excluye `*.db`), así que la migración crea las tablas vacías. La imagen es una plantilla que no cambia. |

**Para que los datos sobrevivan** a borrar el contenedor, la base tiene que
vivir fuera de él, en un volumen:

```bash
docker run -d --name polizas -p 8000:8000 -v polizas-datos:/app/data polizas-api
```

Con el volumen `polizas-datos`, `docker rm -f polizas` borra el contenedor pero
no el volumen, y un contenedor nuevo con el mismo `-v` encuentra los datos.

Al terminar:

```bash
docker rm -f polizas
```

## Endpoints

| Método | Ruta | Qué hace |
|---|---|---|
| GET | `/health` | 200 si el servicio y la base responden (503 si la base no responde) |
| POST | `/polizas` | Crea una póliza, con sus siniestros si ya tiene (201 · 409 si el número existe · 422 si los datos son inválidos) |
| GET | `/polizas` | Lista las pólizas con sus siniestros |
| GET | `/polizas/{id}` | Consulta una póliza (404 si no existe) |
| PUT | `/polizas/{id}` | Actualiza solo los campos enviados (404 · 422) |
| POST | `/polizas/{id}/siniestros` | Declara un siniestro (201 · 404 · 422) |
| GET | `/siniestros` | Lista los siniestros con el número de su póliza |
| GET | `/resumen` | Siniestros y monto total por póliza |
| POST | `/score` | Puntúa el riesgo de una póliza y guarda la predicción (404 · 422) |
| GET | `/predicciones` | Histórico de predicciones con el número de la póliza |

Las respuestas nunca incluyen campos internos como `token_firma`.

### Ejemplo

```bash
curl -X POST localhost:8000/polizas \
  -H "Content-Type: application/json" \
  -d '{"numero": "POL-2026-09001", "asegurado": "Ana Rueda", "tipo": "auto", "prima": 1250000,
       "fecha_inicio": "2026-01-15", "fecha_fin": "2027-01-14"}'
```

```bash
curl -X POST localhost:8000/score -H "Content-Type: application/json" -d '{"numero": "POL-2026-09001"}'
```

En PowerShell use `curl.exe` en lugar de `curl`, o mejor Git Bash.

## Pruebas

```bash
pytest
```

Corre `tests/test_contrato.py` (el contrato del servicio, intacto),
`tests/test_api.py` y `tests/test_ia_corregido.py`. Los tests usan una base
SQLite temporal para cada test, inyectada con `app.dependency_overrides`: no
modifican `app.db` y dan el mismo resultado si se corren dos veces seguidas.

## Utilidades

- `sembrar_datos.py` crea pólizas de ejemplo a través de la API.
- `contar_consultas.py` cuenta las sentencias SQL que emite cada endpoint
  (Parte C; los resultados están en `CONSULTAS.csv`).
- `verificar_entrega.py` revisa la estructura de la entrega.

## Notas

- Los valores sensibles se leen del entorno (`.env` o `.env.example`), no del
  código. `.env.example` solo trae valores de ejemplo.
- La base de datos no se crea al importar la aplicación: se crea con
  `alembic upgrade head`, localmente o al arrancar el contenedor.
- Entregables del taller: `HALLAZGOS.md`, `CONSULTAS.csv`, `DICTAMEN_IA.md`,
  `BITACORA_IA.md` y `EQUIPO.md`.
