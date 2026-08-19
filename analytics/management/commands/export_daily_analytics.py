from django.core.management.base import BaseCommand
from analytics.services import AnalyticsService


class Command(BaseCommand):
    help = 'Exports daily analytics KPI summary to stdout or CSV'

    def add_arguments(self, parser):
        parser.add_argument(
            '--format',
            type=str,
            default='text',
            help='Output format: text or csv'
        )

    def handle(self, *args, **options):
        fmt = options.get('format', 'text').lower()

        if fmt == 'csv':
            csv_data = AnalyticsService.generate_csv_report('sales')
            self.stdout.write(csv_data)
        else:
            kpis = AnalyticsService.get_kpi_summary()
            self.stdout.write(self.style.SUCCESS("=== BOOKMYSHOW DAILY ANALYTICS KPI SUMMARY ==="))
            self.stdout.write(f"Total Revenue:         Rs. {kpis['total_revenue']:.2f}")
            self.stdout.write(f"Total Bookings:        {kpis['total_bookings']}")
            self.stdout.write(f"Total Active Users:    {kpis['total_users']}")
            self.stdout.write(f"Booked / Total Seats:  {kpis['booked_seats']} / {kpis['total_seats']}")
            self.stdout.write(f"Avg Occupancy Rate:    {kpis['avg_occupancy_rate']}%")
            self.stdout.write(self.style.SUCCESS("==============================================="))
