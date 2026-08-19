from django.db import models
from django.contrib.auth.models import User
from movies.models import Booking
from seat_reservations.models import SeatReservation


class PaymentTransaction(models.Model):
    STATUS_CHOICES = (
        ('INITIATED', 'Initiated'),
        ('SUCCESS', 'Success'),
        ('FAILED', 'Failed'),
        ('CANCELLED', 'Cancelled'),
        ('PENDING', 'Pending'),
    )

    GATEWAY_CHOICES = (
        ('RAZORPAY', 'Razorpay'),
        ('STRIPE', 'Stripe'),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='payment_transactions')
    booking = models.ForeignKey(Booking, on_delete=models.SET_NULL, null=True, blank=True, related_name='payment_transactions')
    reservation = models.ForeignKey(SeatReservation, on_delete=models.SET_NULL, null=True, blank=True, related_name='payment_transactions')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_gateway = models.CharField(max_length=20, choices=GATEWAY_CHOICES, default='RAZORPAY')
    gateway_transaction_id = models.CharField(max_length=100, unique=True, db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='INITIATED')
    payment_data = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    webhook_received_at = models.DateTimeField(null=True, blank=True)
    webhook_signature_valid = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user.username} - {self.gateway_transaction_id} - {self.status}"


class PaymentLog(models.Model):
    transaction = models.ForeignKey(PaymentTransaction, on_delete=models.CASCADE, related_name='logs')
    event = models.CharField(max_length=50)
    message = models.TextField(blank=True, default='')
    data = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.transaction.gateway_transaction_id} - {self.event} at {self.created_at}"
