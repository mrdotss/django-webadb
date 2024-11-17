# Generated by Django 5.1.2 on 2024-11-08 08:37

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('home', '0036_alter_selectivefullfilesystemacquisition_hash_result'),
    ]

    operations = [
        migrations.AlterField(
            model_name='acquisition',
            name='status',
            field=models.CharField(choices=[('pending', 'Pending'), ('in_progress', 'In Progress'), ('completed', 'Completed'), ('paused', 'Paused'), ('cancelled', 'Cancelled'), ('failed', 'Failed'), ('error', 'Error')], default='pending', max_length=20),
        ),
    ]