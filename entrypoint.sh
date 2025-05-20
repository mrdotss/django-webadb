#!/usr/bin/env bash
set -e

echo "Migrating…"
python manage.py showmigrations
python manage.py migrate

echo "Collecting static files…"
python manage.py collectstatic --noinput

echo "Starting Gunicorn…"
exec "$@"
