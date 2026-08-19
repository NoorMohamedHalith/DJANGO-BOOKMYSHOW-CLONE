import json
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, HttpResponseBadRequest, HttpResponseForbidden
from django.views.decorators.http import require_GET, require_POST
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError, PermissionDenied
from movies.models import Theater, Seat
from .services import SeatReservationService
from .models import SeatReservation


def parse_json_body(request):
    try:
        return json.loads(request.body.decode('utf-8'))
    except Exception:
        return request.POST


@require_GET
def get_seats_api(request, theater_id):
    try:
        data = SeatReservationService.get_seat_status(theater_id, request.user)
        return JsonResponse({'success': True, **data})
    except Theater.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Screening not found.'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@login_required(login_url='/login/')
@require_POST
def create_reservation_api(request):
    try:
        payload = parse_json_body(request)
        show_id = payload.get('show_id') or payload.get('theater_id')
        seat_ids = payload.get('seat_ids', [])

        if isinstance(seat_ids, str):
            seat_ids = [int(s) for s in seat_ids.split(',') if s.strip()]

        reservation = SeatReservationService.create_reservation(request.user, int(show_id), seat_ids)
        return JsonResponse({
            'success': True,
            'reservation_uuid': str(reservation.reservation_uuid),
            'expires_at': reservation.expires_at.isoformat(),
            'remaining_seconds': reservation.get_remaining_seconds(),
            'message': 'Seats reserved for 2 minutes.'
        })
    except ValidationError as e:
        return JsonResponse({'success': False, 'error': e.message if hasattr(e, 'message') else str(e)}, status=400)
    except PermissionDenied as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=403)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@login_required(login_url='/login/')
@require_POST
def modify_reservation_api(request, reservation_uuid):
    try:
        payload = parse_json_body(request)
        seat_ids = payload.get('seat_ids', [])
        if isinstance(seat_ids, str):
            seat_ids = [int(s) for s in seat_ids.split(',') if s.strip()]

        reservation = SeatReservationService.modify_reservation(reservation_uuid, request.user, seat_ids)
        return JsonResponse({
            'success': True,
            'reservation_uuid': str(reservation.reservation_uuid),
            'expires_at': reservation.expires_at.isoformat(),
            'remaining_seconds': reservation.get_remaining_seconds(),
            'message': 'Reservation updated successfully.'
        })
    except ValidationError as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)
    except PermissionDenied as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=403)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@login_required(login_url='/login/')
@require_POST
def release_reservation_api(request, reservation_uuid):
    try:
        SeatReservationService.release_reservation(reservation_uuid, request.user)
        return JsonResponse({'success': True, 'status': 'released', 'message': 'Reservation released.'})
    except PermissionDenied as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=403)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@login_required(login_url='/login/')
def select_seats_view(request, theater_id):
    theater = get_object_or_404(Theater, id=theater_id)
    seats_data = SeatReservationService.get_seat_status(theater_id, request.user)
    context = {
        'theater': theater,
        'seats_json': json.dumps(seats_data['seats']),
        'user_reservation_json': json.dumps(seats_data.get('user_reservation')),
        'seats_data': seats_data,
    }
    return render(request, 'seat_reservations/select_seats.html', context)
