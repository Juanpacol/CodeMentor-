# Diccionario de datos

Se completa incrementalmente a medida que cada fase introduce sus modelos (ver migraciones en `apps/api/alembic/versions/`). Cada tabla nueva debe documentarse aquí en la misma fase que la introduce.

## Fase 0

| Tabla / extensión | Descripción |
|---|---|
| `vector` (extensión) | Extensión de PostgreSQL (pgvector) habilitada en la migración `000` para soportar embeddings del RAG pedagógico (Fase 5). |

## Fase 1 (migración `001`)

Todas las tablas de dominio (excepto `institutions`, que es la raíz del tenant) incluyen `institution_id` como llave foránea (RE-04, particionamiento lógico multi-tenant desde el día 1) y las columnas `created_at`/`updated_at`.

| Tabla | Descripción |
|---|---|
| `institutions` | Raíz del tenant. `email_domains` (array) resuelve automáticamente a qué institución pertenece un correo en registro/login (RF-01). |
| `users` | Estudiantes, docentes y administradores (`role` enum). Único por `(institution_id, email)`. `student_code` permite la verificación de identidad institucional alternativa al correo (RF-01). |
| `password_reset_tokens` | Tokens de un solo uso (hash con Argon2, nunca en texto plano) para recuperación de contraseña (RF-03). |
| `groups` | Grupos de un docente (`teacher_id`), con `invite_code` único por institución y `archived_at` para archivado (RF-05). |
| `group_memberships` | Relación estudiante↔grupo, única por `(group_id, student_id)` (RF-04, RF-06). |
| `audit_logs` | Registro de auditoría transversal (§6): quién (`actor_user_id`), qué acción, sobre qué entidad y cuándo. Se usa para cambios de rol, archivado de grupos, restablecimiento de contraseña, matrícula masiva por CSV, y se reutilizará para aprobaciones de contenido de IA (Fase 6). |

## Fase 2 (migración `002`)

| Tabla | Descripción |
|---|---|
| `languages` | Lista configurable de lenguajes (RF-25) — no está fija en el código; agregar C/C++/Java/PHP es un dato, no un despliegue (RE-06). Único por `(institution_id, slug)`. `syntax_mode` es el identificador que usará el editor (CodeMirror) en la Fase 9. |
| `topics` | Unidades curriculares (RF-07) con `level` (básico/intermedio/avanzado), `order_index` (secuencia sugerida, RF-19) y `version` — los intentos de evaluación de la Fase 3 fijarán la versión contra la que fueron calificados (RE-07), sin necesitar una tabla de historial completa. |
| `topic_group_states` | Estado de un tema **por grupo** (RF-18, RF-22): `locked` / `enabled` / `evaluated`, con `enabled_at` y `scheduled_enable_at` (habilitación programada, RF-24). Único por `(topic_id, group_id)`. La plataforma nunca cambia este estado por su cuenta — solo un docente (o un job que ejecuta una fecha que el docente ya programó) lo hace. |
| `exercises` | Banco reutilizable entre temas y periodos (RF-08). `type` son los 7 tipos de RF-10 (la lógica de calificación por tipo llega en la Fase 3); `content` es un JSON específico por tipo; `origin` (`teacher`/`ai`) y `status` (`draft`/`published`) existen desde ya para que el generador de ejercicios por IA de la Fase 6 (RF-32) tenga dónde aterrizar sin otra migración. |
| `topic_exercises` | Relación muchos-a-muchos entre `topics` y `exercises`: el mismo ejercicio puede reutilizarse en varios temas. |
| `groups.hide_locked_topics` (columna añadida) | Preferencia por grupo: si los temas bloqueados se muestran como "próximamente" (por defecto) o se ocultan del todo para el estudiante (RF-22). |

## Fase 3 (migración `003`)

El motor de calificación por tipo de ejercicio (`modules/grading`) es puro Python (sin tablas propias): un registro de 7 plugins (RF-10, RE-05) que reciben `content` + `answer` y devuelven un `GradeResult` normalizado. Las tablas siguientes son las que persisten evaluaciones e intentos.

| Tabla | Descripción |
|---|---|
| `evaluations` | Una evaluación de un docente para un grupo. `mode` (`fixed`/`cumulative`) + `up_to_topic_id` implementan el alcance de RF-20/21 — validado server-side al crear, nunca confiado del cliente. `duration_minutes` es el cronómetro (RF-11); `is_ranked` activa la tabla de posiciones. |
| `evaluation_exercises` | Ejercicios seleccionados para una evaluación, con `order_index`, `points` (ponderación) y `exercise_version_at_attach` (trazabilidad RE-07). |
| `evaluation_attempts` | Un intento por `(evaluation_id, student_id)` — a diferencia de la práctica libre (RF-09, sin límite), una evaluación tiene un único intento. `status` (`in_progress`/`submitted`/`expired`) y `total_score` se fijan al finalizar y ya no cambian por ediciones posteriores del contenido (RE-07: la calificación se computa una vez y se persiste). |
| `evaluation_answers` | Una respuesta por `(attempt_id, evaluation_exercise_id)` — se puede sobrescribir mientras el intento sigue `in_progress` (autoguardado, §8.2), pero no después de finalizado. `needs_manual_review`/`manual_score`/`reviewed_by_id` sostienen la cola de revisión manual de RF-12. |
| `practice_submissions` | Práctica libre (RF-09): una fila por envío, sin envoltorio de intento ni límite — retroalimentación inmediata (RF-13). |

La tabla de posiciones (RF-11, RE-02) no tiene tabla propia: se cachea en Redis como un *sorted set* (`ranking:{evaluation_id}`), actualizado en cada envío final.

## Fase 4 (migración `004`)

No se agregan tablas nuevas. La migración `004` amplía el enum `exercise_type` con el valor `live_code` (`ALTER TYPE ... ADD VALUE`, imposible de revertir en Postgres — el `downgrade()` es intencionalmente un no-op documentado). El sandbox en sí (`modules/sandbox`) no persiste nada: es un cliente HTTP hacia Piston (self-hosted, perfil `sandbox` de Docker Compose) y un intérprete propio de PSeInt (gramática Lark) que corre en memoria dentro del proceso de la API, acotado por un límite de pasos (`max_steps`) para evitar ciclos infinitos — ver `docs/adr/002-sandbox-fuera-del-registro-sincrono.md`.

## Fase 5 (migración `005`)

| Tabla | Descripción |
|---|---|
| `ai_interactions` | Registro de auditoría de cada llamada al harness de IA (RF-34, §9.1): quién (`user_id`), qué tarea, qué modelo respondió, cuánto costó (`prompt_tokens`/`completion_tokens`), si vino de caché (`from_cache`) o fue bloqueada por un guardrail (`blocked_by_guardrail`), y un campo `approved` (nulo por defecto, usado a partir de la Fase 6 para contenido que requiere aprobación docente — RF-32/RF-33). |
| `rag_documents` | Un documento fuente ingerido como material de referencia para el Agente Tutor (§9.3): apuntes del docente, referencia de PSeInt, etc. |
| `rag_chunks` | Un fragmento embebido de un `rag_document` (columna `embedding`, `vector(384)` vía pgvector — dimensión del modelo `intfloat/multilingual-e5-small`). Sin `institution_id` propio: el aislamiento multi-tenant se hereda del `rag_document` padre, nunca duplicado. |

El harness de IA (`ai/harness/`) no tiene tablas propias más allá de `ai_interactions`: el presupuesto diario por estudiante (§9.1 "control de costos") y la caché de respuestas viven en Redis, no en Postgres — ver `docs/adr/003-harness-como-fachada-unica.md` para el porqué de este diseño y de la recuperación híbrida (vector + texto completo) del RAG.
