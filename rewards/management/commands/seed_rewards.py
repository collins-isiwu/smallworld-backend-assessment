from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from rewards.models import Reward


class Command(BaseCommand):
    help = "Create sample rewards for testing."

    def handle(self, *args, **options):
        now = timezone.now()

        sample_rewards = [
            Reward(
                reward_type="cash",
                status="claimed",
                claimed_at=now - timedelta(days=10),
            ),
            Reward(
                reward_type="cash",
                status="claimed",
                claimed_at=now - timedelta(days=8),
            ),
            Reward(
                reward_type="voucher",
                status="claimed",
                claimed_at=now - timedelta(days=12),
            ),
            Reward(
                reward_type="cash",
                status="claimed",
                claimed_at=now - timedelta(days=2),
            ),
            Reward(
                reward_type="voucher",
                status="expired",
                claimed_at=now - timedelta(days=15),
                expires_at=now - timedelta(days=8),
            ),
        ]

        Reward.objects.bulk_create(sample_rewards)

        self.stdout.write(
            self.style.SUCCESS(
                f"Created {len(sample_rewards)} sample rewards."
            )
        )