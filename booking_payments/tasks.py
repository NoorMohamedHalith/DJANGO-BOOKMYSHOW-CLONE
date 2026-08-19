import logging
from celery import shared_task
from django.core.mail import EmailMessage
from django.conf import settings
from .models import Ticket
from .services import TicketService

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=10)
def send_ticket_email_async_task(self, ticket_id):
    """
    Asynchronous Celery task that generates/verifies the PDF ticket & QR code,
    constructs an EmailMessage with the PDF attached, and sends it to the user.
    Retries up to 3 times automatically on failure.
    """
    try:
        ticket = Ticket.objects.select_related(
            'payment',
            'payment__reservation',
            'payment__reservation__user',
            'payment__reservation__show',
            'payment__reservation__show__movie'
        ).get(id=ticket_id)

        # Ensure QR code & PDF are generated
        if not ticket.qr_code:
            TicketService.generate_qr_code(ticket)
        if not ticket.pdf_file:
            TicketService.generate_pdf(ticket)

        res = ticket.payment.reservation
        seat_numbers = ", ".join(rs.seat.seat_number for rs in res.reserved_seats.all())
        user_email = res.user.email or 'user@example.com'

        subject = f"Booking Confirmed - Ticket #{ticket.ticket_number}"
        body = (
            f"Hello {res.user.username},\n\n"
            f"Your booking for '{res.show.movie.name}' is CONFIRMED!\n\n"
            f"=== BOOKING & TICKET DETAILS ===\n"
            f"Ticket Number: {ticket.ticket_number}\n"
            f"Payment Reference: {ticket.payment.payment_id}\n"
            f"Movie: {res.show.movie.name}\n"
            f"Theater: {res.show.name}\n"
            f"Showtime: {res.show.time.strftime('%Y-%m-%d %H:%M')}\n"
            f"Seat(s): {seat_numbers}\n"
            f"Total Paid: Rs. {ticket.payment.amount}\n\n"
            f"Please find your official PDF ticket attached with QR code for entry.\n"
            f"Thank you for booking with BookMyShow!"
        )

        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'webmaster@localhost')
        email = EmailMessage(
            subject=subject,
            body=body,
            from_email=from_email,
            to=[user_email]
        )

        # Attach PDF file
        if ticket.pdf_file:
            ticket.pdf_file.open('rb')
            email.attach(
                filename=f"Ticket_{ticket.ticket_number}.pdf",
                content=ticket.pdf_file.read(),
                mimetype='application/pdf'
            )
            ticket.pdf_file.close()

        email.send(fail_silently=False)
        logger.info(f"Successfully sent async ticket email to {user_email} for Ticket #{ticket.ticket_number}")
        return f"Email sent successfully for Ticket #{ticket.ticket_number}"

    except Exception as exc:
        logger.error(f"Failed to send ticket email for ticket_id={ticket_id}: {str(exc)}. Retrying ({self.request.retries + 1}/{self.max_retries})...")
        raise self.retry(exc=exc)
