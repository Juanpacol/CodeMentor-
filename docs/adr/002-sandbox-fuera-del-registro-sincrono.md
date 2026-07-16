# ADR-002: El sandbox vive dentro de `apps/api` y `live_code` no usa el registro síncrono de calificación

## Estado

Aceptado — 2026-07-16.

## Contexto

El plan original de arquitectura ubicaba el sandbox en un directorio propio (`apps/sandbox/`), como si fuera un servicio o paquete separado de la API, análogo a `apps/mcp_server/`. Al implementar la Fase 4 (RE-06) surgieron dos decisiones que se apartan de ese plan inicial y merecen quedar registradas.

## Decisión 1: el runner de PSeInt vive en `apps/api/src/logica/modules/sandbox`, no en `apps/sandbox/`

El motor de calificación (Fase 3, `modules/grading`) necesita invocar el validador/intérprete de PSeInt de forma síncrona y en el mismo proceso — no tiene sentido convertirlo en un servicio HTTP aparte solo por seguir la carpeta del plan al pie de la letra. A diferencia de Piston (que sí es un proceso externo por razones de seguridad: aislar la ejecución de código arbitrario), el intérprete de PSeInt es código nuestro, deshabilitado por diseño para hacer I/O o acceder al sistema — su único riesgo es un ciclo infinito, mitigado con un límite de pasos (`max_steps`), no con aislamiento de proceso. Ponerlo dentro de `apps/api` como cualquier otro módulo de dominio es más simple, más rápido (sin round-trip HTTP) y evita problemas de empaquetado de Python entre paquetes hermanos.

`apps/sandbox/` tal como aparecía en el plan original no se creó como directorio separado; su rol quedó cubierto por `apps/api/src/logica/modules/sandbox/` (cliente de Piston + PSeInt) y la configuración de Piston en `docker-compose.yml`.

## Decisión 2: `live_code` no implementa el protocolo `ExerciseGrader`

El registro de tipos de ejercicio (RE-05, `modules/grading/registry.py`) fue diseñado como funciones **síncronas y puras** — los 7 tipos de RF-10 no requieren I/O. `live_code` (§4.2, "reto de código en vivo") sí lo requiere: calificar significa ejecutar el código del estudiante en Piston, una llamada HTTP asíncrona.

Forzar el protocolo `ExerciseGrader` a ser `async` habría tocado los 7 plugins ya probados de la Fase 3 sin necesidad. En su lugar, `modules/grading/live_code.py` expone `grade_live_code()` como una función async independiente, y `modules/evaluations/service.py` decide con un `if` explícito (`_grade()`) cuál camino tomar según el tipo de ejercicio. Es una pequeña rama de código, no una reescritura del motor — consistente con la promesa de RE-05 de que agregar un tipo nuevo no debería obligar a modificar los tipos existentes.

## Consecuencias

- Agregar un noveno tipo de ejercicio que también necesite I/O (por ejemplo, una skill de IA en la Fase 6) puede seguir el mismo patrón: función async propia + una rama en `_grade()`, sin tocar el registro síncrono.
- El intérprete de PSeInt, al vivir dentro del proceso de la API, comparte el mismo límite de recursos que cualquier otro request — el límite de pasos (`max_steps=10_000` por defecto) es la única salvaguarda y debe mantenerse conservador.
- Si en el futuro PSeInt necesitara ejecutar en un entorno más aislado (por ejemplo, si se le agrega I/O real), debería migrarse al mismo patrón que Piston: proceso externo + cliente HTTP.
