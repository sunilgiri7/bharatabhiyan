from django.urls import path
from . import views, provider_views

urlpatterns = [
    # Authentication endpoints
    path('auth/register', views.register, name='register'),
    path('auth/login', views.login, name='login'),
    path('auth/me', views.me, name='me'),
    
    # User Registration Payment
    path('payments/registration/create-link', views.create_payment_link, name='create_payment_link'),
    path('payments/registration/checkout/<int:payment_id>', views.payment_checkout, name='payment_checkout'),
    path('payments/registration/callback', views.payment_callback, name='payment_callback'),
    path('payments/registration/status/<int:payment_id>', views.check_payment_status, name='check_payment_status'),
    
    # Provider Helper APIs (dropdowns/lists)
    path('providers/categories', provider_views.get_service_categories, name='get_service_categories'),
    path('providers/service-types', provider_views.get_service_types, name='get_service_types'),
    path('providers/service-areas', provider_views.get_service_areas, name='get_service_areas'),
    path('services/', provider_views.get_services, name='get-services'),
    path('providers/by-area/', provider_views.get_providers_by_area, name='providers-by-area'),
    
    # Provider Registration APIs
    path('providers/profile', provider_views.create_provider_profile, name='create_provider_profile'),
    path('providers/profile/me', provider_views.get_provider_profile, name='get_provider_profile'),
    path('providers/profile/submit', provider_views.submit_provider_application, name='submit_provider_application'),
    
    # Provider Subscription & Payment
    path('providers/subscription/create', provider_views.create_subscription_payment, name='create_subscription_payment'),
    path('providers/subscription/checkout/<int:subscription_id>', provider_views.subscription_payment_checkout, name='subscription_payment_checkout'),
    path('providers/subscription/callback', provider_views.subscription_payment_callback, name='subscription_payment_callback'),
    path('providers/subscription/status/<int:subscription_id>', provider_views.check_subscription_status, name='check_subscription_status'),
    path('providers/subscription/active', provider_views.get_active_subscription, name='get_active_subscription'),

    path('ai/guide/', views.get_ai_guide, name='ai-guide'),
]