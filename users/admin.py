from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, Profile, OTP, IdType, TravelPriceSetting
from messaging.utils import send_notification_to_user

class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    verbose_name_plural = 'Profile'
    fields = ('profile_picture_url',  
              'front_side_identity_card_url', 'back_side_identity_card_url', 'selfie_photo_url', 
              'address', )
    readonly_fields = ('created_at', 'updated_at')

class CustomUserAdmin(UserAdmin):
    inlines = (ProfileInline,)
    list_display = ('id', 'email', 'username', 'first_name', 'last_name', 'is_staff',
                   'is_email_verified', 'is_phone_verified', 'is_identity_verified',
                   'is_profile_completed', 'privacy_policy_accepted', 'date_privacy_accepted')
    list_filter = ('is_staff', 'is_superuser', 'is_email_verified', 'is_phone_verified',
                  'is_identity_verified', 'is_profile_completed', 'privacy_policy_accepted')
    search_fields = ('email', 'username', 'first_name', 'last_name', 'phone_number')
    ordering = ('email',)
    
    fieldsets = (
        (None, {'fields': ('email', 'username', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'phone_number', 'google_id','apple_id')}),
        ('Verification Status', {'fields': ('is_email_verified', 'is_phone_verified', 
                                          'is_identity_verified', 'is_profile_completed')}),
        ('Privacy Policy', {'fields': ('privacy_policy_accepted', 'date_privacy_accepted')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser',
                                  'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'username', 'password1', 'password2', 'phone_number'),
        }),
    )

    def get_readonly_fields(self, request, obj=None):
        # Make all fields readonly except is_identity_verified
        all_fields = [
            # 'email', 'username', 'password', 'first_name', 'last_name', 'phone_number',
            # 'is_email_verified', 'is_phone_verified', 'is_profile_completed',
            # 'privacy_policy_accepted', 'date_privacy_accepted', 'is_active', 'is_staff',
            # 'is_superuser', 'groups', 'user_permissions', 'last_login', 'date_joined'
        ]
        # Remove is_identity_verified from readonly
        readonly = [f for f in all_fields if f != 'is_identity_verified']
        return readonly
    
    # when is_identity_verified chagned to completed, send notification to user
    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        from datetime import datetime

        # Check if is_identity_verified changed to completed
        if 'is_identity_verified' in form.changed_data and obj.is_identity_verified == 'completed':
            # Send verification notification to user
            notification_data = {
                'message': "Your identity verification has been completed successfully.",
                'is_read':False,
                'created_at': datetime.now().isoformat(),
            }
            send_notification_to_user(obj.id, notification_data)
        
        if 'is_identity_verified' in form.changed_data and obj.is_identity_verified == 'rejected':
            # Send verification notification to user
            notification_data = {
                'message': "Your identity verification has been rejected.",
                'is_read':False,
                'created_at': datetime.now().isoformat(),
            }
            send_notification_to_user(obj.id, notification_data)

        if obj.is_identity_verified == 'completed' and obj.is_phone_verified and obj.is_email_verified:
            # Update is_profile_completed if all verifications are done
            obj.is_profile_completed = True
            obj.save()

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'user', 'profile_picture_url', 
        'selfie_photo_url', 'address', 'city_of_residence', 'id_type',
        'issue_country', 'front_side_identity_card_url', 'back_side_identity_card_url',
        # 'created_at', 'updated_at'
    )
    list_filter = ('created_at', 'updated_at')
    search_fields = ('user__email', 'user__username', 'address')
    readonly_fields = (
    #     'user', 'profile_picture_url', 
    #     'selfie_photo_url', 'address', 'city_of_residence', 'id_type',
    #     'issue_country', 'front_side_identity_card_url', 'back_side_identity_card_url',
        'created_at', 'updated_at'
    )
    fieldsets = (
        ('User Information', {'fields': ('user',)}),
        ('Contact Information', {'fields': ('address',)}),
        ('Profile Details', {'fields': ('profile_picture_url', )}),
        ('Location & ID', {'fields': ('city_of_residence', 'id_type', 'issue_country')}),
        ('Verification Documents', {'fields': ('front_side_identity_card_url', 'back_side_identity_card_url', 'selfie_photo_url')}),
        ('Timestamps', {'fields': ('created_at', 'updated_at')}),
    )

@admin.register(OTP)
class OTPAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'phone_number', 'code', 'purpose', 'created_at', 'is_used')
    list_filter = ('purpose', 'is_used', 'created_at')
    search_fields = ('user__email', 'user__username', 'code', 'user__phone_number')
    ordering = ('-created_at',)
    readonly_fields = ('created_at',)

    def phone_number(self, obj):
        return obj.user.phone_number
    phone_number.short_description = 'Phone Number'

@admin.register(IdType)
class IdTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'description', 'created_at', 'updated_at')
    search_fields = ('name',)
    readonly_fields = ('created_at', 'updated_at')

admin.site.register(CustomUser, CustomUserAdmin)


@admin.register(TravelPriceSetting)
class TravelPriceSettingAdmin(admin.ModelAdmin):
    list_display = ('price_per_kg', 'price_per_document', 'price_per_phone', 'price_per_tablet', 'price_per_pc', 'price_full_suitcase')
    search_fields = ('price_per_kg', 'price_per_document')
    readonly_fields = ('created_at', 'updated_at')