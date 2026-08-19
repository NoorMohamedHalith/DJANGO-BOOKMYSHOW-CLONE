import uuid
from django.db import models
from seat_reservations.models import SeatReservation


class Payment(models.Model):
    PAYMENT_METHOD_CHOICES = [
        ('MOCK', 'Mock Payment'),
        ('RAZORPAY', 'Razorpay'),
        ('STRIPE', 'Stripe'),
    ]

    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('SUCCESS', 'Success'),
        ('FAILED', 'Failed'),
        ('REFUNDED', 'Refunded'),
    ]

    reservation = models.OneToOneField(SeatReservation, on_delete=models.CASCADE, related_name='payment')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=50, choices=PAYMENT_METHOD_CHOICES, default='MOCK')
    payment_id = models.CharField(max_length=100, unique=True, db_index=True)
    order_id = models.CharField(max_length=100, blank=True, default='')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Payment {self.payment_id} ({self.status}) - ₹{self.amount}"


class Ticket(models.Model):
    payment = models.OneToOneField(Payment, on_delete=models.CASCADE, related_name='ticket')
    ticket_number = models.CharField(max_length=50, unique=True, db_index=True)
    qr_code = models.ImageField(upload_to='tickets/qr/', blank=True, null=True)
    pdf_file = models.FileField(upload_to='tickets/pdf/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Ticket {self.ticket_number} for {self.payment.reservation.user.username}"
