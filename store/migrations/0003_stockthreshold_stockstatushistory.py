from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("store", "0002_order_channel"),
    ]

    operations = [
        migrations.CreateModel(
            name="StockThreshold",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("in_stock_min", models.PositiveIntegerField(default=51, help_text="Stock >= this value → In Stock")),
                ("low_stock_min", models.PositiveIntegerField(default=1, help_text="Stock >= this value (and < in_stock_min) → Low Stock; below → Out of Stock")),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "product",
                    models.OneToOneField(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="threshold",
                        to="store.product",
                    ),
                ),
            ],
            options={"verbose_name": "Stock Threshold"},
        ),
        migrations.CreateModel(
            name="StockStatusHistory",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("old_status", models.CharField(blank=True, max_length=14)),
                ("new_status", models.CharField(max_length=14)),
                ("old_stock", models.IntegerField(default=0)),
                ("new_stock", models.IntegerField(default=0)),
                ("changed_at", models.DateTimeField(auto_now_add=True)),
                ("note", models.CharField(blank=True, max_length=200)),
                (
                    "variant",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="status_history",
                        to="store.productvariant",
                    ),
                ),
            ],
            options={
                "verbose_name": "Stock Status History",
                "verbose_name_plural": "Stock Status Histories",
                "ordering": ["-changed_at"],
            },
        ),
    ]
