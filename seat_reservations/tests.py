import threading
from datetime import timedelta
from django.test import TransactionTestCase, Client
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.exceptions import ValidationError, PermissionDenied
from movies.models import Movie, Theater, Seat, Booking
from seat_reservations.models import SeatReservation, ReservedSeat
from seat_reservations.services import SeatReservationService


class SeatReservationsTestCase(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.client = Client()

        # Users
        self.user1 = User.objects.create_user(username='user1', password='password123')
        self.user2 = User.objects.create_user(username='user2', password='password123')

        # Movie & Theater (Screening)
        self.movie = Movie.objects.create(
            name='Interstellar',
            image='movies/interstellar.jpg',
            rating=4.9,
            cast='Matthew McConaughey',
            description='Space epic'
        )
        self.theater = Theater.objects.create(
            name='PVR Screen 1',
            movie=self.movie,
            time=timezone.now() + timedelta(hours=3)
        )

        # Seats
        self.seat1 = Seat.objects.create(theater=self.theater, seat_number='A1', is_booked=False)
        self.seat2 = Seat.objects.create(theater=self.theater, seat_number='A2', is_booked=False)
        self.seat3 = Seat.objects.create(theater=self.theater, seat_number='A3', is_booked=False)
        self.seat4 = Seat.objects.create(theater=self.theater, seat_number='A4', is_booked=False)

    # 1. Reserve one seat succeeds
    def test_reserve_one_seat_succeeds(self):
        res = SeatReservationService.create_reservation(self.user1, self.theater.id, [self.seat1.id])
        self.assertEqual(res.status, 'ACTIVE')
        self.assertFalse(res.is_expired())
        self.assertEqual(res.reserved_seats.count(), 1)
        self.assertEqual(res.reserved_seats.first().seat, self.seat1)

    # 2. Reserve multiple seats succeeds
    def test_reserve_multiple_seats_succeeds(self):
        res = SeatReservationService.create_reservation(self.user1, self.theater.id, [self.seat1.id, self.seat2.id])
        self.assertEqual(res.reserved_seats.count(), 2)

    # 3. Booked seat cannot be reserved
    def test_booked_seat_cannot_be_reserved(self):
        Booking.objects.create(
            user=self.user2,
            seat=self.seat1,
            movie=self.movie,
            theater=self.theater
        )
        with self.assertRaises(ValidationError):
            SeatReservationService.create_reservation(self.user1, self.theater.id, [self.seat1.id])

    # 4. Active reserved seat cannot be reserved by another user
    def test_active_reserved_seat_cannot_be_reserved_by_other_user(self):
        SeatReservationService.create_reservation(self.user1, self.theater.id, [self.seat1.id])
        with self.assertRaises(ValidationError):
            SeatReservationService.create_reservation(self.user2, self.theater.id, [self.seat1.id])

    # 5. Expired reservation no longer blocks seat
    def test_expired_reservation_unblocks_seat(self):
        # Create an expired reservation for user1
        res = SeatReservation.objects.create(
            show=self.theater,
            user=self.user1,
            status='ACTIVE',
            expires_at=timezone.now() - timedelta(minutes=1)
        )
        ReservedSeat.objects.create(reservation=res, seat=self.seat1)

        # user2 should now be able to reserve seat1
        res2 = SeatReservationService.create_reservation(self.user2, self.theater.id, [self.seat1.id])
        self.assertEqual(res2.status, 'ACTIVE')

    # 6. Modify own reservation works
    def test_modify_own_reservation_works(self):
        res = SeatReservationService.create_reservation(self.user1, self.theater.id, [self.seat1.id])
        updated_res = SeatReservationService.modify_reservation(res.reservation_uuid, self.user1, [self.seat2.id])
        
        reserved_seat_ids = list(updated_res.reserved_seats.values_list('seat_id', flat=True))
        self.assertIn(self.seat2.id, reserved_seat_ids)
        self.assertNotIn(self.seat1.id, reserved_seat_ids)

    # 7. Cannot modify another user's reservation
    def test_cannot_modify_another_user_reservation(self):
        res = SeatReservationService.create_reservation(self.user1, self.theater.id, [self.seat1.id])
        with self.assertRaises(PermissionDenied):
            SeatReservationService.modify_reservation(res.reservation_uuid, self.user2, [self.seat2.id])

    # 8. Release works
    def test_release_reservation_works(self):
        res = SeatReservationService.create_reservation(self.user1, self.theater.id, [self.seat1.id])
        released_res = SeatReservationService.release_reservation(res.reservation_uuid, self.user1)
        self.assertEqual(released_res.status, 'RELEASED')

        # seat1 can now be reserved by user2
        res2 = SeatReservationService.create_reservation(self.user2, self.theater.id, [self.seat1.id])
        self.assertEqual(res2.status, 'ACTIVE')

    # 9. All-or-nothing: one unavailable seat rejects the whole batch
    def test_all_or_nothing_batch_reservation_failure(self):
        # Book seat1
        Booking.objects.create(user=self.user2, seat=self.seat1, movie=self.movie, theater=self.theater)

        # Attempt to reserve seat1 (booked), seat2 (available), seat3 (available)
        with self.assertRaises(ValidationError):
            SeatReservationService.create_reservation(self.user1, self.theater.id, [self.seat1.id, self.seat2.id, self.seat3.id])

        # Verify seat2 and seat3 remain unreserved
        status_data = SeatReservationService.get_seat_status(self.theater.id)
        seat2_status = next(s['status'] for s in status_data['seats'] if s['id'] == self.seat2.id)
        self.assertEqual(seat2_status, 'available')

    # 10. Concurrency test: Two simultaneous requests for the same seat
    def test_concurrency_simultaneous_reservation(self):
        results = []

        def attempt_reservation(user):
            try:
                res = SeatReservationService.create_reservation(user, self.theater.id, [self.seat4.id])
                results.append(('success', res))
            except Exception as e:
                results.append(('failure', str(e)))

        thread1 = threading.Thread(target=attempt_reservation, args=(self.user1,))
        thread2 = threading.Thread(target=attempt_reservation, args=(self.user2,))

        thread1.start()
        thread2.start()
        thread1.join()
        thread2.join()

        successes = [r for r in results if r[0] == 'success']
        failures = [r for r in results if r[0] == 'failure']

        self.assertEqual(len(successes), 1)
        self.assertEqual(len(failures), 1)
