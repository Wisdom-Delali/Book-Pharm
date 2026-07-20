from datetime import date

from django.contrib.auth import authenticate
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import generics, status
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.catalog.codes import normalize_isbn
from apps.catalog.models import Book
from apps.customers.models import Customer, LoyaltyProgram
from apps.customers.phone import normalize_phone
from apps.payments.models import PaymentTransaction
from apps.payments.paystack import PaystackError, charge_mobile_money, verify_transaction
from apps.payments.views_helpers import PAYSTACK_CHANNEL_TO_METHOD
from apps.reports.utils import range_bounds_utc
from apps.sales.models import Sale
from apps.sales.services import (
    InsufficientStockError, cancel_pending_sale, create_pending_instore_sale, create_sale, finalize_paid_sale,
)

from .serializers import (
    BookSyncSerializer, CustomerSerializer, MomoChargeSerializer, PaymentTransactionSerializer,
    SaleBatchSyncSerializer, SaleCreateSerializer, SaleDetailSerializer,
)


class BookSyncListView(generics.ListAPIView):
    """GET /api/catalog/?updated_since=<ISO8601>&q=<search> — incremental
    catalog pull for the Electron POS's local mirror (CLAUDE.md §7), and
    doubles as the POS's live "type a title" search."""

    serializer_class = BookSyncSerializer

    def get_queryset(self):
        qs = Book.objects.select_related('category').all()
        updated_since = self.request.query_params.get('updated_since')
        if updated_since:
            parsed = parse_datetime(updated_since)
            if parsed is not None:
                if timezone.is_naive(parsed):
                    parsed = timezone.make_aware(parsed)
                qs = qs.filter(updated_at__gte=parsed)
        # Sync pulls (updated_since) must see is_active flips either way, so a
        # deactivated book's mirror state actually updates on the POS side.
        # Interactive search (q) is a different use — you can't add a
        # discontinued book to a sale, so it's filtered out here.
        query = self.request.query_params.get('q', '').strip()
        if query:
            qs = qs.filter(is_active=True).filter(Q(title__icontains=query) | Q(author__icontains=query))
        return qs.order_by('updated_at')


class BookLookupView(APIView):
    """GET /api/catalog/lookup/?code=<ISBN or internal code> — resolves a
    barcode scan or manually-typed code to one book, for the POS register."""

    def get(self, request):
        code = request.query_params.get('code', '').strip()
        if not code:
            return Response({'error': 'code is required'}, status=status.HTTP_400_BAD_REQUEST)

        book = None
        try:
            normalized = normalize_isbn(code)
        except DjangoValidationError:
            normalized = None
        if normalized:
            book = Book.objects.filter(isbn=normalized, is_active=True).first()
        if not book:
            book = Book.objects.filter(internal_code=code, is_active=True).first()
        if not book:
            return Response({'error': 'No matching book.'}, status=status.HTTP_404_NOT_FOUND)
        # context={'request': request} matters: without it, DRF's ImageField
        # serializes cover_image as a relative /media/... path, which breaks
        # once loaded from the Electron renderer's file:// origin.
        return Response(BookSyncSerializer(book, context={'request': request}).data)


class CustomerLookupView(APIView):
    """GET /api/customers/lookup/?phone=<any format> — the POS calls this
    once the attendant finishes typing a phone number, to show the
    customer's current loyalty balance before they decide whether to
    redeem. 404 (not a validation error) for an unknown or malformed number
    — either way there's just nothing to show yet; the customer gets
    created for real at checkout, same as always."""

    def get(self, request):
        raw = request.query_params.get('phone', '').strip()
        try:
            phone = normalize_phone(raw)
        except DjangoValidationError:
            return Response({'error': 'Not a valid phone number.'}, status=status.HTTP_404_NOT_FOUND)
        customer = Customer.objects.filter(phone=phone).first()
        if not customer:
            return Response({'error': 'No matching customer.'}, status=status.HTTP_404_NOT_FOUND)
        data = CustomerSerializer(customer).data
        program = LoyaltyProgram.current()
        data['point_value_ghs'] = str(program.point_value_ghs) if program else '0'
        data['min_redeem_points'] = program.min_redeem_points if program else 0
        return Response(data)


class DesktopLoginView(APIView):
    """POST /api/auth/login/ {email, password} -> {token, ...}. Replaces the
    old flow of the owner hand-copying a pre-provisioned device token into
    the app: every attendant (and the owner, if they use the register too)
    now signs in with their own portal-created credentials, and
    Sale.attendant attribution follows whoever is actually logged in on
    that machine rather than being fixed to the device itself. No auth
    required to reach this endpoint, obviously — it's how auth is obtained."""

    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        email = (request.data.get('email') or '').strip()
        password = request.data.get('password') or ''
        user = authenticate(request, username=email, password=password)
        if user is None:
            return Response({'error': 'Incorrect email or password.'}, status=status.HTTP_401_UNAUTHORIZED)
        if not user.is_active:
            return Response({'error': 'This account is inactive.'}, status=status.HTTP_401_UNAUTHORIZED)
        token, _ = Token.objects.get_or_create(user=user)
        return Response({
            'token': token.key, 'email': user.email, 'full_name': user.full_name, 'role': user.role,
        })


class MeView(APIView):
    """GET /api/me/ — who does this token belong to. Used by the POS top
    bar; also doubles as a cheap "is this token still valid" ping."""

    def get(self, request):
        user = request.user
        return Response({'email': user.email, 'full_name': user.full_name, 'role': user.role})


class SaleCreateView(APIView):
    """POST /api/sales/ — single sale, connected path (Phase 2). Rejects
    outright on insufficient stock, since the device is online and can just
    check. The offline batch endpoint (Phase 3) is a different view that
    calls the same create_sale() with allow_oversell=True."""

    def post(self, request):
        serializer = SaleCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            sale, created = create_sale(
                channel=data['channel'],
                items=data['items'],
                payment_method=data['payment_method'],
                offline_uuid=data.get('offline_uuid'),
                customer_phone=data.get('customer_phone') or None,
                customer_full_name=data.get('customer_full_name', ''),
                customer_email=data.get('customer_email', ''),
                customer_birthday=data.get('customer_birthday'),
                attendant=request.user,
                redeem_points=data.get('redeem_points', 0),
            )
        except InsufficientStockError as exc:
            return Response(
                {'error': str(exc), 'book_id': exc.book.id, 'available': exc.available},
                status=status.HTTP_409_CONFLICT,
            )
        except ValueError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        out = SaleDetailSerializer(sale)
        return Response(out.data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class SaleBatchSyncView(APIView):
    """POST /api/sync/sales/ — batch, idempotent on offline_uuid, per-UUID
    result (CLAUDE.md §7). Each sale gets its own create_sale() call (so its
    own transaction) — one bad entry in a batch of 20 must not roll back the
    other 19. allow_oversell=True always: a sale that already happened at
    the register must never be silently discarded for going stock-negative."""

    def post(self, request):
        serializer = SaleBatchSyncSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        results = []
        for sale_data in serializer.validated_data['sales']:
            offline_uuid = sale_data['offline_uuid']
            try:
                sale, created = create_sale(
                    channel=sale_data['channel'],
                    items=sale_data['items'],
                    payment_method=sale_data['payment_method'],
                    offline_uuid=offline_uuid,
                    customer_phone=sale_data.get('customer_phone') or None,
                    customer_full_name=sale_data.get('customer_full_name', ''),
                    customer_email=sale_data.get('customer_email', ''),
                    customer_birthday=sale_data.get('customer_birthday'),
                    attendant=request.user,
                    allow_oversell=True,
                    redeem_points=sale_data.get('redeem_points', 0),
                )
                results.append({
                    'offline_uuid': str(offline_uuid),
                    'status': 'accepted',
                    'sale': SaleDetailSerializer(sale).data,
                    'created': created,
                })
            except ValueError as exc:
                # Not a stock issue (that can never fail here) — a genuine
                # malformed entry, e.g. a book_id that doesn't exist.
                results.append({'offline_uuid': str(offline_uuid), 'status': 'rejected', 'error': str(exc)})

        return Response({'results': results}, status=status.HTTP_200_OK)


class MySalesView(generics.ListAPIView):
    """GET /api/sales/mine/?date=YYYY-MM-DD (defaults to today, Africa/Accra)
    — powers the desktop "My Day" tab: this attendant's own sales for the
    day, with enough detail (via SaleDetailSerializer) to re-open any of
    them as a receipt without a second request. Scoped by `attendant`, not
    by channel — correct either way, since attendant is only ever set on
    sales this device/login actually rang up."""

    serializer_class = SaleDetailSerializer

    def get_queryset(self):
        date_str = self.request.query_params.get('date', '').strip()
        try:
            target_date = date.fromisoformat(date_str) if date_str else timezone.localdate()
        except ValueError:
            target_date = timezone.localdate()
        start_dt, end_dt = range_bounds_utc(target_date, target_date)
        return (
            Sale.objects.filter(
                attendant=self.request.user, created_at__gte=start_dt, created_at__lt=end_dt,
            )
            .exclude(status=Sale.Status.PENDING)
            .prefetch_related('items__book')
            .order_by('-created_at')
        )


def _synthetic_pos_email(customer):
    """Paystack's Charge API requires an email; in-store customers only
    ever give a phone (CLAUDE.md: phone required, rest optional-prompted).
    A synthetic address is enough — the Charge API uses it as an account
    identifier, it isn't sent a receipt the way the storefront's
    redirect-flow checkout email is. `.local` (RFC 6762, not a real public
    TLD) got rejected outright by Paystack's own validation — confirmed
    live against the API, not assumed — so this uses `.com` instead."""
    return f"pos-{customer.phone.lstrip('+')}@bookpharm.com"


class MomoChargeView(APIView):
    """POST /api/sales/momo-charge/ — desktop POS MoMo payment (owner
    request, 2026-07-20). Creates the sale as PENDING (create_pending_instore_sale()
    — stock untouched until confirmed, same as online checkout) and, in the
    same call, sends the Paystack mobile money prompt to the customer's
    phone. If the sale is created but the Paystack call itself fails, the
    pending sale is cancelled immediately rather than left orphaned with no
    corresponding charge attempt to ever check."""

    def post(self, request):
        serializer = MomoChargeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            sale = create_pending_instore_sale(
                items=data['items'],
                customer_phone=data['customer_phone'],
                customer_full_name=data.get('customer_full_name', ''),
                customer_email=data.get('customer_email', ''),
                customer_birthday=data.get('customer_birthday'),
                attendant=request.user,
            )
        except InsufficientStockError as exc:
            return Response(
                {'error': str(exc), 'book_id': exc.book.id, 'available': exc.available},
                status=status.HTTP_409_CONFLICT,
            )
        except ValueError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        email = data.get('customer_email') or _synthetic_pos_email(sale.customer)
        try:
            charge_data = charge_mobile_money(
                email=email, amount_ghs=sale.total, reference=str(sale.offline_uuid),
                phone=data['momo_phone'], provider=data['momo_provider'],
            )
        except PaystackError as exc:
            cancel_pending_sale(sale)
            # A PaymentTransaction row even for an attempt that never made it
            # to Paystack's "prompt sent" state — otherwise a charge that
            # fails instantly (bad number, network blip) leaves no trace at
            # all on the Payments page, which defeats its actual purpose.
            PaymentTransaction.objects.create(
                sale=sale, provider=PaymentTransaction.Provider.PAYSTACK,
                provider_ref=str(sale.offline_uuid), amount=sale.total,
                status=PaymentTransaction.Status.FAILED, raw_payload={'error': str(exc)},
            )
            return Response({'error': f'Could not start MoMo charge: {exc}'}, status=status.HTTP_502_BAD_GATEWAY)

        PaymentTransaction.objects.create(
            sale=sale, provider=PaymentTransaction.Provider.PAYSTACK,
            provider_ref=str(sale.offline_uuid), amount=sale.total,
            status=PaymentTransaction.Status.PENDING, raw_payload=charge_data,
        )

        out = SaleDetailSerializer(sale).data
        out['paystack_status'] = charge_data.get('status', '')
        out['paystack_display_text'] = charge_data.get('display_text', '')
        return Response(out, status=status.HTTP_201_CREATED)


class PaymentStatusView(APIView):
    """GET /api/payments/<offline_uuid>/status/ — checks Paystack for the
    current state of a MoMo charge and finalizes the sale (stock decrement,
    PAID/COMPLETED, loyalty points — via the same finalize_paid_sale() the
    webhook uses) if it's now succeeded. Powers both the desktop app's
    automatic polling right after sending a charge and its manual "Check
    Status" button — same call either way, same as CLAUDE.md §8's
    webhook-plus-verify-on-return principle applied to a POS terminal
    instead of a browser redirect. A no-op re-check (already PAID, or
    Paystack still says pending) is cheap and safe to call repeatedly."""

    def get(self, request, offline_uuid):
        sale = get_object_or_404(Sale, offline_uuid=offline_uuid, channel=Sale.Channel.IN_STORE)
        paystack_status = ''  # stays blank if already PAID — nothing to check

        if sale.payment_status != Sale.PaymentStatus.PAID:
            try:
                data = verify_transaction(str(offline_uuid))
            except PaystackError as exc:
                return Response({'error': f'Could not check payment status: {exc}'}, status=status.HTTP_502_BAD_GATEWAY)

            paystack_status = data.get('status', '')
            if paystack_status == 'success':
                txn_status = PaymentTransaction.Status.SUCCESS
            elif paystack_status == 'failed':
                txn_status = PaymentTransaction.Status.FAILED
            else:
                txn_status = PaymentTransaction.Status.PENDING
            PaymentTransaction.objects.filter(provider_ref=str(offline_uuid)).update(
                status=txn_status, raw_payload=data,
            )

            if paystack_status == 'success':
                method = PAYSTACK_CHANNEL_TO_METHOD.get(data.get('channel'), Sale.PaymentMethod.MOMO)
                sale = finalize_paid_sale(sale, payment_method=method)

        out = SaleDetailSerializer(sale).data
        out['paystack_status'] = paystack_status
        return Response(out)


class CancelPendingSaleView(APIView):
    """POST /api/sales/<offline_uuid>/cancel/ — attendant abandons a pending
    MoMo charge (failed, timed out, customer changed their mind). No stock
    reversal needed — create_pending_instore_sale() never touched stock."""

    def post(self, request, offline_uuid):
        sale = get_object_or_404(Sale, offline_uuid=offline_uuid, channel=Sale.Channel.IN_STORE)
        sale = cancel_pending_sale(sale)
        return Response(SaleDetailSerializer(sale).data)


class InStorePaymentsListView(generics.ListAPIView):
    """GET /api/payments/in-store/ — every MoMo-via-Paystack payment attempt
    rung up on any device, not scoped to the requesting attendant (owner
    request: "records of payments for both attendant and admin" — whoever's
    signed into any desktop terminal sees the same shared list, since a
    charge one attendant started may need another to notice or retry it).
    Powers the desktop Payments page. Capped at the 200 most recent rather
    than paginated — a POS "recent activity" view, not an archive browser."""

    serializer_class = PaymentTransactionSerializer

    def get_queryset(self):
        return PaymentTransaction.objects.filter(
            sale__channel=Sale.Channel.IN_STORE,
        ).select_related('sale', 'sale__customer', 'sale__attendant').order_by('-created_at')[:200]
