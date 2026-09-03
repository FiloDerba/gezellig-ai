"""Gunicorn WSGI server configuration."""

from os import environ

bind = "0.0.0.0:" + environ.get("PORT", "8000")
workers = int(environ.get("GUNICORN_WORKERS", "4"))
threads = int(environ.get("GUNICORN_THREADS", "2"))
timeout = int(environ.get("GUNICORN_TIMEOUT", "120"))
keepalive = 5
preload_app = True
daemon = False
errorlog = "-"
accesslog = "-"
loglevel = environ.get("GUNICORN_LOG_LEVEL", "info")
