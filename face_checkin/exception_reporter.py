"""
Custom exception reporter filter.

When a request is made by an authenticated superuser, always show the full
Django debug error page — regardless of the DEBUG setting.  For all other
requests the standard SafeExceptionReporterFilter is used, which hides
sensitive data and respects DEBUG=False.
"""

from django.views.debug import SafeExceptionReporterFilter


class SuperuserDebugExceptionReporterFilter(SafeExceptionReporterFilter):
    """Show full debug info to superusers; behave normally for everyone else."""

    def is_active(self, request):
        # If a superuser is making the request, always show the debug page.
        if request is not None:
            user = getattr(request, "user", None)
            if user is not None and getattr(user, "is_active", False) and getattr(user, "is_superuser", False):
                return False  # False → "filter is NOT active" → full debug info shown
        # Fall back to the default behaviour (respects DEBUG setting).
        return super().is_active(request)
