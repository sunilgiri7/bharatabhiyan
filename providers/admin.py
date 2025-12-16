from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from .models import (
    ServiceCategory, ServiceType, ServiceArea,
    ServiceProvider, ProviderSubscription
)


@admin.register(ServiceCategory)
class ServiceCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'icon', 'is_active', 'created_at']
    list_filter = ['is_active']
    search_fields = ['name']


@admin.register(ServiceType)
class ServiceTypeAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'is_active', 'created_at']
    list_filter = ['category', 'is_active']
    search_fields = ['name', 'category__name']


@admin.register(ServiceArea)
class ServiceAreaAdmin(admin.ModelAdmin):
    list_display = ['name', 'location', 'is_active', 'created_at']
    list_filter = ['location', 'is_active']
    search_fields = ['name', 'location__name']


@admin.register(ServiceProvider)
class ServiceProviderAdmin(admin.ModelAdmin):
    list_display = [
        'application_id', 'business_name', 'user_name', 'user_phone',
        'verification_status_badge', 'city', 'submitted_at'
    ]
    list_filter = [
        'verification_status', 'service_category', 'city',
        'experience', 'submitted_at'
    ]
    search_fields = [
        'application_id', 'business_name', 'user__name',
        'user__phone', 'user__email'
    ]
    readonly_fields = [
        'application_id', 'user', 'created_at', 'updated_at', 'submitted_at'
    ]
    
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
                'service_category', 'service_type', 'service_description',
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