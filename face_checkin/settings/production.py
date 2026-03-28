"""
Production settings — extends base.
"""

from .base import *  # noqa: F401, F403

# Security hardening
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# Trust the proxy (Cloudflared) for the original protocol
# This tells Django that X-Forwarded-Proto: https means the original request was HTTPS
# Required to avoid redirect loops when running behind Cloudflared
USE_X_FORWARDED_HOST = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# CSRF trusted origins - comma-separated list of HTTPS origins
# Example: CSRF_TRUSTED_ORIGINS=https://example.com,https://www.example.com
_csrf_origins = env("CSRF_TRUSTED_ORIGINS", default="")
CSRF_TRUSTED_ORIGINS = (
    [origin.strip() for origin in _csrf_origins.split(",") if origin.strip()]
    if _csrf_origins
    else []
)
