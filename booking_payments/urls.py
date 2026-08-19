from django.urls import path
from . import views

urlpatterns = [
    path('checkout/<uuid:reservation_uuid>/', views.checkout_view, name='checkout_view'),
    path('checkout/<uuid:reservation_uuid>/pay-mock/', views.process_mock_payment_view, name='process_mock_payment_view'),
    path('ticket/<str:ticket_number>/', views.ticket_detail_view, name='ticket_detail_view'),
    path('ticket/<str:ticket_number>/download-pdf/', views.download_ticket_pdf_view, name='download_ticket_pdf_view'),
]
