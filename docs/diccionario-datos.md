# Diccionario de datos

Se completa incrementalmente a medida que cada fase introduce sus modelos (ver migraciones en `apps/api/alembic/versions/`). Cada tabla nueva debe documentarse aquí en la misma fase que la introduce.

## Fase 0

| Tabla / extensión | Descripción |
|---|---|
| `vector` (extensión) | Extensión de PostgreSQL (pgvector) habilitada en la migración `000` para soportar embeddings del RAG pedagógico (Fase 5). |
