"""Configure Django so its ORM can be used from inside the Streamlit process.

Importing this module has the side effect of calling `django.setup()`, which must happen
before anything imports `vocabulary.*`. It is a no-op when Django is already configured,
so running under pytest or `manage.py` changes nothing.
"""

import os
import sys
from pathlib import Path

# src/dutch_learning/django_bootstrap.py -> repository root
REPO_ROOT = Path(__file__).resolve().parents[2]
DJANGO_DIR = REPO_ROOT / "django"


def setup() -> None:
    if str(DJANGO_DIR) not in sys.path:
        sys.path.insert(0, str(DJANGO_DIR))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")

    from django.apps import apps

    import django

    if not apps.ready:
        django.setup()


setup()
