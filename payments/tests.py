import json
import hmac
import hashlib
from datetime import timedelta
from django.test import TransactionTestCase, Client
from django.contrib.auth.models import User, AnonymousUser
from django.utils import timezone
from django.core.exceptions import ValidationError, PermissionDenied
from django.conf import settings

from movies.models import Movie, Theater, Seat, Booking
from seat_reservations.models import SeatReservation, ReservedSeat
from seat_reservations.services import SeatReservationService
from payments.models import PaymentTransaction, PaymentLog
from payments.services import PaymentService


class PaymentsTestCase(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.client = Client()

        self.user = User.objects.create_user(username='payuser', password='password123')
        self.other_user = User.objects.create_user(username='otheruser', password='password123')

        self.movie = Movie.objects.create(
            name='Dune: Part Two',
            image='movies/dune.jpg',
            rating=4.9,
            cast='Timothée Chalamet',
            description='Sci-fi epic'
        )

        self.theater = Theater.objects.create(
            name='PVR IMAX Screen 2',
            movie=self.movie,
            time=timezone.now() + timedelta(hours=5)
        )

        self.seat1 = Seat.objects.create(theater=self.theater, seat_number='C1', is_booked=False)
        self.seat2 = Seat.objects.create(theater=self.theater, seat_number='C2', is_booked=False)

        self.reservation = SeatReservationService.create_reservation(self.user, self.theater.id, [self.seat1.id, self.seat2.id])

    # 1. Creating a payment order from a valid reservation
    def test_create_payment_order(self):
        tx, order_data = PaymentService.create_payment_order(self.user, self.reservation.reservation_uuid, amount=400, gateway='RAZORPAY')
        self.assertEqual(tx.status, 'INITIATED')
        self.assertEqual(tx.amount, 400.00)
        self.assertEqual(tx.user, self.user)
        self.assertTrue(PaymentLog.objects.filter(transaction=tx, event='order_created').exists())

    # 2. Payment success -> booking created, reservation confirmed, seat.is_booked = True
    def test_payment_success_creates_booking_and_confirms_reservation(self):
        tx, order_data = PaymentService.create_payment_order(self.user, self.reservation.reservation_uuid, amount=400)
        booking = PaymentService.handle_payment_success(tx, gateway_transaction_id=order_data['order_id'], payment_data={'status': 'captured'})

        tx.refresh_from_db()
        self.reservation.refresh_from_db()
        self.seat1.refresh_from_db()
        self.seat2.refresh_from_db()

        self.assertEqual(tx.status, 'SUCCESS')
        self.assertEqual(self.reservation.status, 'CONFIRMED')
        self.assertTrue(self.seat1.is_booked)
        self.assertTrue(self.seat2.is_booked)

        # Confirmed Booking records created in existing movies.Booking model
        bookings = Booking.objects.filter(user=self.user, theater=self.theater)
        self.assertEqual(bookings.count(), 2)
        self.assertIsNotNone(tx.booking)

    # 3. Payment failure -> reservation released, seats freed
    def test_payment_failure_releases_reservation(self):
        tx, order_data = PaymentService.create_payment_order(self.user, self.reservation.reservation_uuid, amount=400)
        PaymentService.handle_payment_failure(tx, gateway_transaction_id=order_data['order_id'], payment_data={'error': 'Payment declined'})

        tx.refresh_from_db()
        self.reservation.refresh_from_db()
        self.seat1.refresh_from_db()

        self.assertEqual(tx.status, 'FAILED')
        self.assertEqual(self.reservation.status, 'RELEASED')
        self.assertFalse(self.seat1.is_booked)

    # 4. Webhook signature validation – accept valid, reject invalid
    def test_webhook_signature_validation(self):
        secret = "test_webhook_secret_123"
        payload_bytes = b'{"event": "payment.captured", "payload": {}}'

        # Valid signature
        valid_sig = hmac.new(secret.encode('utf-8'), payload_bytes, hashlib.sha256).hexdigest()
        self.assertTrue(PaymentService.verify_razorpay_signature(payload_bytes, valid_sig, secret))

        # Invalid signature
        invalid_sig = "invalid_signature_string"
        self.assertFalse(PaymentService.verify_razorpay_signature(payload_bytes, invalid_sig, secret))

    # 5. Webhook idempotency – duplicate webhook does not create duplicate booking
    def test_webhook_idempotency(self):
        tx, order_data = PaymentService.create_payment_order(self.user, self.reservation.reservation_uuid, amount=400)
        
        secret = getattr(settings, 'RAZORPAY_WEBHOOK_SECRET', 'mockwebhooksecret123456')
        webhook_payload = {
            'event': 'payment.captured',
            'payload': {
                'payment': {
                    'entity': {
                        'id': 'pay_test_123',
                        'order_id': order_data['order_id'],
                        'amount': 40000,
                        'status': 'captured'
                    }
                }
            }
        }
        body_bytes = json.dumps(webhook_payload).encode('utf-8')
        sig = hmac.new(secret.encode('utf-8'), body_bytes, hashlib.sha256).hexdigest()

        # First webhook call
        res1 = PaymentService.handle_webhook(body_bytes, sig, gateway='RAZORPAY')
        self.assertTrue(res1['success'])
        booking_count_1 = Booking.objects.filter(user=self.user).count()

        # Duplicate webhook call
        res2 = PaymentService.handle_webhook(body_bytes, sig, gateway='RAZORPAY')
        self.assertTrue(res2['success'])
        self.assertTrue(res2.get('idempotent'))
        booking_count_2 = Booking.objects.filter(user=self.user).count()

        # Verify no duplicate bookings created
        self.assertEqual(booking_count_1, booking_count_2)

    # 6. User payment history returns correct transactions
    def test_user_payment_history(self):
        tx, _ = PaymentService.create_payment_order(self.user, self.reservation.reservation_uuid, amount=400)
        history = PaymentService.get_user_payment_history(self.user)
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0], tx)

    # 7. Unauthenticated users cannot create payment orders
    def test_unauthenticated_user_cannot_create_order(self):
        with self.assertRaises(PermissionDenied):
            PaymentService.create_payment_order(AnonymousUser(), self.reservation.reservation_uuid)

    # 8. Expired reservation cannot be used for payment
    def test_expired_reservation_cannot_be_used_for_payment(self):
        self.reservation.expires_at = timezone.now() - timedelta(minutes=1)
        self.reservation.save()

        with self.assertRaises(ValidationError):
            PaymentService.create_payment_order(self.user, self.reservation.reservation_uuid)
