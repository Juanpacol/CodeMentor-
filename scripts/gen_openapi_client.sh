#!/usr/bin/env bash
# Genera los tipos TypeScript del cliente del frontend a partir del OpenAPI
# que expone la API real corriendo (Fase 9). El archivo generado se commitea
# — el build del frontend en CI no depende de tener la API levantada.
set -euo pipefail

API_URL="${API_URL:-http://localhost:8000}"
OUT="apps/web/src/lib/api/schema.d.ts"

cd "$(dirname "$0")/.."

echo "Generando ${OUT} desde ${API_URL}/openapi.json ..."
npx --prefix apps/web openapi-typescript "${API_URL}/openapi.json" -o "${OUT}"
echo "Listo."
