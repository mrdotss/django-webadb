# Generated by Django 5.1 on 2024-09-16 10:54

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('home', '0022_alter_acquisition_acquisition_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='acquisition',
            name='acquisition_method',
            field=models.CharField(blank=True, max_length=20, null=True),
        ),
    ]