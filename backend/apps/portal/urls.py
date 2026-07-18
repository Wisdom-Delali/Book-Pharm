from django.urls import path

from . import discount_views, reconciliation_views, views

app_name = 'portal'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('catalog/', views.book_list, name='book_list'),
    path('catalog/books/new/', views.book_create, name='book_create'),
    path('catalog/books/<int:pk>/edit/', views.book_update, name='book_update'),
    path('catalog/books/<int:pk>/adjust-stock/', views.stock_adjust, name='stock_adjust'),
    path('discounts/', discount_views.discount_list, name='discount_list'),
    path('discounts/new/', discount_views.discount_create, name='discount_create'),
    path('discounts/<int:pk>/edit/', discount_views.discount_update, name='discount_update'),
    path('reconciliation/', reconciliation_views.reconciliation_list, name='reconciliation_list'),
    path('reconciliation/<int:pk>/resolve/', reconciliation_views.reconciliation_resolve, name='reconciliation_resolve'),
]
