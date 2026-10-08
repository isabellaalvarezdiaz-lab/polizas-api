# Dictamen sobre `ia_tests_propuesta.py` — Parte D

**Grupo:** <6> · **Integrantes:** Eduar Caicedo, Anderson Gonzalez, Isabella Álvarez

> Tres defectos. Las cuatro secciones de cada uno son obligatorias y se parsean.
> El peso está en **«Cómo lo comprobamos»**, y la comprobación tiene una forma
> concreta: **una mutación**. Introduzcan a propósito un defecto en el servicio,
> muestren que el test original sigue en verde y que el corregido se pone en rojo,
> y vuelvan a dejar el servicio como estaba. Afirmar que un test es malo no vale;
> demostrar que no detecta nada, sí.

## Defecto 1

- **Qué está mal:** Hay tests que no pueden fallar. `test_consultar_poliza_inexistente` acepta `status_code in (200, 404)`, `test_crear_poliza_responde` y `test_primas_variadas_son_aceptadas` aceptan `in (200, 201, 422)`, `test_listar_polizas_no_falla` acepta cualquier código `< 500` y `test_score_de_poliza_recien_creada` acepta `"puntaje" in r.json() or "error" in r.json()`. Cada tupla incluye justamente el código del error que el test debería detectar.
- **Por qué es un defecto** (módulo · sección): M6 · 5. Routing y CRUD — el contrato asigna un código a cada caso (201 al crear, 404 si el recurso no existe, 409 si choca con lo existente) y advierte que si no se declara nada FastAPI responde 200; un test que acepta 200 y 404 a la vez no distingue el servicio correcto del roto.
- **Cómo lo comprobamos:** mutamos `GET /polizas/{id}` para que una póliza inexistente devuelva 200 en lugar de 404. El test original sigue en verde; el corregido, que exige exactamente 404, se pone en rojo. Después revertimos con `git checkout -- main.py`.

```diff
# PENDIENTE: ajustar a las líneas reales de main.py cuando esté el núcleo
-    if poliza is None:
-        raise HTTPException(status_code=404, detail="Póliza no encontrada")
+    if poliza is None:
+        return {}
```

```
# PENDIENTE: pytest ia_tests_propuesta.py -k consultar_poliza_inexistente -q  (debe salir 1 passed)
```

```
# PENDIENTE: pytest tests/test_ia_corregido.py -k poliza_inexistente_da_404 -q  (debe salir 1 failed)
```

- **Corrección:** cada test exige el código exacto del contrato (`== 201`, `== 404`, `== 409`, `== 422`) y comprueba el contenido de la respuesta, no solo que llegue algo; `/score` exige un `puntaje` entre 0 y 1 y que la predicción quede registrada en `/predicciones`.

## Defecto 2

- **Qué está mal:** El aislamiento de la base es falso, así que los tests no prueban lo que dicen. El archivo define su propia función `get_db` y hace `app.dependency_overrides[get_db] = get_db`: sustituye una función que ninguna ruta usa por sí misma. La dependencia real, `database.get_db`, queda intacta, y los tests escriben en la base de la aplicación. Además, si el reemplazo funcionara, inyectaría un `MagicMock`, que acepta cualquier llamada sin guardar nada: tampoco se probaría la persistencia.
- **Por qué es un defecto** (módulo · sección): M10 · 6. Fixtures en pytest — el aislamiento se hace con una fixture que crea una base temporal y con `app.dependency_overrides` sobre la dependencia que las rutas realmente reciben; la clave del diccionario tiene que ser esa misma función.
- **Cómo lo comprobamos:** primero, contamos las pólizas de `app.db` antes y después de correr `pytest ia_tests_propuesta.py`: el número sube, prueba de que los tests escribieron en la base real. Luego mutamos `crear_poliza` cambiando `db.commit()` por `db.flush()`: la respuesta sigue siendo 201, pero la póliza no se guarda. El test original sigue en verde; el corregido, que lee la póliza de vuelta y la cuenta en la base temporal, se pone en rojo.

```diff
# PENDIENTE: ajustar a las líneas reales de main.py cuando esté el núcleo
-    db.commit()
+    db.flush()
```

```
# PENDIENTE: pytest ia_tests_propuesta.py -k crear_poliza_responde -q  (debe salir 1 passed)
```

```
# PENDIENTE: pytest tests/test_ia_corregido.py -k queda_guardada -q  (debe salir 1 failed)
```

- **Corrección:** una fixture crea una base SQLite nueva en `tmp_path` para cada test y sustituye `app.dependency_overrides[database.get_db]` por una sesión sobre esa base; al terminar se retira el reemplazo. El test de creación lee la póliza de vuelta y verifica que quedó exactamente una fila en la base temporal.

## Defecto 3

- **Qué está mal:** Los datos son aleatorios y sin semilla: `tipo` sale de `random.choice` y `prima` de `random.uniform(1, 5_000_000)`. Cada corrida prueba un caso distinto, así que un defecto que solo afecta a una parte del rango se detecta unas veces y otras no, y una falla no se puede reproducir para investigarla.
- **Por qué es un defecto** (módulo · sección): M10 · 4. Framework pytest — un test tiene que ser determinista; el módulo fija la semilla (`random.seed(42)`) precisamente para evitar pruebas inestables (*flaky*).
- **Cómo lo comprobamos:** mutamos el esquema para rechazar primas mayores a 2.500.000 (`Field(gt=0, le=2_500_000)`). Corrimos 10 veces una versión del test original con el assert ya exigiendo 201 pero conservando `random`: unas corridas pasan y otras fallan, según la prima que tocó. El corregido, con primas fijas que incluyen 4.999.999,99, falla las 10 veces.

```diff
-    prima: float = Field(gt=0, description="Prima anual, en pesos")
+    prima: float = Field(gt=0, le=2_500_000, description="Prima anual, en pesos")
```

```
# PENDIENTE: 10 corridas del test con random y assert == 201 (mezcla de passed y failed)
```

```
# PENDIENTE: 10 corridas de pytest tests/test_ia_corregido.py -k primas_variadas -q (failed las 10)
```

- **Corrección:** los datos son fijos y se recorren con `@pytest.mark.parametrize`: primas de 1, 1.250.000,5 y 4.999.999,99 (los extremos y un valor intermedio) combinadas con los tres tipos. Cada corrida prueba exactamente los mismos casos, y el número de póliza es fijo porque cada test tiene su propia base.
