import uuid
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from movies.models import Theater, Seat


class SeatReservation(models.Model):
    STATUS_CHOICES = (
        ('ACTIVE', 'Active'),
        ('EXPIRED', 'Expired'),
        ('RELEASED', 'Released'),
        ('CONFIRMED', 'Confirmed'),
        ('CANCELLED', 'Cancelled'),
    )

    show = models.ForeignKey(Theater, on_delete=models.CASCADE, related_name='reservations')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='seat_reservations')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='ACTIVE')
    expires_at = models.DateTimeField()
    reservation_uuid = models.UUIDField(default=uuid.uuid4, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def is_expired(self):
        return timezone.now() > self.expires_at

    def get_remaining_seconds(self):
        if self.is_expired() or self.status != 'ACTIVE':
            return 0
        delta = self.expires_at - timezone.now()
        return max(0, int(delta.total_seconds()))

    def __str__(self):
        return f"{self.user.username} - {self.show.name} - {self.status}"


class ReservedSeat(models.Model):
    reservation = models.ForeignKey(SeatReservation, on_delete=models.CASCADE, related_name='reserved_seats')
    seat = models.ForeignKey(Seat, on_delete=models.CASCADE, related_name='reserved_seat_instances')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('reservation', 'seat')

    def __str__(self):
        return f"Seat {self.seat.seat_number} for {self.reservation.user.username}"


from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=Theater)
def auto_create_seats_for_new_theater(sender, instance, created, **kwargs):
    if created:
        rows = ['A', 'B', 'C', 'D', 'E']
        seats_per_row = 10
        seats_to_create = []
        for r in rows:
            for num in range(1, seats_per_row + 1):
                seat_num = f"{r}{num}"
                seats_to_create.append(Seat(
                    theater=instance,
                    seat_number=seat_num,
                    is_booked=False
                ))
        Seat.objects.bulk_create(seats_to_create)
