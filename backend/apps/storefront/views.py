import json

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Avg, Count, Q, Sum
from django.db.models.functions import Coalesce
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from apps.catalog.models import Book, Category
from apps.fulfillment.models import DeliveryPricingRule, Fulfillment, Review
from apps.payments.models import PaymentTransaction
from apps.payments.paystack import PaystackError, initialize_transaction, verify_transaction
from apps.payments.views_helpers import PAYSTACK_CHANNEL_TO_METHOD
from apps.sales.models import DiscountRule, Sale
from apps.sales.services import InsufficientStockError, create_pending_online_sale, finalize_paid_sale

from .ajax import is_ajax
from .cart import Cart
from .forms import CheckoutForm

PAGE_SIZE = 12


def book_list(request):
    books = Book.objects.filter(is_active=True).select_related('category')
    query = request.GET.get('q', '').strip()
    if query:
        books = books.filter(Q(title__icontains=query) | Q(author__icontains=query))
    category_slug = request.GET.get('category', '').strip()
    if category_slug:
        books = books.filter(category__slug=category_slug)
    sort = request.GET.get('sort', '').strip()
    books = books.order_by('-created_at') if sort == 'new' else books.order_by('title')

    paginator = Paginator(books, PAGE_SIZE)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'storefront/book_list.html', {
        'page_obj': page_obj,
        'categories': Category.objects.all(),
        'query': query,
        'selected_category': category_slug,
        'sort': sort,
    })


def home(request):
    # Bestsellers by units sold (PAID sales only) — falls back to the newest
    # active titles when the shop has no sales history yet, since the
    # secondary sort key is -created_at either way.
    featured_qs = (
        Book.objects.filter(is_active=True, stock_qty__gt=0)
        .annotate(total_sold=Coalesce(
            Sum('sale_items__qty', filter=Q(sale_items__sale__payment_status=Sale.PaymentStatus.PAID)), 0,
        ))
        .select_related('category')
        .order_by('-total_sold', '-created_at')[:2]
    )
    featured_books = [
        {'book': b, 'badge': 'Bestseller' if b.total_sold > 0 else 'New In'} for b in featured_qs
    ]
    featured_ids = [entry['book'].id for entry in featured_books]

    new_arrivals = list(
        Book.objects.filter(is_active=True)
        .exclude(id__in=featured_ids)
        .select_related('category')
        .order_by('-created_at')[:8]
    )

    categories = Category.objects.annotate(
        book_count=Count('books', filter=Q(books__is_active=True))
    ).filter(book_count__gt=0)

    # Only a storewide discount is worth headlining on the homepage — a
    # category/book-scoped rule wouldn't honestly support a storewide claim.
    active_discount = DiscountRule.objects.filter(
        is_active=True, scope=DiscountRule.Scope.GLOBAL,
    ).order_by('-created_at').first()

    return render(request, 'storefront/home.html', {
        'featured_books': featured_books,
        'new_arrivals': new_arrivals,
        'categories': categories,
        'active_discount': active_discount,
    })


def book_detail(request, slug):
    book = get_object_or_404(Book, slug=slug, is_active=True)
    # Reviews hang off Sale, not Book (CLAUDE.md §6) — a book's reviews are
    # every review left on a sale that included it. Aggregate before
    # slicing: a sliced queryset can't be reused for both the rating summary
    # and the recent-reviews list.
    reviews_qs = Review.objects.filter(sale__items__book=book).select_related('sale').distinct()
    rating = reviews_qs.aggregate(avg=Avg('rating'), count=Count('id'))
    reviews = reviews_qs[:10]
    related_books = (
        Book.objects.filter(category=book.category, is_active=True)
        .exclude(pk=book.pk).select_related('category')[:4]
    )

    # WEB-08: server-rendered meta tags + structured data for search
    # indexing. Built here (not in the template) so json.dumps handles
    # escaping correctly — hand-rolling JSON in a template invites subtly
    # broken quoting. The </ mitigation stops a title/description
    # containing "</script>" from breaking out of the tag.
    structured_data = {
        '@context': 'https://schema.org',
        '@type': 'Book',
        'name': book.title,
        'isbn': book.isbn or None,
        'description': book.description or None,
        'offers': {
            '@type': 'Offer',
            'price': str(book.selling_price),
            'priceCurrency': 'GHS',
            'availability': 'https://schema.org/InStock' if book.stock_qty > 0 else 'https://schema.org/OutOfStock',
            'url': request.build_absolute_uri(),
        },
    }
    if book.author:
        structured_data['author'] = {'@type': 'Person', 'name': book.author}
    if rating['count']:
        structured_data['aggregateRating'] = {
            '@type': 'AggregateRating',
            'ratingValue': str(round(rating['avg'], 1)),
            'reviewCount': rating['count'],
        }
    structured_data = {k: v for k, v in structured_data.items() if v is not None}
    structured_data_json = json.dumps(structured_data).replace('</', '<\\/')

    return render(request, 'storefront/book_detail.html', {
        'book': book, 'reviews': reviews, 'structured_data_json': structured_data_json,
        'avg_rating': rating['avg'], 'review_count': rating['count'],
        'full_stars': round(rating['avg']) if rating['avg'] else 0,
        'related_books': related_books,
    })


def cart_view(request):
    cart = Cart(request)
    return render(request, 'storefront/cart.html', {'items': cart.get_items(), 'subtotal': cart.subtotal()})


def cart_add(request, book_id):
    if request.method == 'POST':
        book = get_object_or_404(Book, pk=book_id, is_active=True)
        qty = int(request.POST.get('qty', 1))
        cart = Cart(request)
        cart.add(book.id, max(qty, 1))
        message = f'Added "{book.title}" to your cart.'
        if is_ajax(request):
            # storefront.js intercepts this form's submit — no redirect, no
            # server-rendered flash message (that would just sit in the
            # session and pop up unexpectedly on whatever page the customer
            # navigates to next). The toast is shown directly from this
            # response instead.
            return JsonResponse({'ok': True, 'message': message, 'cart_count': len(cart)})
        messages.success(request, message)
    return redirect(request.POST.get('next') or 'storefront:cart')


def cart_update(request, book_id):
    if request.method == 'POST':
        qty = int(request.POST.get('qty', 0))
        cart = Cart(request)
        cart.set_qty(book_id, qty)
        if is_ajax(request):
            # The quick +/- stepper (WISDOM.md #4) submits this on every
            # click — no page reload, so the JSON response carries
            # everything the page needs to patch in place: this row's own
            # total (or a removal flag, if qty was dragged to 0), plus the
            # cart-wide subtotal and badge count, which change regardless
            # of which row triggered the update.
            item = next((i for i in cart.get_items() if i['book'].id == book_id), None)
            return JsonResponse({
                'ok': True,
                'removed': item is None,
                'qty': item['qty'] if item else 0,
                'line_total': str(item['line_total']) if item else '0.00',
                'subtotal': str(cart.subtotal()),
                'cart_count': len(cart),
            })
    return redirect('storefront:cart')


def cart_remove(request, book_id):
    if request.method == 'POST':
        cart = Cart(request)
        cart.remove(book_id)
        if is_ajax(request):
            return JsonResponse({'ok': True, 'subtotal': str(cart.subtotal()), 'cart_count': len(cart)})
    return redirect('storefront:cart')


def checkout(request):
    cart = Cart(request)
    items = cart.get_items()
    if not items:
        messages.error(request, 'Your cart is empty.')
        return redirect('storefront:cart')

    delivery_zones = DeliveryPricingRule.objects.filter(is_active=True, method=DeliveryPricingRule.Method.FIXED_ZONE)

    if request.method == 'POST':
        form = CheckoutForm(request.POST)
        if form.is_valid():
            ftype = form.cleaned_data['fulfillment_type']
            zone = form.cleaned_data.get('delivery_zone')
            address = form.cleaned_data.get('address', '')
            delivery_fee = zone.fee if ftype == Fulfillment.Type.DELIVERY and zone else 0

            try:
                sale = create_pending_online_sale(
                    items=[{'book_id': item['book'].id, 'qty': item['qty']} for item in items],
                    customer_phone=form.cleaned_data['customer_phone'],
                    customer_full_name=form.cleaned_data.get('customer_full_name', ''),
                    customer_email=form.cleaned_data['customer_email'],
                    customer_birthday=form.cleaned_data.get('customer_birthday'),
                    fulfillment_type=ftype,
                    address=address,
                    delivery_fee=delivery_fee,
                )
            except InsufficientStockError as exc:
                messages.error(request, str(exc))
                return redirect('storefront:cart')

            if ftype == Fulfillment.Type.DELIVERY and zone:
                sale.fulfillment.pricing_rule = zone
                sale.fulfillment.save(update_fields=['pricing_rule'])

            try:
                data = initialize_transaction(
                    email=form.cleaned_data['customer_email'],
                    amount_ghs=sale.total,
                    reference=str(sale.offline_uuid),
                    callback_url=request.build_absolute_uri(reverse('storefront:paystack_callback')),
                )
            except PaystackError as exc:
                messages.error(request, f'Payment could not be started: {exc}')
                return redirect('storefront:checkout')

            PaymentTransaction.objects.create(
                sale=sale, provider=PaymentTransaction.Provider.PAYSTACK,
                provider_ref=str(sale.offline_uuid), amount=sale.total,
                status=PaymentTransaction.Status.PENDING, raw_payload=data,
            )

            cart.clear()
            return redirect(data['authorization_url'])
    else:
        form = CheckoutForm(initial={'fulfillment_type': Fulfillment.Type.DELIVERY})

    return render(request, 'storefront/checkout.html', {
        'form': form, 'items': items, 'subtotal': cart.subtotal(), 'delivery_zones': delivery_zones,
    })


def paystack_callback(request):
    """Verify-on-return — CLAUDE.md §8: never trust the redirect alone.
    This is a *courtesy* fast-path for the customer's browser; the webhook
    (apps/payments/views.py) is the durable path if this never fires."""
    reference = request.GET.get('reference') or request.GET.get('trxref')
    if not reference:
        messages.error(request, 'Missing payment reference.')
        return redirect('storefront:home')

    sale = get_object_or_404(Sale, offline_uuid=reference)

    try:
        data = verify_transaction(reference)
    except PaystackError as exc:
        messages.error(request, f'Could not verify payment: {exc}')
        return redirect('storefront:order_confirmation', offline_uuid=sale.offline_uuid)

    PaymentTransaction.objects.filter(provider_ref=reference).update(
        status=PaymentTransaction.Status.SUCCESS if data.get('status') == 'success' else PaymentTransaction.Status.FAILED,
        raw_payload=data,
    )

    if data.get('status') == 'success':
        method = PAYSTACK_CHANNEL_TO_METHOD.get(data.get('channel'), Sale.PaymentMethod.CARD)
        finalize_paid_sale(sale, payment_method=method)

    return redirect('storefront:order_confirmation', offline_uuid=sale.offline_uuid)


def order_confirmation(request, offline_uuid):
    sale = get_object_or_404(Sale, offline_uuid=offline_uuid)
    return render(request, 'storefront/order_confirmation.html', {'sale': sale})


def confirm_receipt(request, offline_uuid):
    sale = get_object_or_404(Sale, offline_uuid=offline_uuid, payment_status=Sale.PaymentStatus.PAID)
    if request.method == 'POST':
        fulfillment = sale.fulfillment
        fulfillment.confirmed_by_customer_at = timezone.now()
        fulfillment.status = Fulfillment.Status.COMPLETED
        fulfillment.save(update_fields=['confirmed_by_customer_at', 'status'])
        messages.success(request, 'Thanks for confirming! You can leave a review below.')
    return redirect('storefront:order_confirmation', offline_uuid=sale.offline_uuid)


def submit_review(request, offline_uuid):
    sale = get_object_or_404(Sale, offline_uuid=offline_uuid, payment_status=Sale.PaymentStatus.PAID)
    if request.method == 'POST':
        rating = int(request.POST.get('rating', 0))
        comment = request.POST.get('comment', '').strip()
        if 1 <= rating <= 5:
            Review.objects.create(sale=sale, rating=rating, comment=comment)
            messages.success(request, 'Thanks for your feedback!')
        else:
            messages.error(request, 'Please choose a rating between 1 and 5.')
    return redirect('storefront:order_confirmation', offline_uuid=sale.offline_uuid)
