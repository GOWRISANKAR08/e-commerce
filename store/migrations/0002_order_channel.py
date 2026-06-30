from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("store", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="channel",
            field=models.CharField(
                choices=[
                    ("WEBSITE", "Website"),
                    ("INSTAGRAM", "Instagram"),
                    ("WHATSAPP", "WhatsApp"),
                    ("REFERRAL", "Referral"),
                ],
                default="WEBSITE",
                max_length=12,
            ),
        ),
    ]
