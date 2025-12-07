from django.urls import path
from . import views

urlpatterns = [
    # Authentication endpoints
    path('auth/register', views.register, name='register'),
    path('auth/login', views.login, name='login'),
    path('auth/me', views.me, name='me'),
    
    # Payment endpoints
    path('payments/registration/create-checkout', views.create_registration_payment_checkout, name='create_checkout'),
    path('payments/webhook', views.stripe_webhook, name='stripe_webhook'),
]