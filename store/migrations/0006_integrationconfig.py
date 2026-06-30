from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("store", "0005_productvariant_reserved_stock_orderrefund"),
    ]

    operations = [
        migrations.CreateModel(
            name="IntegrationConfig",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("integration", models.CharField(choices=[("RAZORPAY", "Razorpay"), ("FIREBASE", "Firebase")], max_length=20)),
                ("key", models.CharField(max_length=100)),
                ("value", models.TextField(blank=True, default="")),
                ("is_secret", models.BooleanField(default=False)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["integration", "key"], "unique_together": {("integration", "key")}},
        ),
    ]
