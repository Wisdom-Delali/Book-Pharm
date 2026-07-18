from rest_framework import serializers

from apps.catalog.models import Book
from apps.sales.models import Sale, SaleItem


class BookSyncSerializer(serializers.ModelSerializer):
    category = serializers.CharField(source='category.name', read_only=True)

    class Meta:
        model = Book
        # cost_price is deliberately excluded — profit-sensitive, and the POS
        # doesn't need it to complete a sale (CLAUDE.md: never expose cost_price
        # gratuitously; the portal's reporting is the right place for it).
        fields = [
            'id', 'isbn', 'internal_code', 'title', 'author', 'category',
            'selling_price', 'stock_qty', 'low_stock_threshold', 'cover_image',
            'is_active', 'updated_at',
        ]


class SaleItemInputSerializer(serializers.Serializer):
    book_id = serializers.IntegerField()
    qty = serializers.IntegerField(min_value=1)


class SaleCreateSerializer(serializers.Serializer):
    channel = serializers.ChoiceField(choices=Sale.Channel.choices, default=Sale.Channel.IN_STORE)
    items = SaleItemInputSerializer(many=True)
    payment_method = serializers.ChoiceField(choices=Sale.PaymentMethod.choices)
    offline_uuid = serializers.UUIDField(required=False, allow_null=True)
    customer_phone = serializers.CharField(required=False, allow_blank=True)
    customer_full_name = serializers.CharField(required=False, allow_blank=True)
    customer_email = serializers.EmailField(required=False, allow_blank=True)
    customer_birthday = serializers.DateField(required=False, allow_null=True)

    def validate_items(self, items):
        if not items:
            raise serializers.ValidationError('At least one item is required.')
        return items


class SaleSyncItemSerializer(SaleCreateSerializer):
    # Required here (unlike the single-sale endpoint) — every queued outbox
    # entry was already assigned a UUID client-side before it could be
    # queued at all, online or offline (CLAUDE.md §7).
    offline_uuid = serializers.UUIDField(required=True)


class SaleBatchSyncSerializer(serializers.Serializer):
    sales = SaleSyncItemSerializer(many=True)

    def validate_sales(self, sales):
        if not sales:
            raise serializers.ValidationError('At least one sale is required.')
        return sales


class SaleItemOutputSerializer(serializers.ModelSerializer):
    title = serializers.CharField(source='book.title')
    author = serializers.CharField(source='book.author')

    class Meta:
        model = SaleItem
        fields = ['book', 'title', 'author', 'qty', 'unit_price', 'line_discount', 'line_total']


class SaleDetailSerializer(serializers.ModelSerializer):
    items = SaleItemOutputSerializer(many=True, read_only=True)
    customer_phone = serializers.CharField(source='customer.phone', default=None, read_only=True)
    customer_full_name = serializers.CharField(source='customer.full_name', default='', read_only=True)

    class Meta:
        model = Sale
        fields = [
            'id', 'channel', 'customer_phone', 'customer_full_name', 'subtotal', 'discount_amount',
            'delivery_fee', 'total', 'payment_method', 'payment_status', 'status',
            'offline_uuid', 'created_at', 'items',
        ]
