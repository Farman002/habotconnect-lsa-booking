from unittest.mock import patch

import pytest

from booking.models import Booking, Payment


@pytest.mark.django_db
def test_payment_webhook_confirms_booking(api_client, parent, lsa, booking_payload):
    booking_payload.pop("idempotency_key")
    with patch("payments.services.requests.post") as mocked_post:
        mocked_post.return_value.raise_for_status.return_value = None
        mocked_post.return_value.json.return_value = {"success": True, "transaction_id": "MOCK-WEB", "message": "ok"}
        response = api_client.post("/api/v1/bookings/", {**booking_payload, "idempotency_key": "webhook-booking"}, format="json")
    assert response.status_code in {201, 402}
    booking = Booking.objects.get(pk=response.data["id"])
    payment = Payment.objects.get(booking=booking)

    # The normal mock provider already confirms it; webhook is idempotent for the state transition.
    payment.transaction_id = "TXN-WEBHOOK"
    payment.save(update_fields=["transaction_id"])
    booking.status = Booking.Status.PAYMENT_FAILED
    booking.save(update_fields=["status"])

    webhook = api_client.post(
        "/api/v1/payments/webhook/",
        {"transaction_id": "TXN-WEBHOOK", "event": "payment.success", "message": "settled"},
        format="json",
    )
    assert webhook.status_code == 200
    booking.refresh_from_db()
    payment.refresh_from_db()
    assert booking.status == Booking.Status.CONFIRMED
    assert payment.status == Payment.Status.SUCCESS
