from django.urls import path

from . import views

app_name = 'messaging'

urlpatterns = [
    path('unsubscribe/<str:token>/', views.unsubscribe, name='unsubscribe'),
]
