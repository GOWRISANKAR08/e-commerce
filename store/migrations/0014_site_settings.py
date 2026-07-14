from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("store", "0013_review_system"),
    ]

    operations = [
        migrations.CreateModel(
            name="SiteSettings",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("store_name",     models.CharField(max_length=100, default="Spicearog")),
                ("store_tagline",  models.CharField(max_length=200, blank=True, default="Pure · Natural · Authentic")),
                ("business_email", models.EmailField(blank=True, default="")),
                ("support_phone",  models.CharField(max_length=20, blank=True, default="")),
                ("store_address",  models.TextField(blank=True, default="")),
                ("logo_url",       models.CharField(max_length=500, blank=True, default="")),
                ("currency",        models.CharField(max_length=20, default="INR — Indian Rupee (₹)")),
                ("timezone",        models.CharField(max_length=60, default="IST — Asia/Kolkata (UTC+5:30)")),
                ("language",        models.CharField(max_length=40, default="English (India)")),
                ("date_format",     models.CharField(max_length=30, default="DD MMM YYYY")),
                ("weight_unit",     models.CharField(max_length=20, default="Grams (g)")),
                ("order_id_prefix", models.CharField(max_length=10, default="ORD-")),
                ("free_shipping_above",     models.IntegerField(default=499)),
                ("default_shipping_charge", models.IntegerField(default=49)),
                ("processing_time",   models.CharField(max_length=20, default="1-2")),
                ("estimated_delivery", models.CharField(max_length=20, default="3-7")),
                ("cod_enabled",            models.BooleanField(default=True)),
                ("show_delivery_estimate", models.BooleanField(default=True)),
                ("international_shipping", models.BooleanField(default=False)),
                ("gstin",                   models.CharField(max_length=20, blank=True, default="")),
                ("default_gst_rate",        models.CharField(max_length=10, default="5")),
                ("prices_inclusive_of_gst", models.BooleanField(default=True)),
                ("show_gst_in_invoice",     models.BooleanField(default=True)),
                ("notif_new_order",       models.BooleanField(default=True)),
                ("notif_order_cancelled", models.BooleanField(default=True)),
                ("notif_refund_request",  models.BooleanField(default=True)),
                ("notif_order_delivered", models.BooleanField(default=False)),
                ("notif_low_stock",    models.BooleanField(default=True)),
                ("notif_out_of_stock", models.BooleanField(default=True)),
                ("notif_restock",      models.BooleanField(default=False)),
                ("notif_new_review",   models.BooleanField(default=True)),
                ("notif_customer_registered", models.BooleanField(default=True)),
                ("notif_payment_success",     models.BooleanField(default=True)),
                ("notif_payment_failed",      models.BooleanField(default=True)),
                ("notif_promotional",         models.BooleanField(default=False)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"db_table": "site_settings"},
        ),
    ]
