import logging
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Count
from django.utils import timezone

from rewards.models import Reward


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Audit rewards that have been claimed for more than 7 days."

    def add_arguments(self, parser):
        parser.add_argument(
            "--fix",
            action="store_true",
            help="Mark stale claimed rewards as expired.",
        )

    def handle(self, *args, **options):
        fix = options["fix"]
        cutoff = timezone.now() - timedelta(days=7)

        stale_rewards = Reward.objects.filter(
            status="claimed",
            claimed_at__lt=cutoff,
        )

        summary = (
            stale_rewards
            .values("reward_type")
            .annotate(count=Count("id"))
            .order_by("reward_type")
        )

        total = sum(item["count"] for item in summary)

        self.stdout.write(f"Found {total} stale reward(s).")

        for item in summary:
            self.stdout.write(
                f"{item['reward_type']}: {item['count']}"
            )

        if not fix:
            return

        expires_at = timezone.now()

        with transaction.atomic():
            for reward in stale_rewards.iterator(chunk_size=1000):
                reward.status = "expired"
                reward.expires_at = expires_at
                reward.save(
                    update_fields=["status", "expires_at"]
                )

                logger.info(
                    "Expired stale reward %s",
                    reward.id,
                )

        self.stdout.write(
            f"Expired {total} stale reward(s)."
        )