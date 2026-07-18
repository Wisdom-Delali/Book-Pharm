from django.urls import path

from apps.reports import views as report_views

from . import auth_views, discount_views, expense_views, orders_views, reconciliation_views, views

app_name = 'portal'

urlpatterns = [
    path('login/', auth_views.login_view, name='login'),
    path('logout/', auth_views.logout_view, name='logout'),
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
    path('expenses/', expense_views.expense_list, name='expense_list'),
    path('expenses/new/', expense_views.expense_create, name='expense_create'),
    path('expenses/<int:pk>/edit/', expense_views.expense_update, name='expense_update'),
    path('reports/sales/', report_views.sales_report, name='reports_sales'),
    path('reports/profit/', report_views.profit_report, name='reports_profit'),
    path('reports/stock/', report_views.stock_report, name='reports_stock'),
    path('reports/expenses/', report_views.expense_report, name='reports_expenses'),
    path('orders/', orders_views.order_list, name='order_list'),
    path('orders/<int:pk>/', orders_views.order_detail, name='order_detail'),
    path('orders/rider-queue/', orders_views.rider_queue, name='rider_queue'),
    path('orders/fulfillment/<int:pk>/mark-rider-booked/', orders_views.mark_rider_booked, name='mark_rider_booked'),
]
