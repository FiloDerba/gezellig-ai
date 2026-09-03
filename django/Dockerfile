# Built from the repository root, because pyproject.toml and the Streamlit client live there.
#   docker compose -f django/docker-compose.yaml build
FROM python:3.14-slim

WORKDIR /app

# Non-root user with an explicit UID (required for K8s runAsNonRoot)
RUN addgroup --system --gid 1000 usr && adduser --system --uid 1000 --gid 1000 usr

# Keeps Python from generating .pyc files and from buffering stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    # Install into the system interpreter, so `python manage.py` needs no `uv run`
    UV_PROJECT_ENVIRONMENT=/usr/local \
    UV_COMPILE_BYTECODE=1

RUN pip install --no-cache-dir -U uv

# Dependencies resolve from the lockfile first, so code edits don't reinstall the world.
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --frozen --extra deploy --group dev --no-editable

COPY --chown=usr:usr django ./django
COPY --chown=usr:usr .streamlit ./.streamlit
RUN chmod +x django/entrypoint.sh

# manage.py sets this itself; declaring it here also covers plain `python` and gunicorn.
ENV DJANGO_SETTINGS_MODULE=backend.settings \
    PYTHONPATH=/app/django

WORKDIR /app/django

# Bake the admin's CSS/JS into the image; collectstatic does not touch the database.
RUN python manage.py collectstatic --noinput

USER 1000

EXPOSE 8000
CMD ["bash", "entrypoint.sh"]
