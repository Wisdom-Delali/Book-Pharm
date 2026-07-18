from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.catalog.codes import normalize_isbn
from apps.catalog.models import Book
from apps.sales.services import InsufficientStockError, create_sale

from .serializers import BookSyncSerializer, SaleCreateSerializer, SaleDetailSerializer


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
        return Response(BookSyncSerializer(book).data)


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
