# Generated by Django 5.2.3 on 2025-06-25 07:34

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='customuser',
            name='is_identity_verified',
            field=models.CharField(choices=[('pending', 'Pending'), ('rejected', 'Rejected'), ('completed', 'Completed')], default='pending', max_length=10),
        ),
    ]
