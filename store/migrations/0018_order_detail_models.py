import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("store", "0017_cartitem_combo"),
    ]

    operations = [
        # Add combo FK to OrderItem
        migrations.AddField(
            model_name="orderitem",
            name="combo",
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="order_items",
                to="store.combopackage",
            ),
        ),
        # OrderNote model
        migrations.CreateModel(
            name="OrderNote",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("order", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="notes", to="store.order")),
                ("text", models.TextField()),
                ("is_internal", models.BooleanField(default=True)),
                ("created_by_name", models.CharField(blank=True, max_length=120)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"db_table": "order_notes", "ordering": ["-created_at"]},
        ),
        # OrderEvent model
        migrations.CreateModel(
            name="OrderEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("order", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="events", to="store.order")),
                ("title", models.CharField(max_length=120)),
                ("description", models.TextField(blank=True)),
                ("actor_name", models.CharField(blank=True, max_length=120)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"db_table": "order_events", "ordering": ["created_at"]},
        ),
    ]
