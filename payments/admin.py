from django.contrib import admin
from .models import PaymentTransaction, PaymentLog


class PaymentLogInline(admin.TabularInline):
    model = PaymentLog
    extra = 0
    readonly_fields = ('event', 'message', 'data', 'created_at')


@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
    list_display = ('gateway_transaction_id', 'user', 'amount', 'payment_gateway', 'status', 'webhook_signature_valid', 'created_at')
    list_filter = ('status', 'payment_gateway', 'webhook_signature_valid', 'created_at')
    search_fields = ('gateway_transaction_id', 'user__username', 'reservation__reservation_uuid')
    readonly_fields = ('gateway_transaction_id', 'created_at', 'updated_at', 'webhook_received_at')
    inlines = [PaymentLogInline]


@admin.register(PaymentLog)
class PaymentLogAdmin(admin.ModelAdmin):
    list_display = ('transaction', 'event', 'created_at')
    list_filter = ('event', 'created_at')
    search_fields = ('transaction__gateway_transaction_id', 'event', 'message')
    readonly_fields = ('transaction', 'event', 'message', 'data', 'created_at')
