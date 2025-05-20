#!/usr/bin/env bash
set -e

echo "Migrating…"
python manage.py migrate --noinput

echo "Collecting static files…"
python manage.py collectstatic --noinput

echo "Starting Gunicorn on port ${PORT:-8000}…"
exec gunicorn core.wsgi:application \
  --bind 0.0.0.0:${PORT:-8000} \
  --workers 3
