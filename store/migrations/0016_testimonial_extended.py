from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("store", "0015_cms_extensions"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="testimonial",
            name="updated_at",
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.AddField(
            model_name="testimonial",
            name="user",
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="testimonials",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="testimonial",
            name="email",
            field=models.EmailField(blank=True, max_length=254),
        ),
        migrations.AddField(
            model_name="testimonial",
            name="order",
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to="store.order",
            ),
        ),
        migrations.AddField(
            model_name="testimonial",
            name="title",
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AddField(
            model_name="testimonial",
            name="consent",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="testimonial",
            name="is_featured",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="testimonial",
            name="admin_note",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="testimonial",
            name="approval_status",
            field=models.CharField(
                choices=[
                    ("PENDING", "Pending"),
                    ("APPROVED", "Approved"),
                    ("REJECTED", "Rejected"),
                    ("FLAGGED", "Flagged"),
                ],
                default="APPROVED",
                max_length=10,
            ),
        ),
        migrations.AlterField(
            model_name="testimonial",
            name="image",
            field=models.CharField(blank=True, max_length=500, null=True),
        ),
        migrations.AlterField(
            model_name="testimonial",
            name="position",
            field=models.IntegerField(default=0),
        ),
        migrations.AlterModelOptions(
            name="testimonial",
            options={"ordering": ["-created_at"]},
        ),
    ]
