from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('store', '0007_integrationconfig_cloudinary'),
    ]

    operations = [
        migrations.AddField(
            model_name='category',
            name='description',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
    ]
