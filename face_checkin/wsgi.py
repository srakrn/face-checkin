"""
WSGI config for face_checkin project.
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "face_checkin.settings.production")

application = get_wsgi_application()
