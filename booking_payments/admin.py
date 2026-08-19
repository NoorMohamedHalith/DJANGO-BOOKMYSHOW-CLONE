from django.contrib import admin
from .models import Payment, Ticket


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('payment_id', 'reservation', 'amount', 'payment_method', 'status', 'created_at')
    list_filter = ('status', 'payment_method', 'created_at')
    search_fields = ('payment_id', 'order_id', 'reservation__user__username', 'reservation__reservation_uuid')
    readonly_fields = ('payment_id', 'created_at', 'updated_at')


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ('ticket_number', 'payment', 'created_at')
    search_fields = ('ticket_number', 'payment__payment_id', 'payment__reservation__user__username')
    readonly_fields = ('ticket_number', 'created_at')
