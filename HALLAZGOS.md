# Hallazgos — Parte A

**Grupo:** 3 · **Integrantes:** Eduar Caicedo, Anderson Gonzalez, Isabella Álvarez

> No borren la fila de ejemplo hasta haber comprobado que su tabla se parsea
> (`python verificar_entrega.py`). El formato es rígido: ocho columnas, en este
> orden. Una tabla torcida se rechaza indicando la línea, no se «entiende igual».
>
> **Tuberías dentro de una celda:** si su comando lleva `|` —y varios lo llevarán,
> por `grep`, `head` o `jq`— escríbanlo `\|`. Sin escapar, Markdown lo lee como
> separador de columna y su fila pasa a tener nueve.

| ID | Síntoma observable | Causa | Módulo · Sección | SHA donde se observa | Comando de evidencia | Salida obtenida | Corrección aplicada |
|----|--------------------|-------|------------------|----------------------|----------------------|-----------------|---------------------|
| H1 | La clave de reaseguro y el secreto de firma están en texto plano en `config.py`, versionados en el repositorio | La configuración sensible está escrita como constantes en el código en lugar de leerse del entorno; `.gitignore` tampoco cubre `.env` | M8 · 3. De lo duro a lo flexible: variables de entorno | `v0-semilla` | `git grep -n "CLAVE_API_REASEGURO =" -- config.py` | `config.py:5:CLAVE_API_REASEGURO = "rk-polizas-2026-4b9f0a3d"` | Los secretos salen del código: `Settings(BaseSettings)` los lee de `.env`, `.env.example` lleva valores ficticios y `.env` queda en `.gitignore` |
| H2 | Con `DATABASE_URL` apuntando a otra base, el servicio sigue usando `app.db` | `database.py` crea el engine con `config.DATABASE_URL`, que es una constante; ninguna parte del código lee la variable de entorno | M8 · 3. De lo duro a lo flexible: variables de entorno | `v0-semilla` | `DATABASE_URL=sqlite:///otra.db python -c "import database; print(database.engine.url)"` | `sqlite:///app.db` | `Settings.database_url` se lee del entorno; `get_settings()` con `lru_cache` se inyecta con `Depends`, y el engine se construye con esa URL |
| H3 | `GET /polizas/{id}` expone `token_firma`, un hash derivado del secreto de firma | Las rutas devuelven diccionarios armados a mano sin `response_model`, y `_poliza()` incluye el campo interno | M6 · 5. Routing y CRUD | `v0-semilla` | `curl -s localhost:8000/polizas/1 \| python -c "import sys,json; print(json.load(sys.stdin)['token_firma'])"` | `e0f37b88f9799aa7b9103f60a7346b831e588b62b421480649eb6a4fcfbc1102` | Esquema `PolizaSalida` sin `token_firma`, declarado como `response_model` en todas las rutas de pólizas |
| H4 | Una póliza creada con `asegurado: "Ana Rueda"` queda con `asegurado` nulo; las 12 pólizas de `app.db` también lo tienen nulo | `normalizar_asegurado` calcula el nombre normalizado pero no lo devuelve, así que el validador retorna `None` y Pydantic asigna ese valor; la columna es `Optional`, por eso la base no lo rechaza | M7 · 4. Validadores de campo | `v0-semilla` | `curl -s -X POST localhost:8000/polizas -H "Content-Type: application/json" -d "{\"numero\":\"POL-A-$(date +%s)\",\"asegurado\":\"Ana Rueda\",\"tipo\":\"auto\",\"prima\":1250000,\"fecha_inicio\":\"2026-01-15\",\"fecha_fin\":\"2027-01-14\"}" \| python -c "import sys,json; print(json.load(sys.stdin)['asegurado'])"` | `None` | El validador hace `return " ".join(v.split()).title()`; la columna `asegurado` pasa a ser no nula |
| H5 | Una póliza con un siniestro anidado de monto −50 se crea con 200 | Los anidados se tipan como `siniestros: list[dict]`, así que no se aplica `SiniestroEntrada` (que sí exige `monto > 0`); además `.get()` rellena los campos faltantes con 0 y `""` | M7 · 5. Modelos anidados y topología jerárquica | `v0-semilla` | `curl -s -o /dev/null -w "%{http_code}" -X POST localhost:8000/polizas -H "Content-Type: application/json" -d "{\"numero\":\"POL-C-$(date +%s)\",\"asegurado\":\"Ana Rueda\",\"tipo\":\"auto\",\"prima\":1250000,\"fecha_inicio\":\"2026-01-15\",\"fecha_fin\":\"2027-01-14\",\"siniestros\":[{\"fecha\":\"2026-03-02\",\"monto\":-50,\"descripcion\":\"Choque leve\"}]}"` | `200` | `siniestros: list[SiniestroEntrada]`, lo que devuelve 422 |
| H6 | Una póliza con `fecha_fin` anterior a `fecha_inicio` se crea con 200 | `PolizaEntrada` no tiene ninguna validación entre campos | M7 · 4. Validadores de campo | `v0-semilla` | `curl -s -o /dev/null -w "%{http_code}" -X POST localhost:8000/polizas -H "Content-Type: application/json" -d "{\"numero\":\"POL-D-$(date +%s)\",\"asegurado\":\"Ana Rueda\",\"tipo\":\"auto\",\"prima\":1250000,\"fecha_inicio\":\"2027-01-14\",\"fecha_fin\":\"2026-01-15\"}"` | `200` | `@model_validator(mode="after")` que rechaza `fecha_fin <= fecha_inicio`, lo que devuelve 422 |
| H7 | Crear una póliza responde 200, y consultar una inexistente también responde 200, con cuerpo `{"error": ...}` | El `POST` no declara `status_code=201`, y los "no existe" se devuelven como un diccionario en vez de `HTTPException(404)`; pasa lo mismo en `PUT /polizas/{id}` y en `/score` | M6 · 5. Routing y CRUD | `v0-semilla` | `curl -s -o /dev/null -w "%{http_code}," -X POST localhost:8000/polizas -H "Content-Type: application/json" -d "{\"numero\":\"POL-B-$(date +%s)\",\"asegurado\":\"Ana Rueda\",\"tipo\":\"auto\",\"prima\":1250000,\"fecha_inicio\":\"2026-01-15\",\"fecha_fin\":\"2027-01-14\"}"; curl -s -o /dev/null -w "%{http_code}" localhost:8000/polizas/999999` | `200,200` | `status_code=201` en las creaciones y `raise HTTPException(404)` en `GET`, `PUT`, siniestros y `/score` |
| H8 | Un `PUT` que solo envía la prima borra el `tipo` y la `fecha_fin` de la póliza | `model_dump()` sin `exclude_unset` recorre todos los campos del esquema y escribe `None` en los que no se enviaron | M6 · 5. Routing y CRUD | `v0-semilla` | `curl -s -X PUT localhost:8000/polizas/2 -H "Content-Type: application/json" -d "{\"prima\":999000}" \| python -c "import sys,json; d=json.load(sys.stdin); print(d['tipo'], d['fecha_fin'])"` | `None None` | `datos.model_dump(exclude_unset=True)` |
| H9 | El esquema se crea con `create_all` al importar `main.py`, y no existe `alembic/` | El esquema no está versionado: cualquier cambio de modelo exige borrar la base, y no hay manera de aplicarlo sobre una base vacía de forma controlada | M9 · 6. Modelado de BD y migraciones con Alembic | `v0-semilla` | `git grep -n "create_all" -- main.py` | `main.py:17:Base.metadata.create_all(engine)` | Alembic con una revisión inicial; `env.py` lee `DATABASE_URL`; `create_all` sale del arranque |
| H10 | `requirements.txt` no fija ninguna versión, aunque `modelo.pkl` se serializó con scikit-learn 1.9.1 y numpy 2.x | Cada instalación resuelve versiones distintas, y el modelo puede no cargarse o hacerlo con advertencias; además `app.db` está versionada | M10 · 7. Reproducibilidad sin Docker | `v0-semilla` | `python -c "print(sum('==' in l for l in open('requirements.txt')))"` | `0` | Versiones fijadas con `==`, incluida `scikit-learn==1.9.1`; `git rm --cached app.db`; `.gitignore` con `.env`, `*.db` y `.venv/` |
| H11 | Al correr `tests/test_api.py` dos veces seguidas, la segunda corrida falla y deja `POL-TEST-00001` escrito en `app.db` | Los tests golpean la aplicación con su sesión global sobre la base real, sin `dependency_overrides` ni base temporal, y usan un número de póliza fijo | M10 · 6. Fixtures en pytest | `v0-semilla` | `python -m pytest tests/test_api.py -q >/dev/null 2>&1; python -m pytest tests/test_api.py -q >/dev/null 2>&1; echo $?` | `1` | Fixture con base temporal y `app.dependency_overrides[database.get_db]`; números únicos por test |
| H12 | Dentro del contenedor el servicio responde 200, pero desde el host no responde (código 000) | El `CMD` usa `--host 127.0.0.1`, que solo escucha el loopback interno del contenedor; además usa `--reload`, `python:latest`, corre como root, no tiene `HEALTHCHECK` y copia `app.db` a la imagen | M11 · 6. Estructura de un Dockerfile | `v0-semilla` | `docker build -q -t polizas-v0 . >/dev/null && docker run -d --rm --name pv0 -p 8001:8000 polizas-v0 >/dev/null && sleep 15 && docker exec pv0 python -c "import urllib.request as u; print(u.urlopen('http://127.0.0.1:8000/polizas/1').status, end='')" && curl -s -o /dev/null -w ",%{http_code}" localhost:8001/polizas/1; docker rm -f pv0 >/dev/null` | `200,000` | Imagen multietapa sobre `python:3.11.9-slim-bookworm`, `.dockerignore`, usuario no root, `HEALTHCHECK` y `CMD` con `--host 0.0.0.0` sin `--reload` |
| H13 | Declarar un siniestro sobre la póliza 999999 responde 200, y desde ese momento `GET /siniestros` responde 500 | La ruta no verifica que la póliza exista, y SQLite no aplica la clave foránea porque `PRAGMA foreign_keys` está desactivado por defecto; el siniestro huérfano rompe `_siniestro()` al hacer `s.poliza.numero` sobre `None` | M9 · 7. SQLite local e integración con FastAPI | `v0-semilla` | `curl -s -o /dev/null -w "%{http_code}," -X POST localhost:8000/polizas/999999/siniestros -H "Content-Type: application/json" -d "{\"fecha\":\"2026-03-02\",\"monto\":850000,\"descripcion\":\"Choque leve\"}"; curl -s -o /dev/null -w "%{http_code}" localhost:8000/siniestros` | `200,500` | 404 si la póliza no existe; listener en `connect` que ejecuta `PRAGMA foreign_keys=ON` |
| H14 | Crear una póliza con un número ya existente responde 500, y a partir de ahí **todo** el servicio responde 500 hasta reiniciarlo | El `IntegrityError` no se captura (debería responder 409), y la única sesión, creada a nivel de módulo, queda pendiente de rollback: cada petición siguiente lanza `PendingRollbackError` | M8 · 4. Inyección de dependencias con Depends | `v0-semilla` | `curl -s -o /dev/null -w "%{http_code}," -X POST localhost:8000/polizas -H "Content-Type: application/json" -d "{\"numero\":\"POL-2026-00001\",\"asegurado\":\"Ana Rueda\",\"tipo\":\"auto\",\"prima\":1250000,\"fecha_inicio\":\"2026-01-15\",\"fecha_fin\":\"2027-01-14\"}"; curl -s -o /dev/null -w "%{http_code}" localhost:8000/polizas` | `500,500` | `get_db` como generador con `yield` que abre y cierra una sesión por petición; `IntegrityError` se captura con `rollback()` y se responde 409 |

**Reglas que se verifican automáticamente:**

- `Módulo · Sección` debe citar una lección que exista en los módulos 6 a 11, con el
  título tal como aparece en el menú lateral del material.
- **`SHA donde se observa`** es el commit donde el defecto todavía está: normalmente
  `v0-semilla`, la etiqueta del repositorio tal como se les entregó. El calificador hace
  *checkout* de ese commit para reproducir la evidencia. Si lo dejan en el commit final
  —donde ya está corregido— el comando no reproducirá nada y la fila no cuenta.
- `Comando de evidencia` se ejecuta ahí, con el servicio levantado. Escríbanlo contra
  `localhost:8000`; el calificador sustituye el puerto por el que use. Un comando `docker`
  también vale: se reproduce si hay Docker en la máquina que califica.
- `Salida obtenida` es literal, copiada de su terminal. **Se compara con lo que salga de
  verdad**, así que una salida inventada se detecta.
- Entre 8 y 14 hallazgos. Una fila que no corresponda a un defecto real resta la mitad de
  lo que suma una correcta: el máximo se alcanza con precisión, no con volumen.

---

# Parte C — Interpretación de las consultas

> Un párrafo por endpoint. Expliquen **los conteos que ustedes obtuvieron** con
> `contar_consultas.py`: por qué ese número, por qué cambia o no entre 10 y 2000
> pólizas, y qué estrategia dejaron en el código. Si un resultado los sorprendió,
> díganlo: eso se premia.

## `/polizas`

## `/polizas/{id}`

## `/siniestros`

## `/resumen`
