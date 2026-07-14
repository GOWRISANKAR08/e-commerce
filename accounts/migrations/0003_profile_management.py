"""
Migration: adds extended profile fields to User, updates UserAddress,
and creates LoginHistory, OTPRequest, ActivityLog tables.
"""
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0002_user_manual_tags_customernote"),
    ]

    operations = [
        # ── User: extended profile fields ────────────────────────────────────
        migrations.AddField(
            model_name="user",
            name="date_of_birth",
            field=models.DateField(null=True, blank=True),
        ),
        migrations.AddField(
            model_name="user",
            name="gender",
            field=models.CharField(
                max_length=10,
                choices=[
                    ("MALE", "Male"),
                    ("FEMALE", "Female"),
                    ("OTHER", "Other"),
                    ("PREFER_NOT", "Prefer not to say"),
                ],
                null=True,
                blank=True,
            ),
        ),
        migrations.AddField(
            model_name="user",
            name="profile_image_url",
            field=models.CharField(max_length=500, null=True, blank=True),
        ),
        migrations.AddField(
            model_name="user",
            name="loyalty_points",
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name="user",
            name="wallet_balance",
            field=models.FloatField(default=0.0),
        ),
        migrations.AddField(
            model_name="user",
            name="notif_email",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="user",
            name="notif_sms",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="user",
            name="notif_push",
            field=models.BooleanField(default=True),
        ),

        # ── UserAddress: extended fields ─────────────────────────────────────
        migrations.AddField(
            model_name="useraddress",
            name="address_type",
            field=models.CharField(
                max_length=10,
                choices=[("HOME", "Home"), ("OFFICE", "Office"), ("OTHER", "Other")],
                default="HOME",
            ),
        ),
        migrations.AddField(
            model_name="useraddress",
            name="recipient_name",
            field=models.CharField(max_length=150, null=True, blank=True),
        ),
        migrations.AddField(
            model_name="useraddress",
            name="phone",
            field=models.CharField(max_length=20, null=True, blank=True),
        ),
        migrations.AddField(
            model_name="useraddress",
            name="state",
            field=models.CharField(max_length=120, null=True, blank=True),
        ),
        migrations.AlterModelOptions(
            name="useraddress",
            options={"ordering": ["-is_default", "-created_at"]},
        ),

        # ── LoginHistory ──────────────────────────────────────────────────────
        migrations.CreateModel(
            name="LoginHistory",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False)),
                ("user", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="login_history",
                    to=settings.AUTH_USER_MODEL,
                )),
                ("ip_address", models.GenericIPAddressField(null=True, blank=True)),
                ("user_agent", models.CharField(max_length=500, blank=True, default="")),
                ("device", models.CharField(max_length=200, blank=True, default="")),
                ("status", models.CharField(
                    max_length=10,
                    choices=[("SUCCESS", "Success"), ("FAILED", "Failed")],
                    default="SUCCESS",
                )),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"db_table": "login_history", "ordering": ["-created_at"]},
        ),

        # ── OTPRequest ────────────────────────────────────────────────────────
        migrations.CreateModel(
            name="OTPRequest",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False)),
                ("user", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="otp_requests",
                    to=settings.AUTH_USER_MODEL,
                )),
                ("otp_type", models.CharField(
                    max_length=20,
                    choices=[
                        ("EMAIL_CHANGE", "Email Change"),
                        ("PHONE_CHANGE", "Phone Change"),
                        ("DELETE_ACCOUNT", "Delete Account"),
                    ],
                )),
                ("new_value", models.CharField(max_length=255, blank=True, default="")),
                ("code", models.CharField(max_length=6)),
                ("expires_at", models.DateTimeField()),
                ("is_used", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"db_table": "otp_requests", "ordering": ["-created_at"]},
        ),

        # ── ActivityLog ───────────────────────────────────────────────────────
        migrations.CreateModel(
            name="ActivityLog",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False)),
                ("user", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="activity_logs",
                    to=settings.AUTH_USER_MODEL,
                )),
                ("action_type", models.CharField(max_length=30, choices=[
                    ("ORDER_PLACED", "Order Placed"),
                    ("PROFILE_UPDATED", "Profile Updated"),
                    ("PHOTO_UPDATED", "Photo Updated"),
                    ("EMAIL_CHANGED", "Email Changed"),
                    ("PHONE_CHANGED", "Phone Changed"),
                    ("PASSWORD_CHANGED", "Password Changed"),
                    ("ADDRESS_ADDED", "Address Added"),
                    ("ADDRESS_UPDATED", "Address Updated"),
                    ("ADDRESS_DELETED", "Address Deleted"),
                    ("REVIEW_SUBMITTED", "Review Submitted"),
                    ("LOGIN", "Logged In"),
                    ("LOGOUT", "Logged Out"),
                    ("WISHLIST_UPDATED", "Wishlist Updated"),
                    ("NOTIF_PREFS", "Notification Preferences Updated"),
                ])),
                ("description", models.CharField(max_length=500, blank=True, default="")),
                ("metadata", models.CharField(max_length=500, blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"db_table": "activity_logs", "ordering": ["-created_at"]},
        ),
    ]
