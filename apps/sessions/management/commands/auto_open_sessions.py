"""
Management command: auto_open_sessions

Re-opens eligible closed sessions whose scheduled_at time has passed.
Intended to be run periodically (e.g., every minute via cron or a scheduler).

Usage:
    python manage.py auto_open_sessions
"""

from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from apps.sessions.models import Session


class Command(BaseCommand):
    help = "Re-open eligible closed sessions whose scheduled_at time has passed."

    def handle(self, *args, **options):
        now = timezone.now()
        sessions_to_open = Session.objects.filter(
            state=Session.State.CLOSED,
            scheduled_at__lte=now,
        ).filter(
            Q(auto_close_at__isnull=True) | Q(auto_close_at__gt=now),
        )
        count = sessions_to_open.count()
        for session in sessions_to_open:
            session.open()
            self.stdout.write(f"  Opened session #{session.pk}: {session.name}")

        self.stdout.write(
            self.style.SUCCESS(f"auto_open_sessions: opened {count} session(s).")
        )
