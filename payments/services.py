import logging
import uuid

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class PaymentGatewayError(Exception):
    pass


class PaymentService:
    def __init__(self, url=None, timeout=None):
        self.url = url or settings.MOCK_PAYMENT_URL
        self.timeout = timeout or settings.PAYMENT_TIMEOUT_SECONDS

    def charge(self, *, booking_id, amount, customer_email):
        payload = {
            "booking_id": booking_id,
            "amount": str(amount),
            "customer_email": customer_email,
        }
        try:
            response = requests.post(self.url, json=payload, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise PaymentGatewayError(f"Payment provider request failed: {exc}") from exc

        if "success" not in data:
            raise PaymentGatewayError("Payment provider returned an invalid response.")

        return data


def generate_transaction_id():
    return f"MOCK-{uuid.uuid4().hex[:16].upper()}"
