# Dictamen sobre `ia_tests_propuesta.py` — Parte D

**Grupo:** 3 · **Integrantes:** Isabella Álvarez, Eduar Caicedo, Anderson Gonzalez

> Tres defectos. Las cuatro secciones de cada uno son obligatorias y se parsean.
> El peso está en **«Cómo lo comprobamos»**, y la comprobación tiene una forma
> concreta: **una mutación**. Introduzcan a propósito un defecto en el servicio,
> muestren que el test original sigue en verde y que el corregido se pone en rojo,
> y vuelvan a dejar el servicio como estaba. Afirmar que un test es malo no vale;
> demostrar que no detecta nada, sí.

Todas las salidas de abajo son las que obtuvimos al correr `bash ~/mutaciones_parte_d.sh`, que aplica cada mutación, corre los dos tests y deja el servicio como estaba con `git checkout -- main.py esquemas.py`. Antes de mutar, `tests/test_ia_corregido.py` pasó entero sobre el código sano (`20 passed`), y al terminar volvió a pasar (`20 passed`).

## Defecto 1

- **Qué está mal**: Hay tests que no pueden fallar, porque aceptan a la vez el resultado correcto y el resultado del error que deberían detectar. `test_consultar_poliza_inexistente` acepta `status_code in (200, 404)`; `test_crear_poliza_responde` y `test_primas_variadas_son_aceptadas` aceptan `in (200, 201, 422)`, o sea que pasan tanto si la póliza se crea como si se rechaza; `test_listar_polizas_no_falla` acepta cualquier código menor que 500, y `test_score_de_poliza_recien_creada` acepta que la respuesta tenga `"puntaje"` **o** `"error"`. Un test así queda en verde con el servicio sano y también con el servicio roto.
- **Por qué es un defecto** (módulo · sección): M6 · 5. Routing y CRUD — el contrato de una API le asigna un código a cada caso (201 al crear, 404 si el recurso no existe, 422 si la entrada es inválida), y si no se declara nada FastAPI responde 200. Un test que acepta 200 y 404 al mismo tiempo no distingue un servicio que cumple el contrato de uno que no.
- **Cómo lo comprobamos**: introdujimos el defecto de «un 404 que deja de devolverse»: en la función que busca la póliza cambiamos el código del error por 200. El test original siguió en verde; el corregido, que exige exactamente 404, se puso en rojo. Después restauramos `main.py` con `git checkout`.

```diff
@@ -42,3 +42,3 @@ def _poliza_o_404(db: Session, id_poliza: int) -> Poliza:
     if poliza is None:
-        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
+        raise HTTPException(status_code=status.HTTP_200_OK,
                             detail=f"no existe la póliza {id_poliza}")
```

```
$ python -m pytest ia_tests_propuesta.py -k consultar_poliza_inexistente -q
.                                                                        [100%]
1 passed, 5 deselected in 1.14s
```

```
$ python -m pytest tests/test_ia_corregido.py -k poliza_inexistente_da_404 -q
C:\Users\USER\polizas-api\tests\test_ia_corregido.py:187: AssertionError: assert 200 == 404
=========================== short test summary info ===========================
FAILED tests/test_ia_corregido.py::test_poliza_inexistente_da_404 - Assertion...
1 failed, 19 deselected in 1.17s
```

- **Corrección**: cada test exige el código exacto del contrato (`== 201`, `== 404`, `== 409`, `== 422`) y además revisa el contenido de la respuesta, no solo que llegue algo. `test_poliza_inexistente_da_404` comprueba el 404 en las cuatro rutas que reciben una póliza (`GET` y `PUT /polizas/{id}`, `POST /polizas/{id}/siniestros` y `/score`); `test_entrada_invalida_da_422` recorre seis entradas inválidas (prima cero y negativa, tipo inválido, fechas invertidas e iguales, siniestro anidado negativo) y verifica que no quede nada guardado; y `/score` exige un `puntaje` entre 0 y 1 y que la predicción quede registrada en `/predicciones`.

## Defecto 2

- **Qué está mal**: El aislamiento de la base es falso, así que los tests no prueban lo que dicen probar. El archivo define su propia función `get_db` y hace `app.dependency_overrides[get_db] = get_db`, es decir, sustituye una función que ninguna ruta usa. La dependencia que reciben las rutas, `database.get_db`, queda intacta, y los tests escriben en la base real de la aplicación aunque el comentario diga que «nunca escriben en la base de datos de la aplicación». Además, si el reemplazo funcionara, inyectaría un `MagicMock`, que acepta cualquier llamada sin guardar nada, y tampoco se estaría probando la persistencia. Por último, como solo miran el código de respuesta, los tests no se dan cuenta si algo se responde como creado pero no se guarda.
- **Por qué es un defecto** (módulo · sección): M10 · 6. Fixtures en pytest — el aislamiento se hace con una fixture que prepara una base nueva para cada test y la inyecta con `app.dependency_overrides` sobre la dependencia que las rutas realmente reciben; la clave del diccionario tiene que ser esa misma función, no otra con el mismo nombre.
- **Cómo lo comprobamos**: primero, con el código sano, contamos las pólizas de `app.db` antes y después de correr `pytest ia_tests_propuesta.py`: pasó de 0 a 7, prueba de que los tests escribieron en la base real. Luego introdujimos el defecto de «un `commit` que se quita»: en la creación de pólizas cambiamos `db.commit()` por `db.flush()`. El servicio sigue respondiendo como si hubiera creado la póliza, pero no la guarda. El test original siguió en verde; el corregido, que vuelve a leer la póliza, se puso en rojo. Después restauramos `main.py` con `git checkout`.

```
pólizas en app.db antes: 0 · después de pytest ia_tests_propuesta.py: 7
```

```diff
@@ -69,3 +69,3 @@ def crear_poliza(datos: PolizaEntrada, db: Session = Depends(get_db),
     try:
-        db.commit()
+        db.flush()
     except IntegrityError:
```

```
$ python -m pytest ia_tests_propuesta.py -k crear_poliza_responde -q
.                                                                        [100%]
1 passed, 5 deselected in 1.03s
```

```
$ python -m pytest tests/test_ia_corregido.py -k queda_guardada -q
C:\Users\USER\polizas-api\tests\test_ia_corregido.py:97: assert 404 == 200
=========================== short test summary info ===========================
FAILED tests/test_ia_corregido.py::test_crear_poliza_devuelve_201_y_queda_guardada
1 failed, 19 deselected in 1.07s
```

- **Corrección**: una fixture crea una base SQLite nueva en `tmp_path` para cada test, con el mismo constructor de motor que usa la aplicación (que activa las claves foráneas), y sustituye `app.dependency_overrides[database.get_db]` por una sesión sobre esa base; al terminar retira el reemplazo. Los tests no se quedan en el código de respuesta: después de crear, actualizar o declarar algo, vuelven a leerlo por la API, y el de creación cuenta que haya exactamente una fila en la base temporal. Así se detecta un `commit` que falte en la creación de pólizas, en el `PUT` (`test_put_parcial_queda_guardado_y_conserva_lo_demas`), en la declaración de siniestros (`test_declarar_siniestro_da_201_y_queda_guardado`) o en `/score` (que revisa `/predicciones`).

## Defecto 3

- **Qué está mal**: Los datos son aleatorios y sin semilla: `tipo` sale de `random.choice` y `prima` de `random.uniform(1, 5_000_000)`. Cada corrida prueba un caso distinto, así que un defecto que solo afecta a una parte del rango se detecta unas veces y otras no, y cuando un test falla no se puede repetir el mismo caso para investigarlo. En el archivo original esto queda oculto porque, además, el assert acepta el 422 (defecto 1).
- **Por qué es un defecto** (módulo · sección): M10 · 4. Framework pytest — un test tiene que ser determinista; el módulo fija la semilla con `random.seed(42)` precisamente para evitar pruebas inestables (*flaky*).
- **Cómo lo comprobamos**: introdujimos el defecto de «un validador que hace lo que no debe»: el esquema pasó a rechazar primas mayores a 2.500.000. Corrimos 10 veces el test original y quedó en verde las 10 veces, porque acepta el 422. Para mostrar el efecto del azar corrimos 10 veces una variante del test original en la que solo cambiamos el assert para exigir 201, conservando los datos aleatorios: pasó 3 veces y falló 7, según la prima que tocara en cada corrida, es decir, el mismo test sobre el mismo código da resultados distintos. El corregido, con primas fijas que incluyen 4.999.999,99, falló las 10 veces y siempre en el mismo caso. Después restauramos `esquemas.py` con `git checkout`.

```diff
@@ -28,3 +28,3 @@ class PolizaEntrada(BaseModel):
     tipo: str = Field(pattern=TIPOS, description="auto, hogar o vida")
-    prima: float = Field(gt=0, description="Prima anual, en pesos")
+    prima: float = Field(gt=0, le=2_500_000, description="Prima anual, en pesos")
     fecha_inicio: date
```

```
$ for i in $(seq 1 10); do python -m pytest ia_tests_propuesta.py -k primas_variadas -q | tail -n 1; done
1 passed, 5 deselected in 1.12s
1 passed, 5 deselected in 1.10s
1 passed, 5 deselected in 1.21s
1 passed, 5 deselected in 1.11s
1 passed, 5 deselected in 1.11s
1 passed, 5 deselected in 1.15s
1 passed, 5 deselected in 1.10s
1 passed, 5 deselected in 1.08s
1 passed, 5 deselected in 1.22s
1 passed, 5 deselected in 1.07s

# variante: mismo test con random, pero exigiendo 201
$ for i in $(seq 1 10); do python -m pytest variante_estricta.py -k crear_poliza_responde -q | tail -n 1; done
1 passed, 5 deselected in 1.09s
1 passed, 5 deselected in 1.14s
1 failed, 5 deselected in 1.05s
1 failed, 5 deselected in 1.00s
1 passed, 5 deselected in 1.06s
1 failed, 5 deselected in 1.00s
1 failed, 5 deselected in 1.08s
1 failed, 5 deselected in 1.05s
1 failed, 5 deselected in 1.03s
1 failed, 5 deselected in 1.08s
```

```
$ for i in $(seq 1 10); do python -m pytest tests/test_ia_corregido.py -k primas_variadas -q | tail -n 1; done
1 failed, 2 passed, 17 deselected in 1.26s
1 failed, 2 passed, 17 deselected in 1.32s
1 failed, 2 passed, 17 deselected in 1.26s
1 failed, 2 passed, 17 deselected in 1.30s
1 failed, 2 passed, 17 deselected in 1.19s
1 failed, 2 passed, 17 deselected in 1.30s
1 failed, 2 passed, 17 deselected in 1.34s
1 failed, 2 passed, 17 deselected in 1.28s
1 failed, 2 passed, 17 deselected in 1.26s
1 failed, 2 passed, 17 deselected in 1.26s
```

- **Corrección**: los datos son fijos y se recorren con `@pytest.mark.parametrize`: primas de 1, 1.250.000,5 y 4.999.999,99 (los dos extremos y un valor intermedio), cada una con uno de los tres tipos. Cada corrida prueba exactamente los mismos casos, y si uno falla se sabe cuál es y se puede repetir. Los números de póliza también son fijos, porque cada test tiene su propia base temporal y no hay colisiones entre tests.
