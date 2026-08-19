from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import HttpResponse, HttpResponseForbidden, Http404
from django.contrib import messages
from django.core.exceptions import ValidationError
from seat_reservations.models import SeatReservation
from .models import Payment, Ticket
from .services import PaymentService


@login_required(login_url='/login/')
def checkout_view(request, reservation_uuid):
    reservation = get_object_or_404(SeatReservation, reservation_uuid=reservation_uuid)

    if reservation.user != request.user:
        return HttpResponseForbidden("You are not authorized to view this checkout.")

    if reservation.status != 'ACTIVE' or reservation.is_expired():
        messages.error(request, "Your seat reservation has expired. Please select seats again.")
        return redirect('select_seats_view', theater_id=reservation.show.id)

    payment = PaymentService.create_payment_order(reservation)
    reserved_seats = reservation.reserved_seats.select_related('seat').all()
    seat_numbers = ", ".join(rs.seat.seat_number for rs in reserved_seats)

    context = {
        'reservation': reservation,
        'payment': payment,
        'reserved_seats': reserved_seats,
        'seat_numbers': seat_numbers,
        'remaining_seconds': reservation.get_remaining_seconds(),
    }
    return render(request, 'booking_payments/checkout.html', context)


@login_required(login_url='/login/')
@require_POST
def process_mock_payment_view(request, reservation_uuid):
    reservation = get_object_or_404(SeatReservation, reservation_uuid=reservation_uuid)

    if reservation.user != request.user:
        return HttpResponseForbidden("You are not authorized to perform payment for this reservation.")

    try:
        payment = PaymentService.create_payment_order(reservation, payment_method='MOCK')
        ticket = PaymentService.confirm_payment(payment.payment_id, payment_method='MOCK')
        messages.success(request, f"Payment successful! Ticket #{ticket.ticket_number} has been issued.")
        return redirect('ticket_detail_view', ticket_number=ticket.ticket_number)
    except ValidationError as e:
        messages.error(request, str(e))
        return redirect('select_seats_view', theater_id=reservation.show.id)
    except Exception as e:
        messages.error(request, f"Payment processing error: {str(e)}")
        return redirect('checkout_view', reservation_uuid=reservation.reservation_uuid)


@login_required(login_url='/login/')
def ticket_detail_view(request, ticket_number):
    ticket = get_object_or_404(Ticket, ticket_number=ticket_number)

    if ticket.payment.reservation.user != request.user:
        return HttpResponseForbidden("You are not authorized to view this ticket.")

    reserved_seats = ticket.payment.reservation.reserved_seats.select_related('seat').all()
    seat_numbers = ", ".join(rs.seat.seat_number for rs in reserved_seats)

    context = {
        'ticket': ticket,
        'seat_numbers': seat_numbers,
    }
    return render(request, 'booking_payments/ticket_detail.html', context)


@login_required(login_url='/login/')
def download_ticket_pdf_view(request, ticket_number):
    ticket = get_object_or_404(Ticket, ticket_number=ticket_number)

    if ticket.payment.reservation.user != request.user:
        return HttpResponseForbidden("You are not authorized to download this ticket.")

    if not ticket.pdf_file:
        from .services import TicketService
        TicketService.generate_pdf(ticket)

    pdf_file = ticket.pdf_file.open('rb')
    response = HttpResponse(pdf_file.read(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="Ticket_{ticket.ticket_number}.pdf"'
    pdf_file.close()
    return response
