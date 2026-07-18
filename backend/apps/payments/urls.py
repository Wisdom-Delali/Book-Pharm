from django.urls import path

from . import views

app_name = 'payments'

urlpatterns = [
    path('paystack/webhook/', views.paystack_webhook, name='paystack_webhook'),
]
