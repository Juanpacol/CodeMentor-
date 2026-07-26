# ADR-006: Multi-tenencia 100% a nivel de aplicación, sin row-level security de Postgres

## Estado

Aceptado — 2026-07-26.

## Contexto

CodeMentor es multi-institución desde el día 1 (RE-04): `TenantMixin`
(`core/mixins.py`) agrega `institution_id` (FK a `institutions`, indexado) a
toda tabla de dominio. La pregunta que este ADR responde es **dónde vive el
límite de aislamiento entre instituciones** — en Postgres (row-level security,
políticas `CREATE POLICY` + `current_setting('app.institution_id')`), o en la
capa de aplicación (un `WHERE institution_id == ...` explícito en cada query).

## Decisión: el aislamiento vive en la aplicación, no en Postgres

Ninguna de las 13 migraciones existentes (`000_pgvector_extension.py` …
`012_tutor_message_sources.py`) habilita RLS ni define una `POLICY`. El único
mecanismo de aislamiento son predicados escritos a mano — **19 ocurrencias de
`institution_id == ...` en 10 archivos** a la fecha de este ADR:

```
ai/agents/pending_approvals.py
ai/rag/ingestion.py
ai/rag/retriever.py
ai/rag/service.py
modules/content/repository.py
modules/exercises/repository.py
modules/groups/repository.py
modules/observability/repository.py
modules/progress/repository.py
modules/users/repository.py
```

más el helper de comparación explícita `core/permissions.py::ensure_same_institution()`,
usado en flujos de "buscar por id y confirmar que es de mi institución" donde
un `NotFoundError` (no `PermissionDeniedError`) evita filtrar la existencia de
un recurso de otra institución.

Esta decisión se mantiene (no se migra a RLS ahora) por dos razones concretas:

1. **El proyecto corre con una sola institución desplegada en producción**
   (INEM José Félix de Restrepo, ver `docs/despliegue.md`) — la partición es
   lógica "desde el día 1" precisamente para no tener que migrar el esquema
   el día que aparezca una segunda institución, no porque haya una necesidad
   de aislamiento *activo* hoy.
2. **RLS de Postgres tiene un costo de operación real**: cada conexión
   necesitaría fijar `current_setting('app.institution_id')` por request
   (vía un middleware o un `SET LOCAL` por transacción), y con SQLAlchemy
   async + pooling eso es una superficie nueva de bugs sutiles (una conexión
   reciclada del pool que no resetea el setting correctamente filtra entre
   tenants de la peor manera posible: silenciosamente). Introducir esa
   superficie sin un segundo tenant real que la ejercite es costo sin
   beneficio medible todavía.

## Riesgo aceptado y su mitigación actual

El riesgo real de este enfoque: **19 predicados escritos a mano no tienen
respaldo de compilador ni de base de datos** — un repositorio nuevo que
olvide su `WHERE institution_id == ...` es una fuga entre tenants silenciosa,
indistinguible de una query correcta hasta que alguien la audita. La
mitigación actual es puramente de proceso: `CLAUDE.md` documenta la regla
("todo repositorio/query nuevo que toque una tabla con `TenantMixin` necesita
ese filtro") y el code review humano es la única red.

### Desviaciones ya detectadas (documentadas aquí para que no se pierdan)

Auditando el código para este ADR se confirmaron dos lugares que **no** siguen
el patrón, ninguno de los dos alcanza a ser una fuga de datos entre
instituciones hoy, pero valen la pena registrar:

- **`ai/harness/cache.py::_cache_key`** — la clave de caché de Redis es
  `f"ai_cache:{task}:{sha256(prompt)}"`, sin `institution_id`. Dos
  instituciones que le piden al harness la *misma* tarea con el *mismo* texto
  de prompt renderizado (ej. una pista genérica de PSeInt sin datos
  específicos del estudiante) recibirían la respuesta cacheada de la otra. No
  es una fuga de datos personales — el prompt ya pasó por guardrails de
  entrada y no debería contener PII — pero sí es una desviación real del
  patrón de aislamiento por tenant que el resto del código sigue.
- **`ai/repository.py::list_interactions_for_user`** — filtra solo por
  `user_id`, sin `institution_id`. Hoy es inofensivo porque `user_id` es un
  UUID global (no hay colisión posible entre instituciones), pero rompe la
  convención "toda query de una tabla `TenantMixin` lleva el filtro
  explícito" que las otras 19 sí siguen — un futuro cambio que reutilice este
  patrón sin ese contexto podría copiar el hueco a un caso donde sí importe.

Ninguna de las dos se corrige en este ADR — es una decisión de alcance, no un
descuido: este documento existe para **registrar la decisión y la deuda**, no
para pagarla. Un futuro ADR (o una PR dedicada) puede decidir si vale la pena
tenant-scopear la caché y esa query específica.

## Cuándo reconsiderar

Si aparece una segunda institución real desplegada — no antes —, vale la pena
evaluar RLS como defensa en profundidad *adicional* a los predicados de
aplicación (no en reemplazo: los predicados siguen siendo necesarios para
queries que RLS no cubre bien, como agregaciones cross-tabla). El costo de
diseño de ese momento incluye: decidir cómo se propaga
`current_setting('app.institution_id')` por request con SQLAlchemy async +
pooling, y auditar que ninguna conexión reciclada del pool arrastre el
setting de un tenant anterior.

## Consecuencias

- Ningún cambio de código en este ADR — es puramente de registro de una
  decisión ya vigente y su deuda conocida.
- La regla de "todo repositorio nuevo sobre una tabla `TenantMixin` lleva su
  `WHERE institution_id`" queda escrita en `CLAUDE.md`, no solo en la cabeza
  de quien la escribió.
- Las dos desviaciones quedan como items conocidos, no como sorpresas para
  quien audite el código después.
