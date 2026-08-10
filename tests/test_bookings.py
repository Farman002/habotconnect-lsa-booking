from unittest.mock import patch

import pytest
from rest_framework import status

from booking.models import Booking, Payment


@pytest.mark.django_db
def test_create_booking_success(api_client, booking_payload):
    with patch("payments.services.requests.post") as mocked_post:
        mocked_post.return_value.raise_for_status.return_value = None
        mocked_post.return_value.json.return_value = {
            "success": True,
            "transaction_id": "MOCK-123",
            "message": "ok",
        }
        response = api_client.post("/api/v1/bookings/", booking_payload, format="json")

    assert response.status_code == status.HTTP_201_CREATED
    booking = Booking.objects.get(id=response.data["id"])
    assert booking.status == Booking.Status.CONFIRMED
    assert Payment.objects.get(booking=booking).status == Payment.Status.SUCCESS


@pytest.mark.django_db
def test_reject_invalid_time_range(api_client, booking_payload):
    booking_payload["start_time"] = "11:00:00"
    booking_payload["end_time"] = "10:00:00"
    response = api_client.post("/api/v1/bookings/", booking_payload, format="json")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "end_time" in response.data


@pytest.mark.django_db
def test_reject_overlapping_booking(api_client, booking_payload):
    first_payload = dict(booking_payload)
    with patch("payments.services.requests.post") as mocked_post:
        mocked_post.return_value.raise_for_status.return_value = None
        mocked_post.return_value.json.return_value = {
            "success": True,
            "transaction_id": "MOCK-ONE",
            "message": "ok",
        }
        first = api_client.post("/api/v1/bookings/", first_payload, format="json")
        assert first.status_code == status.HTTP_201_CREATED

    second_payload = dict(booking_payload)
    second_payload["start_time"] = "10:30:00"
    second_payload["end_time"] = "11:30:00"
    second_payload["idempotency_key"] = "booking-test-2"
    response = api_client.post("/api/v1/bookings/", second_payload, format="json")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "booking" in response.data


@pytest.mark.django_db
@patch("payments.services.requests.post")
def test_payment_failure_transitions_booking(mocked_post, api_client, booking_payload):
    mocked_post.return_value.raise_for_status.return_value = None
    mocked_post.return_value.json.return_value = {
        "success": False,
        "message": "declined",
    }
    response = api_client.post("/api/v1/bookings/", booking_payload, format="json")
    assert response.status_code == status.HTTP_402_PAYMENT_REQUIRED
    assert response.data["status"] == Booking.Status.PAYMENT_FAILED


@pytest.mark.django_db
@patch("payments.services.requests.post")
def test_payment_gateway_exception_is_handled(mocked_post, api_client, booking_payload):
    import requests
    mocked_post.side_effect = requests.Timeout("provider timeout")
    response = api_client.post("/api/v1/bookings/", booking_payload, format="json")
    assert response.status_code == status.HTTP_402_PAYMENT_REQUIRED
    assert response.data["status"] == Booking.Status.PAYMENT_FAILED
