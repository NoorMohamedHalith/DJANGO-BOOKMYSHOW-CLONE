from django.urls import path
from . import views

urlpatterns = [
    path('api/payments/create-order/', views.create_order_api, name='create_order_api'),
    path('api/payments/webhook/', views.webhook_view, name='payments_webhook'),
    path('payments/checkout/<uuid:reservation_uuid>/', views.checkout_view, name='payment_checkout'),
    path('payments/callback/success/', views.payment_success_callback_view, name='payment_success_callback'),
    path('payments/callback/failure/', views.payment_failure_callback_view, name='payment_failure_callback'),
    path('payments/history/', views.user_payment_history_view, name='user_payment_history'),
]
