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
