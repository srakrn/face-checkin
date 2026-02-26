"""
Development settings — extends base.
"""

from .base import *  # noqa: F401, F403

DEBUG = True

INSTALLED_APPS += [  # noqa: F405
    "debug_toolbar",
]

MIDDLEWARE = [
    "debug_toolbar.middleware.DebugToolbarMiddleware",
] + MIDDLEWARE  # noqa: F405

INTERNAL_IPS = ["127.0.0.1"]

# Use console email backend in development
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
