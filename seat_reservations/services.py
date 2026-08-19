from datetime import timedelta
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError, PermissionDenied
from movies.models import Theater, Seat, Booking
from .models import SeatReservation, ReservedSeat


class SeatReservationService:
    @staticmethod
    def expire_expired_reservations():
        """
        Bulk updates active reservations whose expires_at timestamp has passed.
        """
        now = timezone.now()
        SeatReservation.objects.filter(
            status='ACTIVE',
            expires_at__lte=now
        ).update(status='EXPIRED')

    @classmethod
    def get_seat_status(cls, show_id, user=None):
        """
        Returns live seat status (available, booked, reserved, selected) for a screening show.
        """
        cls.expire_expired_reservations()
        show = Theater.objects.get(id=show_id)
        seats = Seat.objects.filter(theater=show).order_by('id')
        now = timezone.now()

        # Fetch active reserved seats for this screening
        active_reserved_seats = {
            rs.seat_id: rs.reservation
            for rs in ReservedSeat.objects.filter(
                reservation__show=show,
                reservation__status='ACTIVE',
                reservation__expires_at__gt=now
            ).select_related('reservation')
        }

        # Fetch booked seats from Booking model
        booked_seat_ids = set(Booking.objects.filter(theater=show).values_list('seat_id', flat=True))

        seat_list = []
        for seat in seats:
            if seat.is_booked or seat.id in booked_seat_ids:
                status = 'booked'
            elif seat.id in active_reserved_seats:
                res = active_reserved_seats[seat.id]
                if user and user.is_authenticated and res.user_id == user.id:
                    status = 'selected'
                else:
                    status = 'reserved'
            else:
                status = 'available'

            seat_list.append({
                'id': seat.id,
                'seat_number': seat.seat_number,
                'status': status
            })

        user_active_reservation = None
        if user and user.is_authenticated:
            user_active_reservation = SeatReservation.objects.filter(
                show=show,
                user=user,
                status='ACTIVE',
                expires_at__gt=now
            ).order_by('-created_at').first()

        res_data = None
        if user_active_reservation:
            res_data = {
                'reservation_uuid': str(user_active_reservation.reservation_uuid),
                'expires_at': user_active_reservation.expires_at.isoformat(),
                'remaining_seconds': user_active_reservation.get_remaining_seconds(),
                'reserved_seat_ids': list(user_active_reservation.reserved_seats.values_list('seat_id', flat=True))
            }

        return {
            'theater_id': show.id,
            'theater_name': show.name,
            'movie_id': show.movie.id,
            'movie_name': show.movie.name,
            'show_time': show.time.isoformat(),
            'seats': seat_list,
            'user_reservation': res_data
        }

    @classmethod
    def create_reservation(cls, user, show_id, seat_ids, ttl_minutes=2):
        """
        Creates a temporary 2-minute seat reservation using transaction.atomic and select_for_update.
        Enforces all-or-nothing atomicity.
        """
        if not user or not user.is_authenticated:
            raise PermissionDenied("Authentication required to reserve seats.")
        
        if not seat_ids:
            raise ValidationError("No seats selected.")

        with transaction.atomic():
            cls.expire_expired_reservations()
            show = Theater.objects.get(id=show_id)

            # Lock seat rows for concurrency protection
            seats = list(Seat.objects.select_for_update().filter(id__in=seat_ids, theater=show))
            if len(seats) != len(seat_ids):
                raise ValidationError("One or more selected seats do not exist for this show.")

            now = timezone.now()
            booked_seat_ids = set(Booking.objects.filter(theater=show).values_list('seat_id', flat=True))

            for seat in seats:
                if seat.is_booked or seat.id in booked_seat_ids:
                    raise ValidationError(f"Seat {seat.seat_number} is already booked.")

                # Check if seat has an active reservation by another user
                active_rs = ReservedSeat.objects.filter(
                    seat=seat,
                    reservation__status='ACTIVE',
                    reservation__expires_at__gt=now
                ).select_related('reservation').first()

                if active_rs:
                    if active_rs.reservation.user_id != user.id:
                        raise ValidationError(f"Seat {seat.seat_number} is currently reserved by another user.")

            # Release any previous active reservation by this user for this show
            previous_reservations = SeatReservation.objects.filter(
                show=show, user=user, status='ACTIVE'
            )
            previous_reservations.update(status='RELEASED')

            expires_at = now + timedelta(minutes=ttl_minutes)
            reservation = SeatReservation.objects.create(
                show=show,
                user=user,
                status='ACTIVE',
                expires_at=expires_at
            )

            ReservedSeat.objects.bulk_create([
                ReservedSeat(reservation=reservation, seat=seat) for seat in seats
            ])

            return reservation

    @classmethod
    def modify_reservation(cls, reservation_uuid, user, new_seat_ids, ttl_minutes=2):
        """
        Modifies an active reservation by replacing reserved seats.
        Uses row locks and atomic transaction.
        """
        if not user or not user.is_authenticated:
            raise PermissionDenied("Authentication required.")

        with transaction.atomic():
            cls.expire_expired_reservations()
            reservation = SeatReservation.objects.select_for_update().get(reservation_uuid=reservation_uuid)

            if reservation.user_id != user.id:
                raise PermissionDenied("You do not own this reservation.")

            if reservation.status != 'ACTIVE' or reservation.is_expired():
                raise ValidationError("This reservation has expired or is no longer active.")

            new_seats = list(Seat.objects.select_for_update().filter(id__in=new_seat_ids, theater=reservation.show))
            if len(new_seats) != len(new_seat_ids):
                raise ValidationError("One or more selected seats do not exist for this show.")

            now = timezone.now()
            existing_seat_ids = set(reservation.reserved_seats.values_list('seat_id', flat=True))
            booked_seat_ids = set(Booking.objects.filter(theater=reservation.show).values_list('seat_id', flat=True))

            for seat in new_seats:
                if seat.id not in existing_seat_ids:
                    if seat.is_booked or seat.id in booked_seat_ids:
                        raise ValidationError(f"Seat {seat.seat_number} is already booked.")

                    active_rs = ReservedSeat.objects.filter(
                        seat=seat,
                        reservation__status='ACTIVE',
                        reservation__expires_at__gt=now
                    ).select_related('reservation').first()

                    if active_rs and active_rs.reservation.user_id != user.id:
                        raise ValidationError(f"Seat {seat.seat_number} is currently reserved by another user.")

            reservation.reserved_seats.all().delete()
            ReservedSeat.objects.bulk_create([
                ReservedSeat(reservation=reservation, seat=seat) for seat in new_seats
            ])

            reservation.expires_at = now + timedelta(minutes=ttl_minutes)
            reservation.save()

            return reservation

    @classmethod
    def release_reservation(cls, reservation_uuid, user):
        """
        Releases an active reservation.
        """
        if not user or not user.is_authenticated:
            raise PermissionDenied("Authentication required.")

        with transaction.atomic():
            reservation = SeatReservation.objects.select_for_update().get(reservation_uuid=reservation_uuid)
            if reservation.user_id != user.id:
                raise PermissionDenied("You do not own this reservation.")

            reservation.status = 'RELEASED'
            reservation.save()
            return reservation
