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
    path('sales/momo-charge/', views.MomoChargeView.as_view(), name='momo_charge'),
    path('sales/<uuid:offline_uuid>/cancel/', views.CancelPendingSaleView.as_view(), name='cancel_pending_sale'),
    path('sync/sales/', views.SaleBatchSyncView.as_view(), name='sale_batch_sync'),
    path('payments/in-store/', views.InStorePaymentsListView.as_view(), name='payments_in_store'),
    path('payments/<uuid:offline_uuid>/status/', views.PaymentStatusView.as_view(), name='payment_status'),
]
