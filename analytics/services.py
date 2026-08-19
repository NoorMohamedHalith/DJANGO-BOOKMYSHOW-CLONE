import csv
import io
from decimal import Decimal
from datetime import timedelta
from django.utils import timezone
from django.db.models import Sum, Count, Avg, F
from django.db.models.functions import TruncDay
from django.contrib.auth.models import User

from movies.models import Movie, Theater, Seat, Booking
from payments.models import PaymentTransaction


class AnalyticsService:
    @classmethod
    def get_kpi_summary(cls):
        """
        Calculates key high-level performance indicators.
        """
        total_revenue_res = PaymentTransaction.objects.filter(status='SUCCESS').aggregate(total=Sum('amount'))
        total_revenue = float(total_revenue_res['total'] or 0.00)

        total_bookings = Booking.objects.count()
        total_users = User.objects.filter(is_active=True).count()

        total_seats = Seat.objects.count()
        booked_seats = Seat.objects.filter(is_booked=True).count()
        avg_occupancy_rate = round((booked_seats / total_seats * 100), 2) if total_seats > 0 else 0.0

        return {
            'total_revenue': total_revenue,
            'total_bookings': total_bookings,
            'total_users': total_users,
            'total_seats': total_seats,
            'booked_seats': booked_seats,
            'avg_occupancy_rate': avg_occupancy_rate,
        }

    @classmethod
    def get_revenue_timeline(cls, period='7d'):
        """
        Groups successful payment revenue by day.
        """
        now = timezone.now()
        qs = PaymentTransaction.objects.filter(status='SUCCESS')

        if period == '7d':
            qs = qs.filter(created_at__gte=now - timedelta(days=7))
        elif period == '30d':
            qs = qs.filter(created_at__gte=now - timedelta(days=30))

        daily_revenue = (
            qs.annotate(day=TruncDay('created_at'))
            .values('day')
            .annotate(total=Sum('amount'))
            .order_by('day')
        )

        labels = [entry['day'].strftime('%Y-%m-%d') if entry['day'] else 'N/A' for entry in daily_revenue]
        data = [float(entry['total']) for entry in daily_revenue]

        return {
            'labels': labels,
            'data': data
        }

    @classmethod
    def get_top_performing_movies(cls, limit=5):
        """
        Returns top performing movies by total booking count & revenue.
        """
        top_movies = (
            Movie.objects.annotate(
                total_bookings=Count('booking'),
                total_revenue=Sum('booking__payment_transactions__amount')
            )
            .order_by('-total_bookings')[:limit]
        )

        labels = [m.name for m in top_movies]
        bookings = [m.total_bookings for m in top_movies]
        revenue = [float(m.total_revenue or 0.00) for m in top_movies]

        return {
            'labels': labels,
            'bookings': bookings,
            'revenue': revenue
        }

    @classmethod
    def get_theater_occupancy_rates(cls):
        """
        Calculates occupancy percentage per theater room.
        """
        theaters = Theater.objects.all()
        labels = []
        occupancy_pct = []
        booked_list = []
        total_list = []

        for theater in theaters:
            total_s = Seat.objects.filter(theater=theater).count()
            booked_s = Seat.objects.filter(theater=theater, is_booked=True).count()
            pct = round((booked_s / total_s * 100), 2) if total_s > 0 else 0.0

            labels.append(f"{theater.name} ({theater.movie.name})")
            occupancy_pct.append(pct)
            booked_list.append(booked_s)
            total_list.append(total_s)

        return {
            'labels': labels,
            'occupancy_pct': occupancy_pct,
            'booked': booked_list,
            'total': total_list
        }

    @classmethod
    def get_user_growth_timeline(cls):
        """
        Groups user registrations by day.
        """
        user_growth = (
            User.objects.annotate(day=TruncDay('date_joined'))
            .values('day')
            .annotate(count=Count('id'))
            .order_by('day')
        )

        labels = [entry['day'].strftime('%Y-%m-%d') if entry['day'] else 'N/A' for entry in user_growth]
        data = [entry['count'] for entry in user_growth]

        return {
            'labels': labels,
            'data': data
        }

    @classmethod
    def generate_csv_report(cls, report_type='sales'):
        """
        Generates CSV report buffer string for sales, bookings, or movies.
        """
        output = io.StringIO()
        writer = csv.writer(output)

        if report_type == 'sales':
            writer.writerow(['Transaction ID', 'User', 'Movie', 'Theater', 'Gateway', 'Amount (INR)', 'Status', 'Date'])
            transactions = PaymentTransaction.objects.select_related('user', 'booking', 'booking__movie', 'booking__theater').order_by('-created_at')
            for tx in transactions:
                movie_name = tx.booking.movie.name if tx.booking else 'N/A'
                theater_name = tx.booking.theater.name if tx.booking else 'N/A'
                writer.writerow([
                    tx.gateway_transaction_id,
                    tx.user.username,
                    movie_name,
                    theater_name,
                    tx.payment_gateway,
                    float(tx.amount),
                    tx.status,
                    tx.created_at.strftime('%Y-%m-%d %H:%M:%S')
                ])

        elif report_type == 'bookings':
            writer.writerow(['Booking ID', 'User', 'Movie', 'Theater', 'Seat Number', 'Booked At'])
            bookings = Booking.objects.select_related('user', 'movie', 'theater', 'seat').order_by('-booked_at')
            for b in bookings:
                writer.writerow([
                    b.id,
                    b.user.username,
                    b.movie.name,
                    b.theater.name,
                    b.seat.seat_number,
                    b.booked_at.strftime('%Y-%m-%d %H:%M:%S')
                ])

        elif report_type == 'movies':
            writer.writerow(['Movie ID', 'Movie Title', 'Total Bookings', 'Rating', 'Cast'])
            movies = Movie.objects.annotate(total_bookings=Count('booking')).order_by('-total_bookings')
            for m in movies:
                writer.writerow([
                    m.id,
                    m.name,
                    m.total_bookings,
                    float(m.rating),
                    m.cast
                ])

        return output.getvalue()
