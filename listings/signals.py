"""
Django signals for listings app.
Handles wallet operations and profile statistics updates.
"""
from django.db.models.signals import pre_save, post_save, post_delete
from django.dispatch import receiver
from .models import PackageRequest, Review, TravelListing
from money.wallet_service import WalletService
from django.db.models import Avg, Count, Q
import logging

logger = logging.getLogger(__name__)


# ============================================================================
# WALLET OPERATIONS
# ============================================================================

@receiver(pre_save, sender=PackageRequest)
def handle_package_request_status_change(sender, instance, **kwargs):
    """
    Handle wallet operations when package request status changes.
    
    - When status changes to 'completed': Release payment to traveler
    - When status changes to 'rejected': Refund locked amount to requester
    """
    if not instance.pk:
        # New instance, skip
        return
    
    try:
        # Get the old instance from database
        old_instance = PackageRequest.objects.get(pk=instance.pk)
        
        # Check if status has changed
        if old_instance.status != instance.status:
            logger.info(
                f"PackageRequest #{instance.pk} status changed from {old_instance.status} to {instance.status}"
            )
            
            # Handle status change to 'completed'
            if instance.status == 'completed' and old_instance.status == 'accepted':
                logger.info(f"Releasing payment for PackageRequest #{instance.pk}")
                try:
                    WalletService.release_payment_to_traveler(instance)
                    logger.info(f"Payment released successfully for PackageRequest #{instance.pk}")
                except Exception as e:
                    logger.error(f"Failed to release payment for PackageRequest #{instance.pk}: {str(e)}")
                    raise
            
            # Handle status change to 'rejected'
            elif instance.status == 'rejected' and old_instance.status in ['pending', 'accepted']:
                logger.info(f"Refunding locked amount for PackageRequest #{instance.pk}")
                try:
                    WalletService.refund_locked_amount(instance)
                    logger.info(f"Refund processed successfully for PackageRequest #{instance.pk}")
                except Exception as e:
                    logger.error(f"Failed to refund for PackageRequest #{instance.pk}: {str(e)}")
                    raise
                    
    except PackageRequest.DoesNotExist:
        # This shouldn't happen, but just in case
        logger.warning(f"PackageRequest #{instance.pk} not found in database during pre_save")
        pass


# ============================================================================
# PROFILE STATISTICS UPDATES
# ============================================================================

@receiver(post_save, sender=TravelListing)
@receiver(post_delete, sender=TravelListing)
def update_total_trips_created(sender, instance, **kwargs):
    """Update total_trips_created when a travel listing is created or deleted."""
    try:
        profile = instance.user.profile
        profile.total_trips_created = TravelListing.objects.filter(user=instance.user).count()
        profile.save(update_fields=['total_trips_created'])
        logger.info(f"Updated total_trips_created for {instance.user.username}: {profile.total_trips_created}")
    except Exception as e:
        logger.error(f"Failed to update total_trips_created: {str(e)}")


@receiver(post_save, sender=PackageRequest)
@receiver(post_delete, sender=PackageRequest)
def update_offer_counts(sender, instance, **kwargs):
    """
    Update total_offer_sent and total_offer_received when package requests change.
    - total_offer_sent: Package requests created by the user
    - total_offer_received: Package requests for the user's travel listings
    """
    try:
        # Update requester's total_offer_sent
        requester_profile = instance.user.profile
        requester_profile.total_offer_sent = PackageRequest.objects.filter(user=instance.user).count()
        requester_profile.save(update_fields=['total_offer_sent'])
        logger.info(f"Updated total_offer_sent for {instance.user.username}: {requester_profile.total_offer_sent}")
        
        # Update traveler's total_offer_received
        traveler = instance.travel_listing.user
        traveler_profile = traveler.profile
        traveler_profile.total_offer_received = PackageRequest.objects.filter(
            travel_listing__user=traveler
        ).count()
        traveler_profile.save(update_fields=['total_offer_received'])
        logger.info(f"Updated total_offer_received for {traveler.username}: {traveler_profile.total_offer_received}")
        
    except Exception as e:
        logger.error(f"Failed to update offer counts: {str(e)}")


@receiver(post_save, sender=PackageRequest)
@receiver(post_delete, sender=PackageRequest)
def update_completed_deliveries(sender, instance, **kwargs):
    """
    Update total_completed_deliveries for the traveler when package requests are completed.
    Only counts completed package requests.
    """
    try:
        traveler = instance.travel_listing.user
        traveler_profile = traveler.profile
        
        # Count completed deliveries for this traveler
        traveler_profile.total_completed_deliveries = PackageRequest.objects.filter(
            travel_listing__user=traveler,
            status='completed'
        ).count()
        
        traveler_profile.save(update_fields=['total_completed_deliveries'])
        logger.info(
            f"Updated total_completed_deliveries for {traveler.username}: "
            f"{traveler_profile.total_completed_deliveries}"
        )
        
    except Exception as e:
        logger.error(f"Failed to update completed deliveries: {str(e)}")


@receiver(post_save, sender=Review)
@receiver(post_delete, sender=Review)
def update_traveler_rating(sender, instance, **kwargs):
    """
    Update the travel listing owner's profile rating when a review is created, updated, or deleted.
    Reviews are given by package requesters to travelers (listing owners).
    """
    try:
        # Get the traveler (travel listing owner)
        traveler = instance.travel_listing.user
        
        # Calculate new ratings from all reviews for this traveler's listings
        traveler_listings = TravelListing.objects.filter(user=traveler)
        
        # Get all reviews for this traveler's listings
        reviews = Review.objects.filter(travel_listing__in=traveler_listings)
        
        # Calculate average rating and total count
        stats = reviews.aggregate(
            avg_rating=Avg('rate'),
            total_reviews=Count('id')
        )
        
        # Update the traveler's profile
        profile = traveler.profile
        profile.average_rating = round(stats['avg_rating'], 2) if stats['avg_rating'] else 0.0
        profile.total_rating_received = stats['total_reviews'] or 0
        profile.save(update_fields=['average_rating', 'total_rating_received'])
        
        logger.info(
            f"Updated ratings for {traveler.username}: "
            f"avg_rating={profile.average_rating}, total_reviews={profile.total_rating_received}"
        )
        
    except Exception as e:
        logger.error(f"Failed to update traveler rating: {str(e)}")
