"""Publish due GoreeCloud Tasks reminders through the configured ntfy service."""

from django.core.management.base import BaseCommand, CommandError

from notifications.services import dispatch_due_reminders


class Command(BaseCommand):
    help = "Send due user-specific task reminders through the configured ntfy publisher."

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=100,
            help="Maximum due reminders to process in one run (default: 100).",
        )

    def handle(self, *args, **options):
        limit = options["limit"]
        if limit < 1 or limit > 1000:
            raise CommandError("--limit must be between 1 and 1000.")

        summary = dispatch_due_reminders(limit=limit)
        self.stdout.write(
            "Reminder dispatch: "
            f"candidates={summary.candidates} "
            f"sent={summary.sent} "
            f"cancelled={summary.cancelled} "
            f"failed={summary.failed}"
        )
        if summary.failed:
            raise CommandError(
                f"{summary.failed} reminder publication(s) failed; pending reminders were retained for retry."
            )
