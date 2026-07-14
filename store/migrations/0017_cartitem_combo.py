from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('store', '0016_testimonial_extended'),
    ]

    operations = [
        migrations.AddField(
            model_name='cartitem',
            name='combo',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='cart_items',
                to='store.combopackage',
            ),
        ),
    ]
