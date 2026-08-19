from django.contrib import admin
from .models import SeatReservation, ReservedSeat


class ReservedSeatInline(admin.TabularInline):
    model = ReservedSeat
    extra = 0
    readonly_fields = ('seat', 'created_at')


@admin.register(SeatReservation)
class SeatReservationAdmin(admin.ModelAdmin):
    list_display = ('reservation_uuid', 'user', 'show', 'status', 'expires_at', 'created_at')
    list_filter = ('status', 'show', 'created_at')
    search_fields = ('reservation_uuid', 'user__username', 'show__name', 'show__movie__name')
    readonly_fields = ('reservation_uuid', 'created_at', 'updated_at')
    inlines = [ReservedSeatInline]


@admin.register(ReservedSeat)
class ReservedSeatAdmin(admin.ModelAdmin):
    list_display = ('id', 'reservation', 'seat', 'created_at')
    search_fields = ('reservation__reservation_uuid', 'reservation__user__username', 'seat__seat_number')
