from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework import serializers

from .models import Booking, LSAProfile, Parent
from .validators import has_overlapping_booking, validate_time_range


class LSASearchSerializer(serializers.ModelSerializer):
    skills = serializers.SerializerMethodField()

    class Meta:
        model = LSAProfile
        fields = ["id", "name", "email", "hourly_rate", "skills", "is_active"]

    def get_skills(self, obj):
        return [skill.name for skill in obj.skills.all()]


class BookingCreateSerializer(serializers.ModelSerializer):
    parent_id = serializers.PrimaryKeyRelatedField(
        source="parent", queryset=Parent.objects.all(), write_only=True
    )
    lsa_id = serializers.PrimaryKeyRelatedField(
        source="lsa", queryset=LSAProfile.objects.filter(is_active=True), write_only=True
    )

    class Meta:
        model = Booking
        fields = [
            "parent_id",
            "lsa_id",
            "session_date",
            "start_time",
            "end_time",
            "idempotency_key",
        ]

    def validate(self, attrs):
        validate_time_range(attrs.get("session_date"), attrs.get("start_time"), attrs.get("end_time"))
        if attrs.get("session_date"):
            from datetime import date
            if attrs["session_date"] < date.today():
                raise serializers.ValidationError({"session_date": "session_date cannot be in the past."})
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        lsa = LSAProfile.objects.select_for_update().get(pk=validated_data["lsa"].pk)
        parent = validated_data["parent"]
        session_date = validated_data["session_date"]
        start_time = validated_data["start_time"]
        end_time = validated_data["end_time"]

        if not lsa.is_active:
            raise serializers.ValidationError({"lsa_id": "LSA is inactive."})

        if has_overlapping_booking(
            lsa_id=lsa.pk,
            session_date=session_date,
            start_time=start_time,
            end_time=end_time,
        ):
            raise serializers.ValidationError({"booking": "LSA already has an overlapping session."})

        from datetime import datetime
        start = datetime.combine(session_date, start_time)
        end = datetime.combine(session_date, end_time)
        duration_hours = Decimal((end - start).total_seconds()) / Decimal("3600")
        amount = (duration_hours * lsa.hourly_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        return Booking.objects.create(
            parent=parent,
            lsa=lsa,
            session_date=session_date,
            start_time=start_time,
            end_time=end_time,
            amount=amount,
            idempotency_key=validated_data.get("idempotency_key"),
            status=Booking.Status.PENDING_PAYMENT,
        )


class BookingResponseSerializer(serializers.ModelSerializer):
    parent = serializers.SerializerMethodField()
    lsa = serializers.SerializerMethodField()
    payment = serializers.SerializerMethodField()

    class Meta:
        model = Booking
        fields = [
            "id", "parent", "lsa", "session_date", "start_time", "end_time",
            "amount", "status", "payment", "created_at",
        ]

    def get_parent(self, obj):
        return {"id": obj.parent_id, "name": obj.parent.name, "email": obj.parent.email}

    def get_lsa(self, obj):
        return {"id": obj.lsa_id, "name": obj.lsa.name, "email": obj.lsa.email}

    def get_payment(self, obj):
        payment = getattr(obj, "payment", None)
        if not payment:
            return None
        return {
            "id": payment.id,
            "transaction_id": payment.transaction_id,
            "amount": payment.amount,
            "status": payment.status,
            "provider_message": payment.provider_message,
        }
