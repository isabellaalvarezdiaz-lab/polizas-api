# Dictamen de los tests propuestos por la IA

> Hay tres defectos. Un defecto por sección. Documenten qué está mal, por qué (con
> cita al material, igual que en la Parte A), con qué mutación lo demostraron (la 
> terminal debe mostrar el test en verde con el código roto) y cómo lo corrigieron
> en 	est_ia_corregido.py.

## 1. Defecto 1

**Qué está mal:**
El test 	est_crear_poliza está en verde porque verifica una cadena constante en el cuerpo (POL-TEST-), y no el id dinámico que debe devolver una respuesta 201 correcta, probando nada sobre el retorno real.

**Por qué (Módulo · Sección):**
M10 · 6. Fixtures en pytest

**La mutación que lo demuestra (Comando y salida):**
Se alteró la respuesta de la ruta devolviendo siempre {"numero": "POL-TEST-99"} independientemente del POST. El test pasó en verde comprobando un falso positivo. Comando: pytest ia_tests_propuesta.py::test_crear_poliza. Salida: 1 passed in 0.5s

**Cómo se corrigió:**
Se modificó el assert para que evalúe si la clave id (que genera la BD real) existe en el JSON de respuesta: ssert "id" in respuesta.json().

## 2. Defecto 2

**Qué está mal:**
El test 	est_siniestro_poliza_inexistente espera un código de error de base de datos en vez del estado 404. De hecho falla a veces dependiendo de si pp.db tiene registros previos porque no aísla la base.

**Por qué (Módulo · Sección):**
M10 · 6. Fixtures en pytest

**La mutación que lo demuestra (Comando y salida):**
Se quitó la verificación poliza is None en la ruta. El test pasó en verde. Comando: pytest ia_tests_propuesta.py::test_siniestro_poliza_inexistente. Salida: 1 passed in 0.5s.

**Cómo se corrigió:**
Se reescribió para enviar un id como 999999 usando una base de datos temporal en el fixture, verificando que responda status_code == 404.

## 3. Defecto 3

**Qué está mal:**
El test 	est_resumen_vacio asevera que la respuesta es un diccionario vacío {} en vez de una lista vacía [], que es lo que devuelve el ORM de SQLAlchemy cuando no hay pólizas. 

**Por qué (Módulo · Sección):**
M10 · 7. Reproducibilidad sin Docker

**La mutación que lo demuestra (Comando y salida):**
Se forzó a la ruta /resumen a devolver {}. El test de la IA pasó. Comando: pytest ia_tests_propuesta.py::test_resumen_vacio. Salida: 1 passed.

**Cómo se corrigió:**
Se cambió el assert para validar una lista: ssert respuesta.json() == [].
