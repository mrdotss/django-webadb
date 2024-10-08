# Generated by Django 5.1.1 on 2024-10-08 05:22

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('home', '0028_remove_acquisition_size'),
    ]

    operations = [
        migrations.AddField(
            model_name='acquisition',
            name='size',
            field=models.DecimalField(decimal_places=3, default=0, max_digits=8),
        ),
    ]