from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from payment_gateway.models import IdempotencyRecord


class Command(BaseCommand):
    help = "Delete expired idempotency records based on TTL"

    def add_arguments(self, parser):
        parser.add_argument(
            "--ttl",
            type=int,
            default=604800,
            help="Time to live in seconds (default: 604800 = 1 week)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be deleted without actually deleting",
        )

    def handle(self, *args, **options):
        ttl_seconds = options["ttl"]
        dry_run = options["dry_run"]

        cutoff_time = timezone.now() - timedelta(seconds=ttl_seconds)

        expired_records = IdempotencyRecord.objects.filter(created_at__lt=cutoff_time)
        count = expired_records.count()

        if count == 0:
            self.stdout.write(self.style.SUCCESS("No expired records to delete"))
            return

        if dry_run:
            self.stdout.write(
                self.style.WARNING(f"[DRY RUN] Would delete {count} expired record(s)")
            )
            for record in expired_records[:10]:
                self.stdout.write(
                    f"  - User: {record.user.email}, Key: {record.key}, Created: {record.created_at}"
                )
            if count > 10:
                self.stdout.write(f"  ... and {count - 10} more")
        else:
            expired_records.delete()
            self.stdout.write(
                self.style.SUCCESS(f"Deleted {count} expired record(s)")
            )
