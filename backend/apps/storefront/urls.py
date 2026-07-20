from django.urls import path

from . import views

app_name = 'storefront'

urlpatterns = [
    path('', views.home, name='home'),
    path('books/', views.book_list, name='book_list'),
    path('books/<slug:slug>/', views.book_detail, name='book_detail'),

    path('cart/', views.cart_view, name='cart'),
    path('cart/add/<int:book_id>/', views.cart_add, name='cart_add'),
    path('cart/update/<int:book_id>/', views.cart_update, name='cart_update'),
    path('cart/remove/<int:book_id>/', views.cart_remove, name='cart_remove'),

    path('checkout/', views.checkout, name='checkout'),
    path('checkout/delivery-fee/', views.delivery_fee_estimate, name='delivery_fee_estimate'),
    path('checkout/callback/', views.paystack_callback, name='paystack_callback'),

    path('orders/<uuid:offline_uuid>/', views.order_confirmation, name='order_confirmation'),
    path('orders/<uuid:offline_uuid>/confirm-receipt/', views.confirm_receipt, name='confirm_receipt'),
    path('orders/<uuid:offline_uuid>/review/', views.submit_review, name='submit_review'),
]
