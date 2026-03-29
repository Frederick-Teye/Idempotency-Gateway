from django.db import models
from django.conf import settings


class IdempotencyRecord(models.Model):
    """
    Stores idempotency records for payment requests.

    This model ensures that duplicate requests with the same Idempotency-Key
    return the cached response without reprocessing.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        db_index=True,
        help_text="The user who made the payment request",
    )
    key = models.CharField(
        max_length=255,
        db_index=True,
        help_text="Unique idempotency key from request header",
    )
    request_body = models.JSONField(
        help_text="The original request body for validation on retries"
    )
    response_body = models.JSONField(
        help_text="The cached response body to return on duplicate requests"
    )
    status_code = models.IntegerField(
        help_text="HTTP status code of the original response"
    )
    created_at = models.DateTimeField(
        auto_now_add=True, help_text="Timestamp when this record was created"
    )
    processing_completed = models.BooleanField(
        default=False, help_text="Flag to handle race conditions (in-flight requests)"
    )

    class Meta:
        unique_together = ("user", "key")
        indexes = [
            models.Index(fields=["user", "key"]),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.key}"
