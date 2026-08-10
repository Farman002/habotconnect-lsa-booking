from datetime import date, timedelta

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from booking.models import Booking


@pytest.mark.django_db
def test_lsa_search_filters_by_all_requested_skills(api_client, lsa):
    response = api_client.get("/api/v1/lsas/search/?skills=Python,Math")
    assert response.status_code == 200
    assert response.data["count"] == 1
    assert response.data["results"][0]["id"] == lsa.id
    assert set(response.data["results"][0]["skills"]) == {"Python", "Math"}


@pytest.mark.django_db
def test_lsa_search_excludes_overlapping_lsa(api_client, lsa, parent):
    Booking.objects.create(
        parent=parent,
        lsa=lsa,
        session_date=date.today() + timedelta(days=1),
        start_time="10:00",
        end_time="11:00",
        amount=500,
        status=Booking.Status.CONFIRMED,
    )
    response = api_client.get(
        "/api/v1/lsas/search/?skills=Python&session_date="
        f"{(date.today() + timedelta(days=1)).isoformat()}&start_time=10:30:00&end_time=11:30:00"
    )
    assert response.status_code == 200
    assert response.data["count"] == 0


@pytest.mark.django_db
def test_lsa_serializer_does_not_create_n_plus_one_skill_queries(api_client, lsa):
    # Create a few additional profiles sharing the same skill set.
    for i in range(5):
        profile = lsa.__class__.objects.create(
            name=f"LSA {i}",
            email=f"lsa{i}@example.com",
            hourly_rate=500,
        )
        profile.skills.set(lsa.skills.all())

    with CaptureQueriesContext(connection) as ctx:
        response = api_client.get("/api/v1/lsas/search/?skills=Python")

    assert response.status_code == 200
    # The exact count can vary by Django version, but it must not grow one query per result.
    assert len(ctx.captured_queries) < 10


import pytest

from django.db import connection
from django.test.utils import CaptureQueriesContext

from booking.models import LSAProfile


@pytest.mark.django_db
def test_lsa_search_query_count_is_bounded(
    api_client,
    lsa,
):
    # ---------------------------------------------
    # First request
    # ---------------------------------------------

    with CaptureQueriesContext(connection) as queries_small:

        response = api_client.get(
            "/api/v1/lsas/search/?skills=Python"
        )

        response.data

    assert response.status_code == 200

    small_query_count = len(queries_small)

    # ---------------------------------------------
    # Add more LSAs
    # ---------------------------------------------

    for index in range(10):

        extra_lsa = LSAProfile.objects.create(
            name=f"Extra LSA {index}",
            email=f"extra{index}@example.com",
            hourly_rate=400,
            is_active=True,
        )

        # Give them the same Python skill as the fixture LSA.
        extra_lsa.skills.add(*lsa.skills.all())

    # ---------------------------------------------
    # Second request
    # ---------------------------------------------

    with CaptureQueriesContext(connection) as queries_large:

        response = api_client.get(
            "/api/v1/lsas/search/?skills=Python"
        )

        response.data

    assert response.status_code == 200

    large_query_count = len(queries_large)

    # ---------------------------------------------
    # N+1 protection
    # ---------------------------------------------

    assert large_query_count <= small_query_count + 1