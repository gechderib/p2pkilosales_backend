#!/bin/sh

# Run migrations
echo "Running migrations..."
python manage.py makemigrations
python manage.py migrate

# Create superuser
echo "Creating superuser..."
python manage.py create_superuser

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput --clear

# Start Uvicorn
echo "Starting Uvicorn ..."
exec uvicorn config.asgi:application --host 0.0.0.0 --port 8000 --ws-max-size 2097152 

# daphne -b 0.0.0.0 -p 8000 config.asgi:application
# uvicorn config.asgi:application --host 0.0.0.0 --port 8000 --ws-max-size 2097152 