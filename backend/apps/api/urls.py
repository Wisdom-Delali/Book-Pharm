from django.urls import path

from . import views

app_name = 'api'

urlpatterns = [
    path('auth/login/', views.DesktopLoginView.as_view(), name='desktop_login'),
    path('me/', views.MeView.as_view(), name='me'),
    path('catalog/', views.BookSyncListView.as_view(), name='catalog_list'),
    path('catalog/lookup/', views.BookLookupView.as_view(), name='catalog_lookup'),
    path('customers/lookup/', views.CustomerLookupView.as_view(), name='customer_lookup'),
    path('sales/', views.SaleCreateView.as_view(), name='sale_create'),
    path('sales/mine/', views.MySalesView.as_view(), name='sale_mine'),
    path('sync/sales/', views.SaleBatchSyncView.as_view(), name='sale_batch_sync'),
]
