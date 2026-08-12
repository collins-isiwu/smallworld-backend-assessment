from django.db import models

class Reward(models.Model):
    class Status(models.TextChoices):
        CLAIMED = "claimed", "Claimed"
        EXPIRED = "expired", "Expired"

    reward_type = models.CharField(max_length=50)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
    )
    claimed_at = models.DateTimeField()
    expires_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Reward {self.pk} - {self.reward_type}"