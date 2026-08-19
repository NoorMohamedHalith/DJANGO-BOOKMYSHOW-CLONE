from django.core.management.base import BaseCommand
from seat_reservations.services import SeatReservationService


class Command(BaseCommand):
    help = 'Marks expired active seat reservations as EXPIRED.'

    def handle(self, *args, **options):
        SeatReservationService.expire_expired_reservations()
        self.stdout.write(self.style.SUCCESS('Successfully checked and expired stale seat reservations.'))
