# Bitácora de uso de IA

**Grupo:** 3 · **Integrantes:** Isabella Álvarez, Eduar Caicedo, Anderson Gonzalez
**Herramientas usadas:** Claude Opus 5.5 (effort high)

> Las tres secciones son obligatorias. **`## Rechazado` es la que se califica.**
> Una bitácora que solo lista prompts aceptados vale la mitad.

## Prompts

| # | Parte | Quién | Prompt (resumido si es largo) |
|---|-------|-------|-------------------------------|
| 1 | A | Isabella | «Para cada hallazgo de la Parte A, dame el comando que reproduce la evidencia sobre `v0-semilla` y ayúdame a confirmar en el material el módulo y la sección que explican la causa.» Lo hicimos fila por fila, pegando nuestras salidas y el texto de los módulos |
| 2 | B | Isabella | «Implementa las correcciones de los 14 hallazgos cumpliendo las restricciones B1 a B10, y dame una forma de comprobar, uno por uno, que cada hallazgo quedó corregido y que cada restricción se cumple.» |
| 3 | B | Anderson | «Guíame para comitear la Parte B por restricción, de modo que cada commit quede con mi identidad y el repositorio siga funcionando después de cada uno.» |
| 4 | C | Isabella | «Explícame las cuatro estrategias de carga con el caso de pólizas y siniestros, y ayúdame a diseñar experimentos que comparen cada alternativa contando consultas con `contar_consultas.py`.» |
| 5 | C | Eduar | «El profesor dice que lo de colecciones y escalares es una recomendación y no una regla, y que en `/polizas/{id}` hay que justificar qué aporta la segunda consulta: ayúdanos a reescribir la justificación a partir de lo que medimos.» |
| 6 | D | Anderson | «Explícame cómo se comprueba con mutaciones que los tests de la IA están mal, y cómo verifico sus salidas para que lo de la terminal coincida con lo que va a ir en nuestro Dictamen.» |

## Aceptado

| # | Qué propuso la IA | Por qué lo aceptamos | Qué cambiamos antes de usarlo |
|---|-------------------|----------------------|-------------------------------|
| 1 | El código corregido de la Parte B: configuración con `BaseSettings`, sesión por petición con `get_db`, 409 ante número duplicado, Alembic y Dockerfile multietapa | Repetimos la evidencia de los 14 hallazgos sobre el código nuevo y todos cambiaron al resultado esperado; las restricciones B1 a B10 dieron OK una por una | Lo comiteamos por restricción, de B1 a B9, y corregimos en `HALLAZGOS.md` las filas que no coincidían con el código (ver Rechazado 1 y 2) |
| 2 | Las cuatro estrategias de la Parte C: `selectinload` en `/polizas`, `lazy` en `/polizas/{id}`, `joinedload` en `/siniestros` y consulta `agregada` en `/resumen` | `contar_consultas.py` dio 2/5, 2/2, 1/1 y 1/1 consultas con 10 y 2000 pólizas | No la aceptamos de palabra: medimos cada alternativa cambiando `main.py` por un momento y deshaciendo el cambio con `git checkout`; los resultados están en los párrafos de la Parte C |
| 3 | La explicación de que `selectinload` reparte los ids en grupos de 500, y que por eso con 2000 pólizas salen 5 consultas y no 2 | Explicaba un resultado que nos sorprendió, porque el M9 · 6 da a entender que siempre son 2 | La comprobamos con `--tamanos 500 501 1000 1001`: salieron 2, 3, 3 y 4 consultas; con una sola póliza más aparece otra consulta |
| 4 | Un script que aplica cada mutación de la Parte D, corre el test original y el corregido, y deja el servicio como estaba | Hacía las tres mutaciones de la misma forma cada vez y guardaba las salidas | Revisamos que al final `git diff --stat` saliera vacío y que los 20 casos volvieran a pasar, y comparamos línea por línea las salidas con el dictamen antes de comitearlo |
| 5 | Poner en el dictamen solo las salidas reales de la terminal | El enunciado dice que una salida inventada se detecta | Las pegamos tal cual salieron, con las rutas del computador donde se corrieron |

## Rechazado

| # | Qué propuso la IA | Por qué lo rechazamos | Qué hicimos en su lugar |
|---|-------------------|-----------------------|-------------------------|
| 1 | Citar H14 en «M8 · 4. Inyección de dependencias con Depends» | Al leer la sección vimos que explica `Depends` en general; la sesión que se abre y se cierra por petición, que es la causa de H14, se explica en el M9 · 7 | Cambiamos la cita de la fila H14 de `HALLAZGOS.md` a «M9 · 7. SQLite local e integración con FastAPI» (commit `5fcda40`) |
| 2 | Dejar como corrección aplicada de H8 solo `model_dump(exclude_unset=True)` y de H11 «números únicos por test» | No coincidía con el código de la Parte B: el `PUT` también usa `exclude_none=True` y rechaza con 422 una `fecha_fin` anterior, y lo que aísla los tests es la base nueva en `tmp_path`, no los números | Reescribimos esas dos celdas de `HALLAZGOS.md` para que describan lo que de verdad hace el código (commit `c12e075`) |
| 3 | Justificar las estrategias de la Parte C con el glosario del M9, como si «`selectinload` para colecciones y `joinedload` para escalares» fuera una regla | El profesor nos aclaró que es lo ideal pero no obligatorio, así que la decisión tenía que apoyarse en lo que medimos y no en el glosario | En los párrafos de `/polizas`, `/polizas/{id}` y `/siniestros` el glosario queda como sugerencia y la decisión se justifica con el conteo de cada alternativa (commits `74883ea` y `d7d40b3`) |
| 4 | Defender `lazy` en `/polizas/{id}` solo diciendo que da 2 consultas, igual que `selectinload` | El profesor preguntó qué aporta la segunda consulta, porque si no aporta nada es trabajo de más; además medimos que `joinedload` baja a 1, así que «da igual» no bastaba como argumento | El párrafo explica que la segunda consulta trae los siniestros que la respuesta necesita y la primera no tiene, reconoce que `joinedload` da 1, y justifica `lazy` porque `_poliza_o_404` la usan rutas que no necesitan los siniestros |
| 5 | Tomar los tiempos como prueba de que `joinedload` es más lento que `selectinload` en `/polizas` | El tiempo cambia mucho entre corridas: con el mismo código `/siniestros` tardó 521,6 ms en una y 120,8 ms en otra; en corridas seguidas la diferencia fue de 4,5 ms (139,8 contra 135,3), que no alcanza para decir que sea más lento | Comparamos solo corridas hechas una tras otra, escribimos que `joinedload` hizo 1 consulta en vez de 5 pero «no fue más rápido», y dejamos explicado el ruido en la nota sobre la medición de la Parte C |
| 6 | Una primera versión de `tests/test_ia_corregido.py` con 13 casos de prueba | El calificador aplica tres mutaciones que no vemos (un 404 quitado, un `commit` quitado, un validador que acepta lo que no debe), y esa versión no revisaba que el `PUT` y la declaración de siniestros guardaran de verdad, ni el validador del nombre | La ampliamos a 20 casos y comprobamos que detecta validadores permisivos: al quitar `gt=0` de la prima fallaron 2 casos y al quitar el `return` del validador del nombre fallaron 13 (commit `cca609c`) |
| 7 | `ia_tests_propuesta.py`, la batería de tests generada por un asistente de IA | Tiene tres defectos: tests que aceptan el código del error que deberían detectar, un aislamiento que reemplaza una función que ninguna ruta usa (las pólizas de `app.db` pasaron de 0 a 7) y datos aleatorios sin semilla | No la usamos como prueba del servicio: la auditamos con tres mutaciones en `DICTAMEN_IA.md` y la reemplazamos por `tests/test_ia_corregido.py` (commits `cca609c` y `a08f396`) |
