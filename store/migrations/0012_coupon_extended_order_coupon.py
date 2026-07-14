from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("store", "0011_coupon"),
    ]

    operations = [
        # Coupon additions
        migrations.AddField(
            model_name="coupon",
            name="name",
            field=models.CharField(blank=True, default="", max_length=200),
        ),
        migrations.AlterField(
            model_name="coupon",
            name="description",
            field=models.CharField(blank=True, default="", max_length=500),
        ),
        migrations.AddField(
            model_name="coupon",
            name="channels",
            field=models.CharField(blank=True, default="WEBSITE", max_length=100),
        ),
        migrations.AddField(
            model_name="coupon",
            name="per_user_limit",
            field=models.PositiveIntegerField(default=0),
        ),
        # Order additions
        migrations.AddField(
            model_name="order",
            name="coupon",
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name="coupon_orders", to="store.coupon",
            ),
        ),
        migrations.AddField(
            model_name="order",
            name="coupon_discount",
            field=models.FloatField(default=0),
        ),
    ]
