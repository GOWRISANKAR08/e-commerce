from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("store", "0010_review_fields"),
    ]

    operations = [
        migrations.CreateModel(
            name="Coupon",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=30, unique=True)),
                ("description", models.CharField(blank=True, default="", max_length=200)),
                ("coupon_type", models.CharField(
                    choices=[
                        ("PERCENT", "Percentage Off"),
                        ("FLAT", "Flat Amount Off"),
                        ("FREE_SHIPPING", "Free Shipping"),
                    ],
                    default="PERCENT",
                    max_length=15,
                )),
                ("discount_value", models.FloatField(default=0)),
                ("min_order_value", models.FloatField(default=0)),
                ("max_discount", models.FloatField(blank=True, null=True)),
                ("max_uses", models.PositiveIntegerField(default=0)),
                ("used_count", models.PositiveIntegerField(default=0)),
                ("valid_from", models.DateTimeField(blank=True, null=True)),
                ("valid_until", models.DateTimeField(blank=True, null=True)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"db_table": "coupons", "ordering": ["-created_at"]},
        ),
    ]
