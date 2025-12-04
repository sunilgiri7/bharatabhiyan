from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, UserProfile, RegistrationPayment


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ['phone', 'name', 'email', 'is_active', 'is_admin', 'is_captain', 'date_joined']
    list_filter = ['is_active', 'is_admin', 'is_captain', 'date_joined']
    search_fields = ['phone', 'name', 'email']
    ordering = ['-date_joined']
    
    fieldsets = (
        (None, {'fields': ('phone', 'password')}),
        ('Personal Info', {'fields': ('name', 'email')}),
        ('Roles', {'fields': ('is_admin', 'is_captain')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('phone', 'name', 'email', 'password1', 'password2', 'is_active'),
        }),
    )


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'city', 'pincode', 'kyc_status']
    list_filter = ['kyc_status', 'city']
    search_fields = ['user__name', 'user__phone', 'pincode']


@admin.register(RegistrationPayment)
class RegistrationPaymentAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'amount', 'status', 'gateway_order_id', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['user__name', 'user__phone', 'gateway_order_id', 'gateway_ref']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']