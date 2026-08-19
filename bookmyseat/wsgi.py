"""
WSGI config for bookmyseat project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.1/howto/deployment/wsgi/
"""

import os
import shutil
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Guarantee SQLite database copy to /tmp for Vercel Serverless environment
if os.path.exists('/var/task') or os.environ.get('VERCEL') or os.environ.get('LAMBDA_TASK_ROOT'):
    db_path = BASE_DIR / 'db.sqlite3'
    tmp_db_path = '/tmp/db.sqlite3'
    if os.path.exists(db_path) and not os.path.exists(tmp_db_path):
        try:
            shutil.copyfile(str(db_path), tmp_db_path)
        except Exception:
            pass

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bookmyseat.settings')

from django.core.wsgi import get_wsgi_application

application = get_wsgi_application()
app = application