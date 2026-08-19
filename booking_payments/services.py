import io
import uuid
import qrcode
from io import BytesIO
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from django.core.files.base import ContentFile
from django.core.exceptions import ValidationError, PermissionDenied
from django.core.mail import send_mail
from django.conf import settings

from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

from movies.models import Booking, Seat
from seat_reservations.models import SeatReservation, ReservedSeat
from .models import Payment, Ticket


class TicketService:
    @staticmethod
    def generate_qr_code(ticket):
        """
        Generates a QR code image for a ticket and saves it to ticket.qr_code.
        """
        res = ticket.payment.reservation
        seat_numbers = ", ".join(rs.seat.seat_number for rs in res.reserved_seats.all())
        
        qr_data = (
            f"TICKET: {ticket.ticket_number}\n"
            f"MOVIE: {res.show.movie.name}\n"
            f"THEATER: {res.show.name}\n"
            f"SHOWTIME: {res.show.time.strftime('%Y-%m-%d %H:%M')}\n"
            f"SEATS: {seat_numbers}\n"
            f"USER: {res.user.username}\n"
            f"AMOUNT: Rs.{ticket.payment.amount}"
        )

        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=8,
            border=2,
        )
        qr.add_data(qr_data)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        
        file_name = f"qr_{ticket.ticket_number}.png"
        ticket.qr_code.save(file_name, ContentFile(buffer.getvalue()), save=True)

    @staticmethod
    def generate_pdf(ticket):
        """
        Generates a PDF movie ticket using ReportLab and saves it to ticket.pdf_file.
        """
        res = ticket.payment.reservation
        seat_numbers = ", ".join(rs.seat.seat_number for rs in res.reserved_seats.all())

        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36
        )
        
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'TitleStyle',
            parent=styles['Heading1'],
            fontName='Helvetica-Bold',
            fontSize=22,
            textColor=colors.HexColor('#007bff'),
            alignment=1,
            spaceAfter=15
        )
        normal_style = styles['Normal']
        normal_style.fontSize = 11

        story = []
        story.append(Paragraph("🎬 BOOKMYSHOW - MOVIE TICKET", title_style))
        story.append(Spacer(1, 10))

        # Ticket Info Table
        data = [
            [Paragraph("<b>Ticket Number:</b>", normal_style), Paragraph(ticket.ticket_number, normal_style)],
            [Paragraph("<b>Movie Title:</b>", normal_style), Paragraph(res.show.movie.name, normal_style)],
            [Paragraph("<b>Theater:</b>", normal_style), Paragraph(res.show.name, normal_style)],
            [Paragraph("<b>Showtime:</b>", normal_style), Paragraph(res.show.time.strftime('%b %d, %Y - %I:%M %p'), normal_style)],
            [Paragraph("<b>Seat(s):</b>", normal_style), Paragraph(seat_numbers, normal_style)],
            [Paragraph("<b>Customer Name:</b>", normal_style), Paragraph(res.user.username, normal_style)],
            [Paragraph("<b>Total Paid:</b>", normal_style), Paragraph(f"Rs. {ticket.payment.amount}", normal_style)],
            [Paragraph("<b>Payment Status:</b>", normal_style), Paragraph("SUCCESS (CONFIRMED)", normal_style)],
        ]

        table = Table(data, colWidths=[150, 300])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8f9fa')),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dee2e6')),
            ('PADDING', (0, 0), (-1, -1), 8),
        ]))
        story.append(table)
        story.append(Spacer(1, 20))

        # Attach QR Code Image in PDF if generated
        if ticket.qr_code and hasattr(ticket.qr_code, 'path'):
            try:
                story.append(Image(ticket.qr_code.path, width=150, height=150))
                story.append(Spacer(1, 10))
            except Exception:
                pass

        story.append(Paragraph("<font color='#6c757d'>Please present this ticket or QR code at the cinema entry gate.</font>", normal_style))
        
        doc.build(story)

        file_name = f"ticket_{ticket.ticket_number}.pdf"
        ticket.pdf_file.save(file_name, ContentFile(buffer.getvalue()), save=True)


class PaymentService:
    @staticmethod
    def create_payment_order(reservation, payment_method='MOCK'):
        """
        Creates a pending Payment order for a SeatReservation.
        """
        seat_count = reservation.reserved_seats.count()
        amount = Decimal(seat_count * 200)

        # Check existing payment for this reservation
        payment = Payment.objects.filter(reservation=reservation).first()
        if not payment:
            payment_id = f"PAY-{uuid.uuid4().hex[:12].upper()}"
            order_id = f"ORD-{uuid.uuid4().hex[:10].upper()}"
            payment = Payment.objects.create(
                reservation=reservation,
                amount=amount,
                payment_method=payment_method,
                payment_id=payment_id,
                order_id=order_id,
                status='PENDING'
            )
        else:
            payment.amount = amount
            payment.payment_method = payment_method
            payment.status = 'PENDING'
            payment.save()

        return payment

    @classmethod
    def confirm_payment(cls, payment_id, payment_method='MOCK'):
        """
        Confirms a payment:
        1. Updates payment status to SUCCESS
        2. Updates reservation status to CONFIRMED
        3. Creates confirmed Booking records and sets seat.is_booked = True
        4. Generates Ticket with QR Code & PDF
        5. Sends confirmation email notification
        """
        with transaction.atomic():
            payment = Payment.objects.select_for_update().get(payment_id=payment_id)
            reservation = payment.reservation

            if reservation.status != 'ACTIVE' or reservation.is_expired():
                payment.status = 'FAILED'
                payment.save()
                raise ValidationError("Reservation has expired. Cannot complete payment.")

            payment.status = 'SUCCESS'
            payment.payment_method = payment_method
            payment.save()

            reservation.status = 'CONFIRMED'
            reservation.save()

            # Confirm seats in Booking model and set is_booked = True
            for rs in reservation.reserved_seats.select_related('seat').all():
                seat = rs.seat
                seat.is_booked = True
                seat.save()

                Booking.objects.create(
                    user=reservation.user,
                    seat=seat,
                    movie=reservation.show.movie,
                    theater=reservation.show
                )

            ticket_number = f"TICK-{uuid.uuid4().hex[:10].upper()}"
            ticket = Ticket.objects.create(
                payment=payment,
                ticket_number=ticket_number
            )

            # Generate QR Code & PDF
            TicketService.generate_qr_code(ticket)
            TicketService.generate_pdf(ticket)

            # Trigger Asynchronous Email Confirmation via Celery with non-blocking fallback
            try:
                from .tasks import send_ticket_email_async_task
                send_ticket_email_async_task.delay(ticket.id)
            except Exception:
                # Non-blocking background thread fallback if Celery/Redis broker is offline
                import threading
                def _bg_send():
                    try:
                        from .tasks import send_ticket_email_async_task
                        send_ticket_email_async_task(ticket.id)
                    except Exception:
                        pass
                threading.Thread(target=_bg_send, daemon=True).start()

            return ticket
