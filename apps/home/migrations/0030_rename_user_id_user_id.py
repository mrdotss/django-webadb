# Generated by Django 5.1.2 on 2024-10-16 13:43

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('home', '0029_acquisition_size'),
    ]

    operations = [
        migrations.RenameField(
            model_name='user',
            old_name='user_id',
            new_name='id',
        ),
    ]
