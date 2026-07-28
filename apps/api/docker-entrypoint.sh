#!/bin/sh
# Arranque de la API en Render (free tier). El preDeployCommand de Render es solo
# para planes pagos, así que las migraciones corren acá, antes de uvicorn — el free
# tier corre una sola instancia, así que no hay carrera entre réplicas migrando en
# paralelo. Si algún día se escala a varias, esto debe moverse a un preDeployCommand.
set -e

echo "entrypoint: aplicando migraciones"
alembic upgrade head

# El seed es idempotente (chequea la institución demo antes de crearla), pero se deja
# detrás de un flag para no sumar segundos al cold start en cada arranque.
if [ "$RUN_SEED_ON_START" = "true" ]; then
  echo "entrypoint: RUN_SEED_ON_START=true, sembrando datos demo"
  python scripts/seed.py
fi

exec uvicorn logica.main:app --host 0.0.0.0 --port 8000
