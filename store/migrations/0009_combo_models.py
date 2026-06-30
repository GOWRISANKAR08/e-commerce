from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('store', '0008_category_description'),
    ]

    operations = [
        migrations.CreateModel(
            name='ComboPackage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(max_length=20, unique=True)),
                ('name', models.CharField(max_length=200)),
                ('slug', models.SlugField(max_length=220, unique=True)),
                ('short_description', models.CharField(blank=True, default='', max_length=300)),
                ('description', models.TextField(blank=True, default='')),
                ('badge_label', models.CharField(blank=True, default='', max_length=50)),
                ('badge_style', models.CharField(blank=True, choices=[('spice-red', 'Spice Red (Secondary)'), ('brand-green', 'Brand Green (Primary)'), ('gold', 'Gold'), ('dark', 'Dark')], default='', max_length=20)),
                ('tags', models.CharField(blank=True, default='', max_length=500)),
                ('selling_price', models.FloatField(default=0)),
                ('mrp_price', models.FloatField(blank=True, null=True)),
                ('gst_rate', models.FloatField(default=5)),
                ('is_featured', models.BooleanField(default=False)),
                ('is_limited_time', models.BooleanField(default=False)),
                ('is_cod_available', models.BooleanField(default=True)),
                ('status', models.CharField(choices=[('ACTIVE', 'Active'), ('DRAFT', 'Draft')], default='DRAFT', max_length=10)),
                ('available_from', models.DateField(blank=True, null=True)),
                ('available_until', models.DateField(blank=True, null=True)),
                ('max_qty_per_order', models.PositiveIntegerField(default=10)),
                ('orders_count', models.PositiveIntegerField(default=0)),
                ('position', models.IntegerField(default=1)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ['position', '-created_at'],
            },
        ),
        migrations.CreateModel(
            name='ComboItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('quantity', models.PositiveIntegerField(default=1)),
                ('position', models.IntegerField(default=0)),
                ('combo', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='items', to='store.combopackage')),
                ('variant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='combo_items', to='store.productvariant')),
            ],
            options={
                'ordering': ['position'],
            },
        ),
        migrations.CreateModel(
            name='ComboImage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('url', models.CharField(max_length=500)),
                ('is_main', models.BooleanField(default=False)),
                ('position', models.IntegerField(default=0)),
                ('combo', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='images', to='store.combopackage')),
            ],
            options={
                'ordering': ['position'],
            },
        ),
    ]
