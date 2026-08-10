from django.db import migrations, models
import django.db.models.deletion
from django.core.validators import MinValueValidator
from decimal import Decimal


class Migration(migrations.Migration):
    initial = True
    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Parent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120)),
                ("email", models.EmailField(max_length=254, unique=True)),
                ("phone", models.CharField(blank=True, max_length=20)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"ordering": ["id"], "indexes": [models.Index(fields=["email"], name="parent_email_idx")]},
        ),
        migrations.CreateModel(
            name="Skill",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=80, unique=True)),
            ],
            options={"ordering": ["name"], "indexes": [models.Index(fields=["name"], name="skill_name_idx")]},
        ),
        migrations.CreateModel(
            name="LSAProfile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120)),
                ("email", models.EmailField(max_length=254, unique=True)),
                ("hourly_rate", models.DecimalField(decimal_places=2, max_digits=10, validators=[MinValueValidator(Decimal("0.01"))])),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("skills", models.ManyToManyField(blank=True, related_name="lsa_profiles", to="booking.skill")),
            ],
            options={"ordering": ["id"], "indexes": [models.Index(fields=["is_active"], name="lsa_active_idx"), models.Index(fields=["hourly_rate"], name="lsa_rate_idx")]},
        ),
        migrations.CreateModel(
            name="Booking",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("session_date", models.DateField()),
                ("start_time", models.TimeField()),
                ("end_time", models.TimeField()),
                ("amount", models.DecimalField(decimal_places=2, max_digits=10, validators=[MinValueValidator(Decimal("0.01"))])),
                ("status", models.CharField(choices=[("PENDING_PAYMENT", "Pending Payment"), ("CONFIRMED", "Confirmed"), ("PAYMENT_FAILED", "Payment Failed"), ("CANCELLED", "Cancelled")], default="PENDING_PAYMENT", max_length=20)),
                ("idempotency_key", models.CharField(blank=True, max_length=100, null=True, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("lsa", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="bookings", to="booking.lsaprofile")),
                ("parent", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="bookings", to="booking.parent")),
            ],
            options={
                "ordering": ["-created_at"],
                "indexes": [models.Index(fields=["lsa", "session_date", "start_time"], name="booking_slot_idx"), models.Index(fields=["parent", "status"], name="booking_parent_status_idx"), models.Index(fields=["status"], name="booking_status_idx")],
                "constraints": [models.CheckConstraint(condition=models.Q(("end_time__gt", models.F("start_time"))), name="booking_end_after_start")],
            },
        ),
        migrations.CreateModel(
            name="Payment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("transaction_id", models.CharField(blank=True, max_length=120, null=True, unique=True)),
                ("amount", models.DecimalField(decimal_places=2, max_digits=10, validators=[MinValueValidator(Decimal("0.01"))])),
                ("status", models.CharField(choices=[("PENDING", "Pending"), ("SUCCESS", "Success"), ("FAILED", "Failed")], default="PENDING", max_length=10)),
                ("provider_message", models.CharField(blank=True, max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("booking", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="payment", to="booking.booking")),
            ],
            options={"indexes": [models.Index(fields=["status"], name="payment_status_idx"), models.Index(fields=["transaction_id"], name="payment_txn_idx")]},
        ),
    ]
