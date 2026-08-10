from django.db.models import Count, Q

from .models import LSAProfile


def search_available_lsas(
    *,
    skills=None,
    session_date=None,
    start_time=None,
    end_time=None,
):
    """
    Return active LSAs matching all requested skills.

    Uses database-level filtering and eager-loads the skills
    relationship to avoid N+1 queries during serialization.
    """

    # ---------------------------------------------
    # CLEAN SKILLS
    # ---------------------------------------------

    skills = [
        skill.strip()
        for skill in (skills or [])
        if skill.strip()
    ]

    # Remove duplicates while preserving order
    skills = list(dict.fromkeys(
        skill.lower()
        for skill in skills
    ))

    # ---------------------------------------------
    # BASE QUERY
    # ---------------------------------------------

    qs = (
        LSAProfile.objects
        .filter(is_active=True)
        .prefetch_related("skills")
        .order_by("id")
    )

    # ---------------------------------------------
    # SKILL FILTER
    # ---------------------------------------------

    if skills:

        # Build case-insensitive OR condition:
        #
        # name = Python OR name = Math
        #
        skill_filter = Q()

        for skill in skills:
            skill_filter |= Q(
                skills__name__iexact=skill
            )

        qs = (
            qs
            .filter(skill_filter)
            .annotate(
                matched_skills=Count(
                    "skills",
                    filter=skill_filter,
                    distinct=True,
                )
            )
            .filter(
                matched_skills=len(skills)
            )
        )

    # ---------------------------------------------
    # AVAILABILITY FILTER
    # ---------------------------------------------

    if (
        session_date
        and start_time
        and end_time
    ):

        from .models import Booking

        overlapping = Booking.objects.filter(
            lsa_id__in=qs.values("pk"),
            session_date=session_date,
            status__in=[
                Booking.Status.PENDING_PAYMENT,
                Booking.Status.CONFIRMED,
            ],
            start_time__lt=end_time,
            end_time__gt=start_time,
        ).values("lsa_id")

        qs = qs.exclude(
            pk__in=overlapping
        )

    # ---------------------------------------------
    # DISTINCT
    # ---------------------------------------------

    return qs.distinct()