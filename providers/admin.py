from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone

from accounts.models import CaptainProfile, User, UserProfile
from .models import (
    GovernmentService, ServiceCategory, ServiceQuestion, ServiceType, ServiceArea,
    ServiceProvider, ProviderSubscription
)


@admin.register(ServiceCategory)
class ServiceCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'icon', 'short_description', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'description']
    ordering = ['-created_at']
    list_editable = ['is_active']


    def short_description(self, obj):
        return (obj.description[:60] + '...') if obj.description else '—'

    short_description.short_description = "Description"


@admin.register(ServiceType)
class ServiceTypeAdmin(admin.ModelAdmin):
    list_display = ['name', 'get_categories', 'is_active', 'created_at']
    list_filter = ['category', 'is_active'] # Note: 'category' here is the related name from ServiceType model (ForeignKey)
    search_fields = ['name', 'category__name']

    def get_categories(self, obj):
        return obj.category.name if obj.category else "-"
    get_categories.short_description = 'Category'


@admin.register(ServiceArea)
class ServiceAreaAdmin(admin.ModelAdmin):
    list_display = ['name', 'location', 'is_active', 'created_at']
    list_filter = ['location', 'is_active']
    search_fields = ['name', 'location__name']


@admin.register(ServiceProvider)
class ServiceProviderAdmin(admin.ModelAdmin):
    # UPDATED: 'service_category' removed, added 'get_categories_display'
    list_display = [
        'application_id', 'business_name', 'user_name', 'user_phone',
        'verification_status_badge', 'get_categories_display', 'city', 'submitted_at'
    ]
    
    # UPDATED: Filter by the new ManyToMany fields
    list_filter = [
        'verification_status', 
        'service_categories', # Renamed from service_category
        'service_types',      # Added service_types
        'city',
        'experience', 
        'submitted_at'
    ]
    
    search_fields = [
        'application_id', 'business_name', 'user__name',
        'user__phone', 'user__email'
    ]
    
    readonly_fields = [
        'application_id', 'user', 'created_at', 'updated_at', 'submitted_at'
    ]
    
    # UPDATED: Fieldsets to include new M2M fields
    fieldsets = (
        ('Application Info', {
            'fields': ('application_id', 'user', 'verification_status', 'submitted_at')
        }),
        ('Business Details', {
            'fields': (
                'business_name', 'experience', 'business_address',
                'city', 'pincode', 'whatsapp_number'
            )
        }),
        ('Service Details', {
            'fields': (
                'service_categories', # Renamed
                'service_types',      # Renamed
                'service_description',
                'service_areas'
            )
        }),
        ('Documents', {
            'fields': (
                'aadhaar_front', 'aadhaar_back', 'address_proof_type',
                'address_proof', 'profile_photo', 'skill_certificate'
            )
        }),
        ('Verification', {
            'fields': (
                'verified_by', 'verification_date', 'rejection_reason'
            )
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    
    # NEW: Helper to display M2M categories in list_display
    def get_categories_display(self, obj):
        return ", ".join([c.name for c in obj.service_categories.all()])
    get_categories_display.short_description = 'Service Categories'

    def user_name(self, obj):
        return obj.user.name
    user_name.short_description = 'Provider Name'
    
    def user_phone(self, obj):
        return obj.user.phone
    user_phone.short_description = 'Phone'
    
    def verification_status_badge(self, obj):
        colors = {
            'DRAFT': 'gray',
            'PENDING_VERIFICATION': 'orange',
            'VERIFIED': 'green',
            'REJECTED': 'red',
        }
        color = colors.get(obj.verification_status, 'gray')
        return format_html(
            '<span style="background: {}; color: white; padding: 4px 8px; '
            'border-radius: 4px; font-size: 11px; font-weight: bold;">{}</span>',
            color,
            obj.get_verification_status_display()
        )
    verification_status_badge.short_description = 'Status'
    
    actions = ['verify_providers', 'reject_providers']
    
    def verify_providers(self, request, queryset):
        if not request.user.is_captain and not request.user.is_admin:
            self.message_user(request, "Only captains can verify providers.", level='error')
            return
        
        count = queryset.filter(
            verification_status='PENDING_VERIFICATION'
        ).update(
            verification_status='VERIFIED',
            verified_by=request.user,
            verification_date=timezone.now()
        )
        self.message_user(request, f'{count} provider(s) verified successfully.')
    verify_providers.short_description = "Verify selected providers"
    
    def reject_providers(self, request, queryset):
        if not request.user.is_captain and not request.user.is_admin:
            self.message_user(request, "Only captains can reject providers.", level='error')
            return
        
        count = queryset.filter(
            verification_status='PENDING_VERIFICATION'
        ).update(
            verification_status='REJECTED',
            verified_by=request.user,
            verification_date=timezone.now()
        )
        self.message_user(request, f'{count} provider(s) rejected. Please add rejection reason manually.')
    reject_providers.short_description = "Reject selected providers"


@admin.register(ProviderSubscription)
class ProviderSubscriptionAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'provider_name', 'plan_type_badge', 'amount',
        'status_badge', 'start_date', 'end_date'
    ]
    list_filter = ['plan_type', 'status', 'created_at']
    search_fields = [
        'provider__business_name', 'provider__user__name',
        'gateway_order_id', 'gateway_payment_id'
    ]
    readonly_fields = [
        'provider', 'created_at', 'updated_at'
    ]
    
    def provider_name(self, obj):
        return obj.provider.business_name
    provider_name.short_description = 'Provider'
    
    def plan_type_badge(self, obj):
        color = '#FF9933' if obj.plan_type == 'YEARLY' else '#005ea2'
        return format_html(
            '<span style="background: {}; color: white; padding: 4px 8px; '
            'border-radius: 4px; font-size: 11px; font-weight: bold;">{}</span>',
            color,
            obj.get_plan_type_display()
        )
    plan_type_badge.short_description = 'Plan'
    
    def status_badge(self, obj):
        colors = {
            'PENDING': 'orange',
            'ACTIVE': 'green',
            'EXPIRED': 'gray',
            'CANCELLED': 'red',
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="background: {}; color: white; padding: 4px 8px; '
            'border-radius: 4px; font-size: 11px; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'

class ServiceQuestionInline(admin.TabularInline):
    """
    Add/Edit questions directly inside a Government Service
    """
    model = ServiceQuestion
    extra = 1
    fields = ("question", "created_at")
    readonly_fields = ("created_at",)


@admin.register(GovernmentService)
class GovernmentServiceAdmin(admin.ModelAdmin):
    list_display = ("name", "short_description", "created_at")
    search_fields = ("name", "description")
    ordering = ("-created_at",)

    inlines = [ServiceQuestionInline]

    def short_description(self, obj):
        if not obj.description:
            return "—"
        return obj.description[:60] + ("..." if len(obj.description) > 60 else "")

    short_description.short_description = "Description Preview"


@admin.register(ServiceQuestion)
class ServiceQuestionAdmin(admin.ModelAdmin):
    list_display = ("question_preview", "service", "created_at")
    list_filter = ("service", "created_at")
    search_fields = ("question",)
    ordering = ("-created_at",)

    def question_preview(self, obj):
        return obj.question[:70] + ("..." if len(obj.question) > 70 else "")

    question_preview.short_description = "Question"

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'phone', 'email', 'is_captain', 'is_user', 'admin_verified', 'is_active', 'date_joined']
    list_filter = ['is_captain', 'is_user', 'admin_verified', 'is_active', 'date_joined']
    search_fields = ['name', 'phone', 'email', 'captain_code']
    readonly_fields = ['date_joined', 'captain_code']
    
    fieldsets = (
        ('Personal Information', {
            'fields': ('phone', 'email', 'name', 'password')
        }),
        ('Role & Permissions', {
            'fields': ('is_captain', 'is_user', 'is_admin', 'is_staff', 'is_superuser')
        }),
        ('Captain Details', {
            'fields': ('captain_code', 'admin_verified')
        }),
        ('Status', {
            'fields': ('is_active', 'date_joined')
        }),
    )


@admin.register(CaptainProfile)
class CaptainProfileAdmin(admin.ModelAdmin):
    list_display = [
        'id', 
        'captain_name', 
        'captain_code', 
        'phone', 
        'verification_status_badge', 
        'created_at'
    ]
    list_filter = ['verification_status', 'created_at']
    search_fields = ['user__name', 'user__captain_code', 'phone']
    readonly_fields = [
        'user', 
        'created_at', 
        'updated_at', 
        'verified_by', 
        'verification_date',
        'display_aadhaar_front',
        'display_aadhaar_back'
    ]
    
    fieldsets = (
        ('Captain Information', {
            'fields': ('user', 'phone')
        }),
        ('Documents', {
            'fields': ('display_aadhaar_front', 'display_aadhaar_back')
        }),
        ('Verification Details', {
            'fields': (
                'verification_status', 
                'verified_by', 
                'verification_date', 
                'rejection_reason'
            )
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    
    actions = ['verify_captains', 'reject_captains']
    
    def captain_name(self, obj):
        return obj.user.name
    captain_name.short_description = 'Captain Name'
    
    def captain_code(self, obj):
        return obj.user.captain_code
    captain_code.short_description = 'Captain Code'
    
    def verification_status_badge(self, obj):
        colors = {
            'PENDING': 'orange',
            'VERIFIED': 'green',
            'REJECTED': 'red'
        }
        color = colors.get(obj.verification_status, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            color,
            obj.get_verification_status_display()
        )
    verification_status_badge.short_description = 'Status'
    
    def display_aadhaar_front(self, obj):
        if obj.aadhaar_front:
            return format_html(
                '<a href="{}" target="_blank"><img src="{}" style="max-width: 300px; max-height: 200px;"/></a>',
                obj.aadhaar_front.url,
                obj.aadhaar_front.url
            )
        return "No image"
    display_aadhaar_front.short_description = 'Aadhaar Front'
    
    def display_aadhaar_back(self, obj):
        if obj.aadhaar_back:
            return format_html(
                '<a href="{}" target="_blank"><img src="{}" style="max-width: 300px; max-height: 200px;"/></a>',
                obj.aadhaar_back.url,
                obj.aadhaar_back.url
            )
        return "No image"
    display_aadhaar_back.short_description = 'Aadhaar Back'
    
    def verify_captains(self, request, queryset):
        """Verify selected captains"""
        updated = 0
        for captain_profile in queryset.filter(verification_status='PENDING'):
            captain_profile.verification_status = 'VERIFIED'
            captain_profile.verified_by = request.user
            captain_profile.verification_date = timezone.now()
            captain_profile.rejection_reason = ''
            captain_profile.save()
            
            # Update user's admin_verified flag
            captain_profile.user.admin_verified = True
            captain_profile.user.save()
            
            updated += 1
        
        self.message_user(request, f'{updated} captain(s) verified successfully.')
    verify_captains.short_description = 'Verify selected captains'
    
    def reject_captains(self, request, queryset):
        """Reject selected captains"""
        updated = 0
        for captain_profile in queryset.filter(verification_status='PENDING'):
            captain_profile.verification_status = 'REJECTED'
            captain_profile.verified_by = request.user
            captain_profile.verification_date = timezone.now()
            captain_profile.save()
            
            # Update user's admin_verified flag
            captain_profile.user.admin_verified = False
            captain_profile.user.save()
            
            updated += 1
        
        self.message_user(request, f'{updated} captain(s) rejected.')
    reject_captains.short_description = 'Reject selected captains'


# @admin.register(UserProfile)
# class UserProfileAdmin(admin.ModelAdmin):
#     list_display = ['id', 'user', 'city', 'kyc_status']
#     list_filter = ['kyc_status']
#     search_fields = ['user__name', 'user__phone']