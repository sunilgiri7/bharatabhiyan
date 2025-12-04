from django.urls import path
from . import views

urlpatterns = [
    # Authentication endpoints
    path('auth/register', views.register, name='register'),
    path('auth/login', views.login, name='login'),
    path('auth/me', views.me, name='me'),
    
    # Payment endpoints
    path('payments/registration/create-order', views.create_registration_payment_order, name='create_payment_order'),
    path('payments/registration/verify', views.verify_registration_payment, name='verify_payment'),
]