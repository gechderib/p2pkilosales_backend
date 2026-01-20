from rest_framework import serializers
from .models import TravelListing, PackageRequest, Alert, Country, Region, TransportType, PackageType, Review
from decimal import Decimal
from django.db import models
from django.db.models import Q, Sum

class CountrySerializer(serializers.ModelSerializer):
    class Meta:
        model = Country
        fields = ['id', 'name', 'code', 'is_popular', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']

class RegionSerializer(serializers.ModelSerializer):
    country_name = serializers.CharField(source='country.name', read_only=True)

    class Meta:
        model = Region
        fields = ['id', 'name', 'country', 'country_name', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']

class RegionWithCountrySerializer(serializers.ModelSerializer):
    display_name = serializers.SerializerMethodField()

    class Meta:
        model = Region
        fields = ['id', 'name', 'country', 'display_name']

    def get_display_name(self, obj):
        return f"{obj.name}, {obj.country.name}"

class TransportTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = TransportType
        fields = ['id', 'name', 'description']

class PackageTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = PackageType
        fields = ['id', 'name', 'description']

class TravelListingSerializer(serializers.ModelSerializer):
    pickup = RegionWithCountrySerializer(source='pickup_region', read_only=True)
    destination = RegionWithCountrySerializer(source='destination_region', read_only=True)
    pickup_region_id = serializers.PrimaryKeyRelatedField(queryset=Region.objects.all(), source='pickup_region', write_only=True)
    destination_region_id = serializers.PrimaryKeyRelatedField(queryset=Region.objects.all(), source='destination_region', write_only=True)
    mode_of_transport = TransportTypeSerializer(read_only=True)
    mode_of_transport_id = serializers.PrimaryKeyRelatedField(queryset=TransportType.objects.all(), source='mode_of_transport', write_only=True)

    class Meta:
        model = TravelListing
        fields = [
            'id', 'user', 'pickup', 'pickup_region_id', 'destination', 'destination_region_id',
            'travel_date', 'travel_time', 'mode_of_transport', 'mode_of_transport_id', 'maximum_weight_in_kg',
            'notes', 'price_per_kg', 'price_per_document', 'price_per_phone',
            'price_per_tablet', 'price_per_pc', 'price_full_suitcase', 'currency', 'status',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['user', 'created_at', 'updated_at', 'pickup', 'destination', 'mode_of_transport']

    def validate(self, data):
        """
        Ensure that at least one pricing field is provided.
        """
        pricing_fields = [
            'price_per_kg', 'price_per_document', 'price_per_phone',
            'price_per_tablet', 'price_per_pc',
            'price_full_suitcase'
        ]
        
        # On update, we need to consider existing values if not provided in data
        if self.instance:
            has_pricing = any(
                data.get(field, getattr(self.instance, field)) is not None 
                for field in pricing_fields
            )
        else:
            has_pricing = any(data.get(field) is not None for field in pricing_fields)

        if not has_pricing:
            raise serializers.ValidationError(
                "At least one pricing method (e.g., price per kg, per document, or full suitcase) must be provided."
            )
        
        # Check wallet balance for listing creation
        request = self.context.get('request')
        if request and not self.instance:  # Only on creation, not update
            from money.wallet_service import WalletService
            if not WalletService.check_balance_for_listing(request.user):
                from money.models import PlatformConfig
                config = PlatformConfig.get_config()
                raise serializers.ValidationError(
                    f"Insufficient wallet balance. Minimum {config.min_balance_for_travel_listing} ETB required to create a travel listing."
                )
        
        return data

    def create(self, validated_data):
        pickup_region = validated_data.pop('pickup_region')
        destination_region = validated_data.pop('destination_region')
        validated_data['pickup_region'] = pickup_region
        validated_data['pickup_country'] = pickup_region.country
        validated_data['destination_region'] = destination_region
        validated_data['destination_country'] = destination_region.country
        
        # Create the listing
        listing = super().create(validated_data)
        
        # Deduct listing fee from user's wallet
        from money.wallet_service import WalletService, InsufficientBalanceError
        try:
            WalletService.deduct_listing_fee(listing.user, listing)
        except InsufficientBalanceError as e:
            # If fee deduction fails, delete the listing and raise error
            listing.delete()
            raise serializers.ValidationError(str(e))
        
        return listing

    def update(self, instance, validated_data):
        if 'pickup_region' in validated_data:
            pickup_region = validated_data.pop('pickup_region')
            instance.pickup_region = pickup_region
            instance.pickup_country = pickup_region.country
        if 'destination_region' in validated_data:
            destination_region = validated_data.pop('destination_region')
            instance.destination_region = destination_region
            instance.destination_country = destination_region.country
        return super().update(instance, validated_data)

    def validate_travel_date(self, value):
        from django.utils import timezone
        if value < timezone.now().date():
            raise serializers.ValidationError("Travel date must be in the future.")
        return value

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        from users.serializers import UserProfileSerializer  # Lazy import to avoid circular import
        representation['user'] = UserProfileSerializer(instance.user, context=self.context).data
        return representation

class PackageRequestSerializer(serializers.ModelSerializer):
    travel_listing = serializers.PrimaryKeyRelatedField(queryset=TravelListing.objects.all())
    package_types = serializers.PrimaryKeyRelatedField(queryset=PackageType.objects.all(), many=True, required=False)
    total_price = serializers.ReadOnlyField()

    class Meta:
        model = PackageRequest
        fields = [
            'id', 'user', 'travel_listing', 'package_description', 'weight',
            'number_of_document', 'number_of_phone', 'number_of_tablet',
            'number_of_pc', 'number_of_full_suitcase', 
            'package_types', 'total_price', 'status', 'created_at', 'updated_at'
        ]
        read_only_fields = ['user', 'status', 'created_at', 'updated_at', 'total_price']

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        from users.serializers import UserProfileSerializer  # Lazy import to avoid circular import
        representation['user'] = UserProfileSerializer(instance.user, context=self.context).data
        representation['package_types'] = PackageTypeSerializer(instance.package_types.all(), many=True).data
        return representation

    def validate(self, data):
        """
        Ensure the travel listing is published and the user is not the owner.
        Also check that package_description is provided if weight is greater than 0.
        Also check that requested weight does not exceed available weight and travel has not started.
        """
        weight = data.get('weight', getattr(self.instance, 'weight', Decimal('0.0')))
        description = data.get('package_description', getattr(self.instance, 'package_description', ''))

        if Decimal(weight) > 0 and not description.strip():
            raise serializers.ValidationError({
                "package_description": "A description is required when specifying a weight."
            })
        # Ensure travel listing is published and user is not the owner
        request = self.context.get('request')
        travel_listing = data.get('travel_listing')
        if travel_listing:
            if travel_listing.status != 'published':
                raise serializers.ValidationError({
                    "travel_listing": "You can only create a package request for a published travel listing."
                })
            if request and travel_listing.user == request.user:
                raise serializers.ValidationError({
                    "travel_listing": "You cannot create a package request for your own travel listing."
                })
            # Check travel has not started
            from datetime import datetime, time
            now = datetime.now()
            travel_datetime = datetime.combine(travel_listing.travel_date, travel_listing.travel_time)
            if travel_datetime <= now:
                raise serializers.ValidationError({
                    "travel_listing": "You cannot create a package request for a travel that has already started."
                })
            # Check available weight
            # Sum accepted package weights for this travel listing
            from listings.models import PackageRequest
            accepted_weight = PackageRequest.objects.filter(
                travel_listing=travel_listing, status='accepted'
            ).aggregate(Sum('weight'))['weight__sum'] or Decimal('0.0')
            
            # If we are updating an existing request that is already accepted, 
            # we should not count its own weight in the accepted_weight sum
            if self.instance and self.instance.status == 'accepted':
                accepted_weight -= self.instance.weight

            available_weight = travel_listing.maximum_weight_in_kg - accepted_weight
            if Decimal(weight) > available_weight:
                raise serializers.ValidationError({
                    "weight": f"Requested weight ({weight}kg) exceeds available capacity ({available_weight}kg)."
                })
        
        # Check wallet balance for package request creation
        if not self.instance:  # Only on creation
            request = self.context.get('request')
            if request and travel_listing:
                # Calculate total price to check if user has enough balance
                total_price = self._calculate_price(data, travel_listing)
                from money.wallet_service import WalletService
                if not WalletService.check_balance_for_request(request.user, total_price):
                    from money.models import PlatformConfig
                    config = PlatformConfig.get_config()
                    required = config.min_balance_for_package_request + total_price
                    raise serializers.ValidationError({
                        "wallet": f"Insufficient wallet balance. You need {required} ETB (fee: {config.min_balance_for_package_request}, package price: {total_price})."
                    })
        
        return data

    def _calculate_price(self, validated_data, travel_listing):
        price = Decimal('0.0')
        
        # Handle case where fields might not be in validated_data (on update)
        instance = getattr(self, 'instance', None)

        def get_value(field_name):
            return validated_data.get(field_name, getattr(instance, field_name, 0))

        # Price per kg
        weight = get_value('weight')
        if weight and travel_listing.price_per_kg:
            price += Decimal(weight) * Decimal(travel_listing.price_per_kg)

        # Price per item
        item_prices = {
            'number_of_document': travel_listing.price_per_document,
            'number_of_phone': travel_listing.price_per_phone,
            'number_of_tablet': travel_listing.price_per_tablet,
            'number_of_pc': travel_listing.price_per_pc,
            'number_of_full_suitcase': travel_listing.price_full_suitcase,
        }

        for field, item_price in item_prices.items():
            count = get_value(field)
            if count and item_price:
                price += Decimal(count) * Decimal(item_price)
                
        return price

    def create(self, validated_data):
        travel_listing = validated_data['travel_listing']
        total_price = self._calculate_price(validated_data, travel_listing)
        validated_data['total_price'] = total_price
        
        # Create the package request
        package_request = super().create(validated_data)
        
        # Deduct fee and lock payment amount
        from money.wallet_service import WalletService, InsufficientBalanceError
        try:
            WalletService.deduct_request_fee_and_lock_amount(package_request.user, package_request)
        except InsufficientBalanceError as e:
            # If fee deduction/lock fails, delete the package request and raise error
            package_request.delete()
            raise serializers.ValidationError(str(e))
        
        return package_request

    def update(self, instance, validated_data):
        travel_listing = validated_data.get('travel_listing', instance.travel_listing)
        total_price = self._calculate_price(validated_data, travel_listing)
        validated_data['total_price'] = total_price
        return super().update(instance, validated_data)

class AlertSerializer(serializers.ModelSerializer):
    user = serializers.ReadOnlyField(source='user.username')
    pickup_country = CountrySerializer(read_only=True)
    pickup_country_id = serializers.PrimaryKeyRelatedField(queryset=Country.objects.all(), source='pickup_country', write_only=True)
    pickup_region = RegionSerializer(read_only=True)
    pickup_region_id = serializers.PrimaryKeyRelatedField(queryset=Region.objects.all(), source='pickup_region', write_only=True)
    destination_country = CountrySerializer(read_only=True)
    destination_country_id = serializers.PrimaryKeyRelatedField(queryset=Country.objects.all(), source='destination_country', write_only=True)
    destination_region = RegionSerializer(read_only=True)
    destination_region_id = serializers.PrimaryKeyRelatedField(queryset=Region.objects.all(), source='destination_region', write_only=True)

    class Meta:
        model = Alert
        fields = [
            'id', 'user',
            'pickup_country', 'pickup_country_id',
            'pickup_region', 'pickup_region_id',
            'destination_country', 'destination_country_id',
            'destination_region', 'destination_region_id',
            'from_travel_date', 'to_travel_date',
            'notify_for_any_pickup_city', 'notify_for_any_destination_city',
            'notify_me',
            'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'user', 'created_at', 'updated_at',
            'pickup_country', 'pickup_region', 'destination_country', 'destination_region'
        ]

class ReviewSerializer(serializers.ModelSerializer):
    reviewer = serializers.ReadOnlyField(source='reviewer.username')
    travel_listing = serializers.PrimaryKeyRelatedField(read_only=True)
    class Meta:
        model = Review
        fields = ['id', 'travel_listing', 'package_request', 'reviewer', 'rate', 'description', 'created_at']
        read_only_fields = ['id', 'reviewer', 'created_at', 'travel_listing']

    def validate(self, data):
        request = self.context['request']
        user = request.user
        package_request = data.get('package_request')
        # Only package request owner can review
        if package_request.user != user:
            raise serializers.ValidationError('You can only review as the package request owner.')
        # Only if package request is completed
        if package_request.status != 'completed':
            raise serializers.ValidationError('You can only review after the package request is completed.')
        travel_listing = package_request.travel_listing
        # Only one review per travel listing per user
        if Review.objects.filter(travel_listing=travel_listing, reviewer=user).exists():
            raise serializers.ValidationError('You have already reviewed this travel listing.')
        data['travel_listing'] = travel_listing
        return data

    def create(self, validated_data):
        # travel_listing is set in validate
        return super().create(validated_data) 