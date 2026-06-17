import asyncio
import uuid
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.db import IntegrityError
from asgiref.sync import sync_to_async

from .models import IdempotencyRecord
from .serializers import PaymentSerializer


class PaymentCreateView(APIView):
    """
    API view for processing FinSafe payments with idempotency support.
    """

    permission_classes = [IsAuthenticated]

    async def post(self, request, *args, **kwargs):
        idem_key = request.headers.get("Idempotency-Key")
        if not idem_key:
            return Response(
                {"error": "Idempotency-Key header is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            # Enforce UUIDv4 format to prevent weak keys
            uuid.UUID(idem_key, version=4)
        except ValueError:
            return Response(
                {"error": "Idempotency-Key must be a valid UUIDv4"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = PaymentSerializer(data=request.data)
        # raise_exception=True automatically returns a 400 response if invalid.
        serializer.is_valid(raise_exception=True)

        validated_data = serializer.validated_data
        request_body = {
            "amount": str(validated_data["amount"]),
            "currency": validated_data["currency"],
        }

        existing_record = await sync_to_async(
            lambda: IdempotencyRecord.objects.filter(
                user=request.user, key=idem_key
            ).first()
        )()

        if existing_record:
            if existing_record.request_body != request_body:
                return Response(
                    {
                        "error": "Idempotency key already used for a different request body."
                    },
                    status=status.HTTP_422_UNPROCESSABLE_ENTITY,
                )

            await self._wait_for_in_flight_request(existing_record, max_wait=10)

            return self._build_cached_response(existing_record)

        try:
            idempotency_record = await sync_to_async(IdempotencyRecord.objects.create)(
                user=request.user,
                key=idem_key,
                request_body=request_body,
                status_code=201,
                response_body={},
                processing_completed=False,
            )
        except IntegrityError:
            # If two exact requests hit this line at the same millisecond,
            # the database's unique constraint will throw an IntegrityError for one of them.
            existing_record = await sync_to_async(
                lambda: IdempotencyRecord.objects.get(user=request.user, key=idem_key)
            )()
            await self._wait_for_in_flight_request(existing_record, max_wait=10)
            return self._build_cached_response(existing_record)

        try:
            await asyncio.sleep(2)

            response_body = {
                "status": "success",
                "message": f"Charged {validated_data['amount']} {validated_data['currency']}",
                "amount": str(validated_data["amount"]),
                "currency": validated_data["currency"],
                "idempotency_key": idem_key,
            }

            idempotency_record.response_body = response_body
            idempotency_record.status_code = status.HTTP_201_CREATED
            idempotency_record.processing_completed = True
            await sync_to_async(idempotency_record.save)()

            return Response(response_body, status=status.HTTP_201_CREATED)

        except Exception as e:
            # If the payment processing crashes, delete the
            # pending record so the user is not permanently locked out from retrying.
            await sync_to_async(idempotency_record.delete)()
            raise e

    async def _wait_for_in_flight_request(self, record, max_wait=5):
        """Polls the DB briefly if another request is currently processing this key."""
        if not record.processing_completed:
            waited = 0
            while not record.processing_completed and waited < max_wait:
                await asyncio.sleep(0.1)
                waited += 0.1
                await sync_to_async(record.refresh_from_db)()

    def _build_cached_response(self, record):
        """Returns the saved response with the X-Cache-Hit header."""
        response = Response(record.response_body, status=record.status_code)
        response["X-Cache-Hit"] = "true"
        return response
