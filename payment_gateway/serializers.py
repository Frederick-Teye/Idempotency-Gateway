from rest_framework import serializers
from decimal import Decimal


class PaymentSerializer(serializers.Serializer):
    """
    Serializer for payment requests.
    Validates that amount and currency are provided.
    """

    amount = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=True,
        min_value=Decimal("0.01"),
    )
    currency = serializers.CharField(
        max_length=3, required=True, help_text="ISO 4217 currency code (e.g., GHS, USD)"
    )

    def validate_currency(self, value):
        """Validate currency code is 3 uppercase letters"""
        if not value.isalpha() or len(value) != 3:
            raise serializers.ValidationError(
                "Currency must be a 3-letter ISO code (e.g., GHS, USD)"
            )
        return value.upper()
