import logging

from django.db import transaction
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from booking.models import Booking, Payment

from .services import generate_transaction_id


logger = logging.getLogger(__name__)


class MockPaymentGatewayAPIView(APIView):
    """
    Local mock payment provider used by the booking service
    during development and testing.
    """

    authentication_classes = []
    permission_classes = []

    @transaction.atomic
    def post(self, request):

        booking_id = request.data.get("booking_id")
        amount = request.data.get("amount")
        customer_email = request.data.get("customer_email")

        # -----------------------------------------
        # VALIDATION
        # -----------------------------------------

        if not booking_id or not amount or not customer_email:

            return Response(
                {
                    "success": False,
                    "message": (
                        "booking_id, amount and customer_email "
                        "are required"
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # -----------------------------------------
        # CHECK BOOKING
        # -----------------------------------------

        try:

            booking = Booking.objects.get(
                id=booking_id
            )

        except Booking.DoesNotExist:

            return Response(
                {
                    "success": False,
                    "message": "Booking not found",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        # -----------------------------------------
        # MOCK FAILURE
        # -----------------------------------------

        if str(customer_email).lower().endswith("@fail.test"):

            logger.warning(
                "Mock payment declined booking=%s email=%s",
                booking_id,
                customer_email,
            )

            return Response(
                {
                    "success": False,
                    "message": "Mock payment declined",
                },
                status=status.HTTP_200_OK,
            )

        # -----------------------------------------
        # SUCCESS
        # -----------------------------------------

        transaction_id = generate_transaction_id()

        logger.info(
            "Mock payment successful booking=%s transaction=%s",
            booking_id,
            transaction_id,
        )

        return Response(
            {
                "success": True,
                "transaction_id": transaction_id,
                "message": "Mock payment successful",
            },
            status=status.HTTP_200_OK,
        )


class PaymentWebhookAPIView(APIView):
    """
    Handles payment success/failure webhook events.
    """

    authentication_classes = []
    permission_classes = []

    @transaction.atomic
    def post(self, request):

        transaction_id = request.data.get(
            "transaction_id"
        )

        event = request.data.get(
            "event"
        )

        # -----------------------------------------
        # VALIDATION
        # -----------------------------------------

        if (
            not transaction_id
            or event not in {
                "payment.success",
                "payment.failed",
            }
        ):

            return Response(
                {
                    "detail": (
                        "transaction_id and a valid "
                        "payment event are required."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # -----------------------------------------
        # FIND PAYMENT
        # -----------------------------------------

        try:

            payment = (
                Payment.objects
                .select_for_update()
                .select_related("booking")
                .get(
                    transaction_id=transaction_id
                )
            )

        except Payment.DoesNotExist:

            return Response(
                {
                    "detail": "Payment not found."
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        # -----------------------------------------
        # SUCCESS
        # -----------------------------------------

        if event == "payment.success":

            payment.status = Payment.Status.SUCCESS

            payment.booking.status = (
                Booking.Status.CONFIRMED
            )

        # -----------------------------------------
        # FAILURE
        # -----------------------------------------

        else:

            payment.status = Payment.Status.FAILED

            payment.booking.status = (
                Booking.Status.PAYMENT_FAILED
            )

        # -----------------------------------------
        # PROVIDER MESSAGE
        # -----------------------------------------

        payment.provider_message = request.data.get(
            "message",
            "Webhook processed",
        )[:255]

        # -----------------------------------------
        # SAVE PAYMENT
        # -----------------------------------------

        payment.save(
            update_fields=[
                "status",
                "provider_message",
                "updated_at",
            ]
        )

        # -----------------------------------------
        # SAVE BOOKING
        # -----------------------------------------

        payment.booking.save(
            update_fields=[
                "status",
                "updated_at",
            ]
        )

        logger.info(
            "Payment webhook processed "
            "transaction=%s event=%s",
            transaction_id,
            event,
        )

        return Response(
            {
                "detail": "Webhook processed."
            },
            status=status.HTTP_200_OK,
        )