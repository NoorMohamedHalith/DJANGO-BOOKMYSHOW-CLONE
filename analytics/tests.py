from datetime import timedelta
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.utils import timezone

from movies.models import Movie, Theater, Seat, Booking
from seat_reservations.models import SeatReservation
from payments.models import PaymentTransaction
from analytics.services import AnalyticsService


class AnalyticsTestCase(TestCase):
    def setUp(self):
        self.client = Client()

        self.staff_user = User.objects.create_superuser(username='adminuser', password='password123')
        self.normal_user = User.objects.create_user(username='regularuser', password='password123')

        self.movie1 = Movie.objects.create(
            name='Inception',
            image='movies/inception.jpg',
            rating=4.8,
            cast='Leonardo DiCaprio',
            description='Mind bending thriller'
        )
        self.movie2 = Movie.objects.create(
            name='Interstellar',
            image='movies/interstellar.jpg',
            rating=4.9,
            cast='Matthew McConaughey',
            description='Space exploration'
        )

        self.theater1 = Theater.objects.create(
            name='Screen A',
            movie=self.movie1,
            time=timezone.now() + timedelta(hours=2)
        )
        self.theater2 = Theater.objects.create(
            name='Screen B',
            movie=self.movie2,
            time=timezone.now() + timedelta(hours=4)
        )

        self.seat1 = Seat.objects.create(theater=self.theater1, seat_number='A1', is_booked=True)
        self.seat2 = Seat.objects.create(theater=self.theater1, seat_number='A2', is_booked=False)

        self.booking1 = Booking.objects.create(
            user=self.normal_user,
            seat=self.seat1,
            movie=self.movie1,
            theater=self.theater1
        )

        self.reservation = SeatReservation.objects.create(
            show=self.theater1,
            user=self.normal_user,
            status='CONFIRMED',
            expires_at=timezone.now() + timedelta(minutes=2)
        )

        self.payment = PaymentTransaction.objects.create(
            user=self.normal_user,
            booking=self.booking1,
            reservation=self.reservation,
            amount=200.00,
            payment_gateway='RAZORPAY',
            gateway_transaction_id='tx_test_123',
            status='SUCCESS'
        )

    def test_kpi_summary_calculation(self):
        kpis = AnalyticsService.get_kpi_summary()
        self.assertEqual(kpis['total_revenue'], 200.00)
        self.assertEqual(kpis['total_bookings'], 1)
        self.assertGreaterEqual(kpis['total_users'], 2)
        self.assertEqual(kpis['booked_seats'], 1)

    def test_revenue_timeline(self):
        data = AnalyticsService.get_revenue_timeline(period='7d')
        self.assertIn('labels', data)
        self.assertIn('data', data)
        self.assertEqual(sum(data['data']), 200.00)

    def test_top_performing_movies(self):
        data = AnalyticsService.get_top_performing_movies(limit=5)
        self.assertEqual(data['labels'][0], 'Inception')
        self.assertEqual(data['bookings'][0], 1)

    def test_theater_occupancy_rates(self):
        data = AnalyticsService.get_theater_occupancy_rates()
        self.assertIn('labels', data)
        self.assertIn('occupancy_pct', data)

    def test_csv_report_generation(self):
        sales_csv = AnalyticsService.generate_csv_report(report_type='sales')
        self.assertIn('Transaction ID', sales_csv)
        self.assertIn('tx_test_123', sales_csv)

        bookings_csv = AnalyticsService.generate_csv_report(report_type='bookings')
        self.assertIn('Booking ID', bookings_csv)

        movies_csv = AnalyticsService.generate_csv_report(report_type='movies')
        self.assertIn('Inception', movies_csv)

    def test_dashboard_view_staff_access_security(self):
        # Non-staff user gets 403 Forbidden
        self.client.login(username='regularuser', password='password123')
        res1 = self.client.get('/admin-dashboard/')
        self.assertEqual(res1.status_code, 403)

        # Staff user gets 200 OK
        self.client.login(username='adminuser', password='password123')
        res2 = self.client.get('/admin-dashboard/')
        self.assertEqual(res2.status_code, 200)
        self.assertContains(res2, 'Admin Analytics Dashboard')

    def test_api_endpoints_staff_access_security(self):
        self.client.login(username='regularuser', password='password123')
        res1 = self.client.get('/api/analytics/kpis/')
        self.assertEqual(res1.status_code, 403)

        self.client.login(username='adminuser', password='password123')
        res2 = self.client.get('/api/analytics/kpis/')
        self.assertEqual(res2.status_code, 200)
        self.assertTrue(res2.json()['success'])

    def test_export_csv_view_content_type(self):
        self.client.login(username='adminuser', password='password123')
        response = self.client.get('/api/analytics/export-csv/?type=sales')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv')
        self.assertIn('attachment', response['Content-Disposition'])
