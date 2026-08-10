from datetime import datetime

from django.core.exceptions import ValidationError

from .models import Booking


ACTIVE_BOOKING_STATUSES = {
    Booking.Status.PENDING_PAYMENT,
    Booking.Status.CONFIRMED,
}


def validate_time_range(session_date, start_time, end_time):
    if not session_date or not start_time or not end_time:
        return
    if end_time <= start_time:
        raise ValidationError({"end_time": "end_time must be later than start_time."})


def has_overlapping_booking(*, lsa_id, session_date, start_time, end_time, exclude_booking_id=None):
    qs = Booking.objects.filter(
        lsa_id=lsa_id,
        session_date=session_date,
        status__in=ACTIVE_BOOKING_STATUSES,
        start_time__lt=end_time,
        end_time__gt=start_time,
    )
    if exclude_booking_id:
        qs = qs.exclude(pk=exclude_booking_id)
    return qs.exists()
