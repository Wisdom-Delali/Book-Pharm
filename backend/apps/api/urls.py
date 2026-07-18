from django.urls import path

from . import views

app_name = 'api'

urlpatterns = [
    path('me/', views.MeView.as_view(), name='me'),
    path('catalog/', views.BookSyncListView.as_view(), name='catalog_list'),
    path('catalog/lookup/', views.BookLookupView.as_view(), name='catalog_lookup'),
    path('sales/', views.SaleCreateView.as_view(), name='sale_create'),
]
