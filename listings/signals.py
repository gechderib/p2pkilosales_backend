from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import TravelListing, Alert, PackageRequest, Review
from django.contrib.auth import get_user_model
from messaging.utils import send_notification_to_user
from messaging.models import Notification
from messaging.serializers import NotificationSerializer
from datetime import date
from django.db import transaction

User = get_user_model()

@receiver(post_save, sender=TravelListing)
def notify_alerts_on_travel_listing(sender, instance, created, **kwargs):
    if not created:
        return

    print(f" {instance.id} - {instance.destination_country} - {instance.destination_region}")
    alerts = Alert.objects.filter(
        pickup_country=instance.pickup_country,
        pickup_region=instance.pickup_region,
        destination_country=instance.destination_country,
        destination_region=instance.destination_region,
        from_travel_date__lte=instance.travel_date,
        # notify_me=True,
        is_active=True
    )

    alerts = alerts.filter(
        to_travel_date__isnull=True
    ) | alerts.filter(
        to_travel_date__gte=instance.travel_date
    )
    for alert in alerts.distinct():
        user = alert.user
        notification = Notification.objects.create(
            user=user,
            travel_listing=instance,
            message=f"A new travel listing matches your alert: {instance}"
        )
        # Send notification via Django Channels
        serializer = NotificationSerializer(notification)
        send_notification_to_user(user.id, serializer.data) 


@receiver(post_save, sender=TravelListing)
def update_user_profile_total_trips_created(sender, instance, created, **kwargs):
    if created:
        print("Its created successfully")
        instance.user.profile.total_trips_created += 1
        instance.user.profile.save()

@receiver(post_save, sender=PackageRequest)
def update_user_profile_total_offer_sent(sender, instance, **kwargs):
    if 'status' in kwargs.get('update_fields', []):
        if instance.status == 'pending':
            instance.user.profile.total_offers_sent += 1
            instance.user.profile.save()
        if instance.status == 'accepted':
            instance.travel_listing.user.profile.total_offer_received += 1
            instance.travel_listing.user.profile.save()
        if instance.status == "completed":
            instance.user.profile.total_completed_deliveries += 1
            instance.user.profile.save()


@receiver(post_save, sender=Review)
def update_user_rating(sender, instance, created, **kwargs):
    """
    Updates the user's average rating when a Review is created or updated.
    """
    profile = instance.travel_listing.user.profile

    with transaction.atomic():  # ensure data consistency
        if created:
            # When a new review is created
            total = profile.total_rating_received + 1
            new_average = (
                profile.average_rating * profile.total_rating_received + instance.rate
            ) / total
            profile.total_rating_received = total
            profile.average_rating = new_average
            profile.save(update_fields=["total_rating_received", "average_rating"])

        else:
            # When an existing review is updated (rate changed)
            update_fields = kwargs.get("update_fields", None)
            if not update_fields or "rate" in update_fields:
                try:
                    old_instance = Review.objects.get(pk=instance.pk)
                except Review.DoesNotExist:
                    return  # safety fallback

                if old_instance.rate != instance.rate:
                    total = profile.total_rating_received
                    if total > 0:
                        new_average = (
                            profile.average_rating * total - old_instance.rate + instance.rate
                        ) / total
                        profile.average_rating = new_average
                        profile.save(update_fields=["average_rating"])


@receiver(post_delete, sender=Review)
def recalculate_user_rating_on_delete(sender, instance, **kwargs):
    """
    Recalculates the user's rating when a Review is deleted.
    """
    profile = instance.travel_listing.user.profile

    with transaction.atomic():
        total = profile.total_rating_received - 1

        if total > 0:
            new_average = (
                profile.average_rating * profile.total_rating_received - instance.rate
            ) / total
            profile.total_rating_received = total
            profile.average_rating = new_average
        else:
            # Reset if no reviews remain
            profile.total_rating_received = 0
            profile.average_rating = 0

        profile.save(update_fields=["total_rating_received", "average_rating"])
