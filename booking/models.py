from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models


class Parent(models.Model):
    name = models.CharField(max_length=120)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]
        indexes = [models.Index(fields=["email"], name="parent_email_idx")]

    def __str__(self):
        return f"{self.name} ({self.email})"


class Skill(models.Model):
    name = models.CharField(max_length=80, unique=True)

    class Meta:
        ordering = ["name"]
        indexes = [models.Index(fields=["name"], name="skill_name_idx")]

    def __str__(self):
        return self.name


class LSAProfile(models.Model):
    name = models.CharField(max_length=120)
    email = models.EmailField(unique=True)
    hourly_rate = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    is_active = models.BooleanField(default=True)
    skills = models.ManyToManyField(Skill, related_name="lsa_profiles", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]
        indexes = [
            models.Index(fields=["is_active"], name="lsa_active_idx"),
            models.Index(fields=["hourly_rate"], name="lsa_rate_idx"),
        ]

    def __str__(self):
        return f"{self.name} ({self.email})"


class Booking(models.Model):
    class Status(models.TextChoices):
        PENDING_PAYMENT = "PENDING_PAYMENT", "Pending Payment"
        CONFIRMED = "CONFIRMED", "Confirmed"
        PAYMENT_FAILED = "PAYMENT_FAILED", "Payment Failed"
        CANCELLED = "CANCELLED", "Cancelled"

    parent = models.ForeignKey(Parent, on_delete=models.PROTECT, related_name="bookings")
    lsa = models.ForeignKey(LSAProfile, on_delete=models.PROTECT, related_name="bookings")
    session_date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING_PAYMENT)
    idempotency_key = models.CharField(max_length=100, unique=True, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["lsa", "session_date", "start_time"], name="booking_slot_idx"),
            models.Index(fields=["parent", "status"], name="booking_parent_status_idx"),
            models.Index(fields=["status"], name="booking_status_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(end_time__gt=models.F("start_time")),
                name="booking_end_after_start",
            ),
        ]

    def __str__(self):
        return f"Booking #{self.pk} - {self.status}"


class Payment(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        SUCCESS = "SUCCESS", "Success"
        FAILED = "FAILED", "Failed"

    booking = models.OneToOneField(Booking, on_delete=models.CASCADE, related_name="payment")
    transaction_id = models.CharField(max_length=120, unique=True, null=True, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    provider_message = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["status"], name="payment_status_idx"),
            models.Index(fields=["transaction_id"], name="payment_txn_idx"),
        ]

    def __str__(self):
        return f"Payment #{self.pk} - {self.status}"
