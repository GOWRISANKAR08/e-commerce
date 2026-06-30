from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("store", "0009_combo_models"),
    ]

    operations = [
        migrations.AddField(
            model_name="review",
            name="title",
            field=models.CharField(blank=True, default="", max_length=200),
        ),
        migrations.AddField(
            model_name="review",
            name="reply",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="review",
            name="replied_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="review",
            name="is_flagged",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="review",
            name="helpful_count",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="review",
            name="is_verified",
            field=models.BooleanField(default=True),
        ),
    ]
