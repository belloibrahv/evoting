#!/bin/bash
# Render startup script
# Runs DB init then starts gunicorn
set -e

echo "==> Running database setup..."
python scripts/init_db.py

echo "==> Starting gunicorn..."
exec gunicorn "run:app" \
  --workers 2 \
  --threads 2 \
  --timeout 60 \
  --bind "0.0.0.0:${PORT:-10000}" \
  --access-logfile - \
  --error-logfile -
