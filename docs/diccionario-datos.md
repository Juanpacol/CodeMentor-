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
