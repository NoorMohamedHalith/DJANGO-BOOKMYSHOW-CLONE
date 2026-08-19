from datetime import timedelta
from django.test import TransactionTestCase, Client
from django.contrib.auth.models import User
from django.utils import timezone
from movies.models import Movie, Theater, Seat, Booking
from seat_reservations.models import SeatReservation, ReservedSeat
from seat_reservations.services import SeatReservationService
from booking_payments.models import Payment, Ticket
from booking_payments.services import PaymentService, TicketService


class BookingPaymentsTestCase(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.client = Client()

        self.user = User.objects.create_user(username='testuser', email='user@example.com', password='password123')
        self.other_user = User.objects.create_user(username='otheruser', password='password123')

        self.movie = Movie.objects.create(
            name='Oppenheimer',
            image='movies/oppenheimer.jpg',
            rating=4.9,
            cast='Cillian Murphy',
            description='Biographical thriller'
        )

        self.theater = Theater.objects.create(
            name='IMAX Screen 1',
            movie=self.movie,
            time=timezone.now() + timedelta(hours=4)
        )

        self.seat1 = Seat.objects.create(theater=self.theater, seat_number='B1', is_booked=False)
        self.seat2 = Seat.objects.create(theater=self.theater, seat_number='B2', is_booked=False)

        self.reservation = SeatReservationService.create_reservation(self.user, self.theater.id, [self.seat1.id, self.seat2.id])

    def test_create_payment_order(self):
        payment = PaymentService.create_payment_order(self.reservation, payment_method='MOCK')
        self.assertEqual(payment.status, 'PENDING')
        self.assertEqual(payment.amount, 400.00)
        self.assertTrue(payment.payment_id.startswith('PAY-'))

    def test_confirm_payment_creates_booking_and_sets_is_booked(self):
        payment = PaymentService.create_payment_order(self.reservation, payment_method='MOCK')
        ticket = PaymentService.confirm_payment(payment.payment_id, payment_method='MOCK')

        payment.refresh_from_db()
        self.reservation.refresh_from_db()
        self.seat1.refresh_from_db()
        self.seat2.refresh_from_db()

        self.assertEqual(payment.status, 'SUCCESS')
        self.assertEqual(self.reservation.status, 'CONFIRMED')
        self.assertTrue(self.seat1.is_booked)
        self.assertTrue(self.seat2.is_booked)

        # Verify Booking records created in existing Booking model
        bookings = Booking.objects.filter(user=self.user, theater=self.theater)
        self.assertEqual(bookings.count(), 2)

        # Verify Ticket object created
        self.assertEqual(ticket.payment, payment)
        self.assertTrue(ticket.ticket_number.startswith('TICK-'))
        self.assertTrue(bool(ticket.qr_code))
        self.assertTrue(bool(ticket.pdf_file))

    def test_checkout_view(self):
        self.client.login(username='testuser', password='password123')
        response = self.client.get(f'/checkout/{self.reservation.reservation_uuid}/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Oppenheimer')
        self.assertContains(response, 'B1, B2')

    def test_process_mock_payment_view(self):
        self.client.login(username='testuser', password='password123')
        response = self.client.post(f'/checkout/{self.reservation.reservation_uuid}/pay-mock/')
        self.assertEqual(response.status_code, 302)
        
        ticket = Ticket.objects.get(payment__reservation=self.reservation)
        self.assertIn(ticket.ticket_number, response.url)

    def test_download_ticket_pdf_view(self):
        payment = PaymentService.create_payment_order(self.reservation, payment_method='MOCK')
        ticket = PaymentService.confirm_payment(payment.payment_id, payment_method='MOCK')

        self.client.login(username='testuser', password='password123')
        response = self.client.get(f'/ticket/{ticket.ticket_number}/download-pdf/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertTrue('attachment' in response['Content-Disposition'])

    def test_send_ticket_email_async_task(self):
        from booking_payments.tasks import send_ticket_email_async_task
        payment = PaymentService.create_payment_order(self.reservation, payment_method='MOCK')
        ticket = PaymentService.confirm_payment(payment.payment_id, payment_method='MOCK')

        res = send_ticket_email_async_task(ticket.id)
        self.assertIn("Email sent successfully", res)

