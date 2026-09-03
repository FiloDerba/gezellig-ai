#!/bin/bash
set -e

cmd=${1:-web}

echo "Running with command: $cmd"

wait_for_database() {
    echo "Waiting for the database..."
    python - <<'PY'
import time

import django
from django.db import connection
from django.db.utils import OperationalError

django.setup()
for attempt in range(30):
    try:
        connection.ensure_connection()
    except OperationalError as exc:
        print(f"  not ready ({exc.__class__.__name__}), retrying...")
        connection.close()
        time.sleep(2)
    else:
        print("  database is up")
        break
else:
    raise SystemExit("Database never became available")
PY
}

run_migrations() {
    echo "Applying database migrations..."
    python manage.py migrate --noinput
}

create_superuser() {
    if [ -n "$DJANGO_SUPERUSER_USERNAME" ] && [ -n "$DJANGO_SUPERUSER_PASSWORD" ]; then
        echo "Creating superuser if not exists..."
        python manage.py createsuperuser --noinput 2>/dev/null || true
    fi
}

seed_sample_deck() {
    # Only fires on an empty deck, so a real import is never overwritten.
    if [ "$LOAD_SAMPLE_DECK" = "True" ]; then
        echo "Loading the sample deck if the database is empty..."
        python manage.py shell -c "
from vocabulary.models import Word
from vocabulary.sample_deck import load_sample_words
print('added', load_sample_words() if not Word.objects.exists() else 0, 'sample word(s)')
"
    fi
}

if [ "$cmd" = "dev" ]; then
    wait_for_database
    run_migrations
    create_superuser
    seed_sample_deck
    exec python manage.py runserver 0.0.0.0:"${PORT:-8000}"

elif [ "$cmd" = "web" ]; then
    wait_for_database
    run_migrations
    create_superuser
    exec gunicorn -c gunicorn_config.py backend.wsgi

elif [ "$cmd" = "streamlit" ]; then
    # Run from the repo root so .streamlit/config.toml (dark theme, orange accent) applies.
    cd /app
    exec streamlit run src/dutch_learning/app.py \
        --server.address 0.0.0.0 \
        --server.port "${STREAMLIT_PORT:-8501}" \
        --server.headless true

elif [ "$cmd" = "test" ]; then
    echo "Running tests..."
    cd /app && exec pytest

elif [ "$cmd" = "migrate" ]; then
    wait_for_database
    run_migrations

elif [ "$cmd" = "shell" ]; then
    exec python manage.py shell

else
    echo "Unknown command: $cmd"
    echo "Available commands: dev, web, streamlit, test, migrate, shell"
    exit 1
fi
