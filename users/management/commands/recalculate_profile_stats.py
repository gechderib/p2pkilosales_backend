from django.core.management.base import BaseCommand
from listings.models import Review, TravelListing, PackageRequest
from users.models import Profile, CustomUser
from django.db.models import Avg, Count


class Command(BaseCommand):
    help = 'Recalculate all profile statistics from existing data'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting profile statistics recalculation...'))
        self.stdout.write('=' * 60)
        
        all_users = CustomUser.objects.all()
        updated_count = 0
        
        for user in all_users:
            try:
                profile = user.profile
                
                # 1. Total trips created
                total_trips = TravelListing.objects.filter(user=user).count()
                
                # 2. Total offer sent (package requests created by user)
                total_sent = PackageRequest.objects.filter(user=user).count()
                
                # 3. Total offer received (package requests for user's listings)
                total_received = PackageRequest.objects.filter(
                    travel_listing__user=user
                ).count()
                
                # 4. Total completed deliveries
                total_completed = PackageRequest.objects.filter(
                    travel_listing__user=user,
                    status='completed'
                ).count()
                
                # 5. Average rating and total reviews
                traveler_listings = TravelListing.objects.filter(user=user)
                reviews = Review.objects.filter(travel_listing__in=traveler_listings)
                
                stats = reviews.aggregate(
                    avg_rating=Avg('rate'),
                    total_reviews=Count('id')
                )
                
                avg_rating = round(stats['avg_rating'], 2) if stats['avg_rating'] else 0.0
                total_reviews = stats['total_reviews'] or 0
                
                # Update profile
                profile.total_trips_created = total_trips
                profile.total_offer_sent = total_sent
                profile.total_offer_received = total_received
                profile.total_completed_deliveries = total_completed
                profile.average_rating = avg_rating
                profile.total_rating_received = total_reviews
                profile.save()
                
                updated_count += 1
                
                # Print summary for users with activity
                if any([total_trips, total_sent, total_received, total_completed, total_reviews]):
                    self.stdout.write(f"\n{user.username} ({user.email}):")
                    self.stdout.write(f"  Trips Created: {total_trips}")
                    self.stdout.write(f"  Offers Sent: {total_sent}")
                    self.stdout.write(f"  Offers Received: {total_received}")
                    self.stdout.write(f"  Completed Deliveries: {total_completed}")
                    self.stdout.write(f"  Average Rating: {avg_rating} ({total_reviews} reviews)")
                    
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"Error updating {user.username}: {str(e)}")
                )
        
        self.stdout.write('\n' + '=' * 60)
        self.stdout.write(
            self.style.SUCCESS(f'Total users updated: {updated_count}')
        )
        self.stdout.write(
            self.style.SUCCESS('Profile statistics recalculation complete!')
        )
