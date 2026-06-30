from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("store", "0004_alter_stockstatushistory_id_alter_stockthreshold_id"),
    ]

    operations = [
        migrations.AddField(
            model_name="productvariant",
            name="reserved_stock",
            field=models.IntegerField(default=0),
        ),
        migrations.CreateModel(
            name="OrderRefund",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("refund_type", models.CharField(
                    choices=[("FULL", "Full Refund"), ("PARTIAL", "Partial Refund")],
                    default="FULL",
                    max_length=8,
                )),
                ("amount", models.FloatField()),
                ("reason", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "order",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="refunds",
                        to="store.order",
                    ),
                ),
            ],
            options={"ordering": ["-created_at"]},
        ),
    ]
