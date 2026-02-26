"""
Management command: auto_close_sessions

Closes all active sessions whose auto_close_at time has passed.
Intended to be run periodically (e.g., every minute via cron or a scheduler).

Usage:
    python manage.py auto_close_sessions
"""

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.sessions.models import Session


class Command(BaseCommand):
    help = "Close all active sessions whose auto_close_at time has passed."

    def handle(self, *args, **options):
        now = timezone.now()
        sessions_to_close = Session.objects.filter(
            state=Session.State.ACTIVE,
            auto_close_at__lte=now,
        )
        count = sessions_to_close.count()
        for session in sessions_to_close:
            session.close()
            self.stdout.write(f"  Closed session #{session.pk}: {session.name}")

        self.stdout.write(
            self.style.SUCCESS(f"auto_close_sessions: closed {count} session(s).")
        )
