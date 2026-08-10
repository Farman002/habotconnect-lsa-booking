from datetime import date, time, timedelta
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from booking.models import LSAProfile, Parent, Skill


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def parent(db):
    return Parent.objects.create(name="Test Parent", email="parent@example.com")


@pytest.fixture
def lsa(db):
    python = Skill.objects.create(name="Python")
    math = Skill.objects.create(name="Math")
    profile = LSAProfile.objects.create(
        name="Test LSA",
        email="lsa@example.com",
        hourly_rate=Decimal("500.00"),
    )
    profile.skills.add(python, math)
    return profile


@pytest.fixture
def booking_payload(parent, lsa):
    tomorrow = date.today() + timedelta(days=1)
    return {
        "parent_id": parent.id,
        "lsa_id": lsa.id,
        "session_date": tomorrow.isoformat(),
        "start_time": "10:00:00",
        "end_time": "11:00:00",
        "idempotency_key": "booking-test-1",
    }
