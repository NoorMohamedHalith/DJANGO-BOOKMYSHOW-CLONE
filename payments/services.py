import hmac
import hashlib
import json
import uuid
import razorpay
import stripe
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from django.conf import settings
from django.core.exceptions import ValidationError, PermissionDenied
from django.shortcuts import get_object_or_404

from movies.models import Booking, Seat
from seat_reservations.models import SeatReservation, ReservedSeat
from .models import PaymentTransaction, PaymentLog


class PaymentService:
    @classmethod
    def get_razorpay_client(cls):
        key_id = getattr(settings, 'RAZORPAY_KEY_ID', 'rzp_test_mockkeyid123')
        key_secret = getattr(settings, 'RAZORPAY_KEY_SECRET', 'mockkeysecret123456789')
        return razorpay.Client(auth=(key_id, key_secret))

    @classmethod
    def create_payment_order(cls, user, reservation_uuid, amount=None, gateway='RAZORPAY'):
        """
        Creates a PaymentTransaction and generates order details via Razorpay / Stripe SDK.
        """
        if not user or not user.is_authenticated:
            raise PermissionDenied("Authentication required.")

        reservation = get_object_or_404(SeatReservation, reservation_uuid=reservation_uuid)

        if reservation.user != user:
            raise PermissionDenied("You do not own this seat reservation.")

        if reservation.status != 'ACTIVE' or reservation.is_expired():
            raise ValidationError("Reservation is expired or no longer active.")

        if amount is None:
            seat_count = reservation.reserved_seats.count()
            amount = Decimal(seat_count * 200)
        else:
            amount = Decimal(amount)

        gateway = gateway.upper()
        key_id = getattr(settings, 'RAZORPAY_KEY_ID', 'rzp_test_mockkeyid123')
        key_secret = getattr(settings, 'RAZORPAY_KEY_SECRET', 'mockkeysecret123456789')

        gateway_order_id = f"order_{gateway[:3].lower()}_{uuid.uuid4().hex[:14]}"
        order_response_data = {}

        if gateway == 'RAZORPAY':
            try:
                client = cls.get_razorpay_client()
                order_params = {
                    'amount': int(amount * 100),  # amount in paise
                    'currency': 'INR',
                    'receipt': f"rcpt_{uuid.uuid4().hex[:10]}",
                    'notes': {
                        'reservation_uuid': str(reservation.reservation_uuid),
                        'username': user.username
                    }
                }
                rzp_order = client.order.create(data=order_params)
                gateway_order_id = rzp_order.get('id', gateway_order_id)
                order_response_data = rzp_order
            except Exception:
                # Sandbox fallback if SDK API credentials fail
                order_response_data = {
                    'id': gateway_order_id,
                    'entity': 'order',
                    'amount': int(amount * 100),
                    'currency': 'INR',
                    'status': 'created'
                }
        elif gateway == 'STRIPE':
            try:
                stripe.api_key = getattr(settings, 'STRIPE_SECRET_KEY', 'sk_test_mocksecretkey')
                intent = stripe.PaymentIntent.create(
                    amount=int(amount * 100),
                    currency='inr',
                    metadata={'reservation_uuid': str(reservation.reservation_uuid)}
                )
                gateway_order_id = intent.id
                order_response_data = {'id': intent.id, 'client_secret': intent.client_secret}
            except Exception:
                order_response_data = {'id': gateway_order_id, 'client_secret': f"secret_{gateway_order_id}"}

        # Check existing transaction for this reservation
        existing_tx = PaymentTransaction.objects.filter(reservation=reservation, status='INITIATED').first()
        if existing_tx:
            existing_tx.gateway_transaction_id = gateway_order_id
            existing_tx.amount = amount
            existing_tx.payment_gateway = gateway
            existing_tx.payment_data = order_response_data
            existing_tx.save()
            transaction_obj = existing_tx
        else:
            transaction_obj = PaymentTransaction.objects.create(
                user=user,
                reservation=reservation,
                amount=amount,
                payment_gateway=gateway,
                gateway_transaction_id=gateway_order_id,
                status='INITIATED',
                payment_data=order_response_data
            )

        PaymentLog.objects.create(
            transaction=transaction_obj,
            event='order_created',
            message=f"Order created via {gateway}",
            data={'amount': float(amount), 'order_id': gateway_order_id}
        )

        return transaction_obj, {
            'order_id': gateway_order_id,
            'key_id': key_id,
            'amount': float(amount),
            'currency': 'INR',
            'reservation_uuid': str(reservation.reservation_uuid),
            'gateway': gateway,
            'raw_data': order_response_data
        }

    @classmethod
    def handle_payment_success(cls, transaction_obj, gateway_transaction_id=None, payment_data=None):
        """
        Marks transaction as SUCCESS, sets reservation to CONFIRMED, creates Booking entries,
        and marks seats as is_booked = True.
        """
        if payment_data is None:
            payment_data = {}

        with transaction.atomic():
            tx = PaymentTransaction.objects.select_for_update().get(id=transaction_obj.id)
            
            if tx.status == 'SUCCESS':
                # Already processed (idempotent)
                return tx.booking

            if gateway_transaction_id:
                tx.gateway_transaction_id = gateway_transaction_id

            tx.status = 'SUCCESS'
            tx.payment_data.update(payment_data)
            tx.save()

            reservation = tx.reservation
            if reservation:
                reservation.status = 'CONFIRMED'
                reservation.save()

                created_booking = None
                for rs in reservation.reserved_seats.select_related('seat').all():
                    seat = rs.seat
                    seat.is_booked = True
                    seat.save()

                    created_booking = Booking.objects.create(
                        user=tx.user,
                        seat=seat,
                        movie=reservation.show.movie,
                        theater=reservation.show
                    )

                if created_booking:
                    tx.booking = created_booking
                    tx.save()

            PaymentLog.objects.create(
                transaction=tx,
                event='payment_success',
                message="Payment confirmed successfully and bookings created",
                data=payment_data
            )

            return tx.booking

    @classmethod
    def handle_payment_failure(cls, transaction_obj, gateway_transaction_id=None, payment_data=None):
        """
        Marks transaction as FAILED and releases the seat reservation.
        """
        if payment_data is None:
            payment_data = {}

        with transaction.atomic():
            tx = PaymentTransaction.objects.select_for_update().get(id=transaction_obj.id)
            tx.status = 'FAILED'
            if gateway_transaction_id:
                tx.gateway_transaction_id = gateway_transaction_id
            tx.payment_data.update(payment_data)
            tx.save()

            if tx.reservation:
                tx.reservation.status = 'RELEASED'
                tx.reservation.save()

            PaymentLog.objects.create(
                transaction=tx,
                event='payment_failed',
                message="Payment failed or cancelled, reservation released",
                data=payment_data
            )

    @classmethod
    def verify_razorpay_signature(cls, payload_bytes, signature, secret):
        """
        Cryptographic verification of Razorpay webhook signature.
        """
        if not signature or not secret:
            return False
        expected_sig = hmac.new(
            secret.encode('utf-8'),
            payload_bytes,
            hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected_sig, signature)

    @classmethod
    def handle_webhook(cls, request_body, signature, gateway='RAZORPAY'):
        """
        Processes webhook event with signature verification and IDEMPOTENCY check.
        """
        secret = getattr(settings, 'RAZORPAY_WEBHOOK_SECRET', 'mockwebhooksecret123456')
        is_valid_signature = cls.verify_razorpay_signature(request_body, signature, secret)

        try:
            payload = json.loads(request_body.decode('utf-8'))
        except Exception:
            payload = {}

        event_type = payload.get('event', 'unknown')
        order_id = None
        payment_data = {}

        if gateway.upper() == 'RAZORPAY':
            entity_data = payload.get('payload', {}).get('payment', {}).get('entity', {})
            order_id = entity_data.get('order_id') or entity_data.get('id')
            payment_data = entity_data
        elif gateway.upper() == 'STRIPE':
            order_id = payload.get('data', {}).get('object', {}).get('id')
            payment_data = payload.get('data', {}).get('object', {})

        if not order_id:
            return {'success': False, 'error': 'Missing transaction or order ID in webhook'}

        tx = PaymentTransaction.objects.filter(gateway_transaction_id=order_id).first()

        # Idempotency Check: if webhook already received or payment already SUCCESS
        if tx and (tx.webhook_received_at is not None or tx.status == 'SUCCESS'):
            PaymentLog.objects.create(
                transaction=tx,
                event='webhook_duplicate_ignored',
                message=f"Duplicate webhook event {event_type} ignored",
                data={'event': event_type}
            )
            return {
                'success': True,
                'idempotent': True,
                'message': f"Webhook event {event_type} already processed for transaction {tx.gateway_transaction_id}"
            }

        if not tx:
            return {'success': False, 'error': f"Transaction {order_id} not found"}

        tx.webhook_received_at = timezone.now()
        tx.webhook_signature_valid = is_valid_signature
        tx.save()

        PaymentLog.objects.create(
            transaction=tx,
            event='webhook_received',
            message=f"Webhook received ({event_type}), signature valid: {is_valid_signature}",
            data={'event': event_type, 'signature_valid': is_valid_signature}
        )

        if not is_valid_signature:
            return {'success': False, 'error': 'Invalid webhook signature'}

        if event_type in ['order.paid', 'payment.captured', 'payment_intent.succeeded']:
            cls.handle_payment_success(tx, order_id, payment_data)
        elif event_type in ['payment.failed', 'payment_intent.payment_failed']:
            cls.handle_payment_failure(tx, order_id, payment_data)

        return {'success': True, 'event': event_type, 'transaction_id': tx.gateway_transaction_id}

    @classmethod
    def get_user_payment_history(cls, user):
        """
        Returns all PaymentTransactions for user with related booking & reservation info.
        """
        return PaymentTransaction.objects.filter(user=user).select_related(
            'reservation', 'booking', 'booking__movie', 'booking__theater'
        ).order_by('-created_at')
