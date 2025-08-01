# Generated by Django 5.2.3 on 2025-06-25 07:00

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('listings', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='alert',
            name='user',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='packagerequest',
            name='user',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='listingimage',
            name='package_request',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='images', to='listings.packagerequest'),
        ),
        migrations.AddField(
            model_name='packagerequest',
            name='package_types',
            field=models.ManyToManyField(blank=True, to='listings.packagetype'),
        ),
        migrations.AddField(
            model_name='region',
            name='country',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='regions', to='listings.country'),
        ),
        migrations.AddField(
            model_name='travellisting',
            name='destination_country',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='destination_listings', to='listings.country'),
        ),
        migrations.AddField(
            model_name='travellisting',
            name='destination_region',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='destination_listings', to='listings.region'),
        ),
        migrations.AddField(
            model_name='travellisting',
            name='mode_of_transport',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='listings.transporttype'),
        ),
        migrations.AddField(
            model_name='travellisting',
            name='pickup_country',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='pickup_listings', to='listings.country'),
        ),
        migrations.AddField(
            model_name='travellisting',
            name='pickup_region',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='pickup_listings', to='listings.region'),
        ),
        migrations.AddField(
            model_name='travellisting',
            name='user',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='packagerequest',
            name='travel_listing',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='package_requests', to='listings.travellisting'),
        ),
        migrations.AddField(
            model_name='listingimage',
            name='travel_listing',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='images', to='listings.travellisting'),
        ),
        migrations.AlterUniqueTogether(
            name='region',
            unique_together={('name', 'country')},
        ),
    ]
