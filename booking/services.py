import logging

from django.db import transaction

from payments.services import PaymentGatewayError, PaymentService

from .models import Booking, Payment

logger = logging.getLogger(__name__)


class BookingService:
    @staticmethod
    @transaction.atomic
    def process_payment(booking_id):
        booking = Booking.objects.select_for_update().select_related("parent", "lsa").get(pk=booking_id)
        payment, _ = Payment.objects.get_or_create(
            booking=booking,
            defaults={"amount": booking.amount, "status": Payment.Status.PENDING},
        )

        if booking.status == Booking.Status.CONFIRMED:
            return booking

        try:
            result = PaymentService().charge(
                booking_id=booking.id,
                amount=booking.amount,
                customer_email=booking.parent.email,
            )
        except PaymentGatewayError as exc:
            logger.exception("Payment gateway failed for booking=%s", booking.id)
            payment.status = Payment.Status.FAILED
            payment.provider_message = str(exc)[:255]
            payment.save(update_fields=["status", "provider_message", "updated_at"])
            booking.status = Booking.Status.PAYMENT_FAILED
            booking.save(update_fields=["status", "updated_at"])
            return booking

        payment.status = Payment.Status.SUCCESS if result["success"] else Payment.Status.FAILED
        payment.transaction_id = result.get("transaction_id")
        payment.provider_message = result.get("message", "")[:255]
        payment.save()

        booking.status = Booking.Status.CONFIRMED if result["success"] else Booking.Status.PAYMENT_FAILED
        booking.save(update_fields=["status", "updated_at"])
        return booking
