from django.contrib import admin
from django.urls import include, path
from apis import views as payment_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('apis.urls')),

    # Payment success/failure pages
    path('payment/success', payment_views.payment_success, name='payment_success'),
    path('payment/failure', payment_views.payment_failure, name='payment_failure'),
]
