import json
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponseBadRequest, HttpResponseForbidden, HttpResponse
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError, PermissionDenied
from django.contrib import messages

from seat_reservations.models import SeatReservation
from .models import PaymentTransaction, PaymentLog
from .services import PaymentService


def parse_json_payload(request):
    try:
        return json.loads(request.body.decode('utf-8'))
    except Exception:
        return request.POST


@login_required(login_url='/login/')
@require_POST
def create_order_api(request):
    try:
        payload = parse_json_payload(request)
        reservation_uuid = payload.get('reservation_uuid')
        gateway = payload.get('gateway', 'RAZORPAY')
        amount = payload.get('amount')

        tx, order_data = PaymentService.create_payment_order(
            user=request.user,
            reservation_uuid=reservation_uuid,
            amount=amount,
            gateway=gateway
        )
        return JsonResponse({'success': True, **order_data})
    except ValidationError as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)
    except PermissionDenied as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=403)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@login_required(login_url='/login/')
def checkout_view(request, reservation_uuid):
    reservation = get_object_or_404(SeatReservation, reservation_uuid=reservation_uuid)

    if reservation.user != request.user:
        return HttpResponseForbidden("You are not authorized to view this checkout.")

    if reservation.status != 'ACTIVE' or reservation.is_expired():
        messages.error(request, "Your seat reservation has expired. Please select seats again.")
        return redirect('select_seats_view', theater_id=reservation.show.id)

    tx, order_data = PaymentService.create_payment_order(
        user=request.user,
        reservation_uuid=reservation_uuid,
        gateway='RAZORPAY'
    )

    reserved_seats = reservation.reserved_seats.select_related('seat').all()
    seat_numbers = ", ".join(rs.seat.seat_number for rs in reserved_seats)

    context = {
        'reservation': reservation,
        'transaction': tx,
        'order_data': order_data,
        'order_data_json': json.dumps(order_data),
        'reserved_seats': reserved_seats,
        'seat_numbers': seat_numbers,
        'remaining_seconds': reservation.get_remaining_seconds(),
    }
    return render(request, 'payments/checkout.html', context)


@login_required(login_url='/login/')
def payment_success_callback_view(request):
    payload = parse_json_payload(request)
    order_id = payload.get('razorpay_order_id') or payload.get('order_id') or request.GET.get('order_id')
    payment_id = payload.get('razorpay_payment_id') or payload.get('payment_id') or request.GET.get('payment_id') or f"pay_mock_{order_id}"

    if not order_id:
        # Fallback if URL params passed
        order_id = request.GET.get('razorpay_order_id')

    tx = PaymentTransaction.objects.filter(gateway_transaction_id=order_id, user=request.user).first()
    if not tx:
        # If order_id not matched directly, find latest initiated transaction for user
        tx = PaymentTransaction.objects.filter(user=request.user, status='INITIATED').order_by('-created_at').first()

    if not tx:
        messages.error(request, "No pending payment order found.")
        return redirect('home')

    booking = PaymentService.handle_payment_success(tx, gateway_transaction_id=payment_id, payment_data=dict(payload))
    messages.success(request, f"Payment successful! Booking confirmed for {booking.movie.name}.")
    
    context = {
        'transaction': tx,
        'booking': booking,
        'reservation': tx.reservation,
    }
    return render(request, 'payments/success.html', context)


@login_required(login_url='/login/')
def payment_failure_callback_view(request):
    order_id = request.GET.get('order_id') or request.POST.get('order_id')
    tx = None
    if order_id:
        tx = PaymentTransaction.objects.filter(gateway_transaction_id=order_id, user=request.user).first()
    
    if not tx:
        tx = PaymentTransaction.objects.filter(user=request.user, status='INITIATED').order_by('-created_at').first()

    if tx:
        PaymentService.handle_payment_failure(tx, payment_data={'reason': 'User cancelled or payment failed'})

    context = {
        'transaction': tx,
    }
    return render(request, 'payments/failure.html', context)


@csrf_exempt
@require_POST
def webhook_view(request):
    signature = request.headers.get('X-Razorpay-Signature') or request.headers.get('Stripe-Signature', '')
    gateway = 'STRIPE' if 'Stripe-Signature' in request.headers else 'RAZORPAY'

    result = PaymentService.handle_webhook(
        request_body=request.body,
        signature=signature,
        gateway=gateway
    )
    if result.get('success'):
        return JsonResponse(result, status=200)
    else:
        return JsonResponse(result, status=400)


@login_required(login_url='/login/')
def user_payment_history_view(request):
    transactions = PaymentService.get_user_payment_history(request.user)
    context = {
        'transactions': transactions
    }
    return render(request, 'payments/history.html', context)
