from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("store", "0014_site_settings"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # ── Policy: new SEO + lifecycle fields ──
        migrations.AddField("Policy", "meta_title",       models.CharField(max_length=200, blank=True, default="")),
        migrations.AddField("Policy", "meta_description", models.TextField(blank=True, default="")),
        migrations.AddField("Policy", "meta_keywords",    models.CharField(max_length=500, blank=True, default="")),
        migrations.AddField("Policy", "og_image",         models.CharField(max_length=500, blank=True, default="")),
        migrations.AddField("Policy", "is_published",     models.BooleanField(default=True)),

        # ── Enquiry: is_read flag ──
        migrations.AddField("Enquiry", "is_read", models.BooleanField(default=False)),

        # ── EnquiryReply ──
        migrations.CreateModel(
            name="EnquiryReply",
            fields=[
                ("id",         models.AutoField(auto_created=True, primary_key=True, serialize=False)),
                ("message",    models.TextField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("enquiry",    models.ForeignKey("store.Enquiry", on_delete=django.db.models.deletion.CASCADE, related_name="replies")),
                ("sent_by",    models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=django.db.models.deletion.SET_NULL, related_name="enquiry_replies")),
            ],
            options={"db_table": "enquiry_replies", "ordering": ["created_at"]},
        ),

        # ── FaqCategory ──
        migrations.CreateModel(
            name="FaqCategory",
            fields=[
                ("id",         models.AutoField(auto_created=True, primary_key=True, serialize=False)),
                ("name",       models.CharField(max_length=100)),
                ("position",   models.IntegerField(default=0)),
                ("is_active",  models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"db_table": "faq_categories", "ordering": ["position"]},
        ),

        # ── Faq: category FK ──
        migrations.AddField(
            "Faq", "category",
            models.ForeignKey("store.FaqCategory", null=True, blank=True,
                              on_delete=django.db.models.deletion.SET_NULL,
                              related_name="items"),
        ),

        # ── TeamMember ──
        migrations.CreateModel(
            name="TeamMember",
            fields=[
                ("id",         models.AutoField(auto_created=True, primary_key=True, serialize=False)),
                ("name",       models.CharField(max_length=100)),
                ("role",       models.CharField(max_length=100)),
                ("bio",        models.TextField(blank=True)),
                ("photo_url",  models.CharField(max_length=500, blank=True)),
                ("position",   models.IntegerField(default=0)),
                ("is_active",  models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"db_table": "team_members", "ordering": ["position"]},
        ),

        # ── CMSRevision ──
        migrations.CreateModel(
            name="CMSRevision",
            fields=[
                ("id",         models.AutoField(auto_created=True, primary_key=True, serialize=False)),
                ("page_type",  models.CharField(max_length=20)),
                ("title",      models.CharField(max_length=200)),
                ("content",    models.TextField()),
                ("note",       models.CharField(max_length=200, blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("saved_by",   models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                                  on_delete=django.db.models.deletion.SET_NULL,
                                                  related_name="cms_revisions")),
            ],
            options={"db_table": "cms_revisions", "ordering": ["-created_at"]},
        ),
    ]
