#!/bin/sh

# # Wait for Postgres
# echo "Waiting for database..."
# while ! nc -z db 5432; do
#   echo "Postgres is unavailable - sleeping"
#   sleep 1
# done
# echo "Postgres is up - continuing"

# Run migrations
echo "Running migrations..."
python manage.py makemigrations
python manage.py migrate

# Create superuser
echo "Creating superuser..."
python manage.py createsuperuser --noinput --username admin --email admin@example.com || true

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput --clear

# # Start Celery worker and beat in the background
# echo "Starting Celery worker and beat..."
# celery -A config worker -B -l info &

# Start Daphne
echo "Starting Daphne ..."
exec daphne -b 0.0.0.0 -p 8000 config.asgi:application
