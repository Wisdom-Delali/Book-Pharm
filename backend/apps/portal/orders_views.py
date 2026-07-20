from urllib.parse import quote

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.customers.phone import normalize_phone
from apps.fulfillment.models import Fulfillment
from apps.messaging.sms_client import SmsError, send_sms
from apps.sales.models import Sale

PAGE_SIZE = 20


def _rider_sms_text(sale):
    fulfillment = sale.fulfillment
    if fulfillment.latitude is not None and fulfillment.longitude is not None:
        maps_url = f'https://www.google.com/maps/search/?api=1&query={fulfillment.latitude},{fulfillment.longitude}'
    else:
        maps_url = f'https://www.google.com/maps/search/?api=1&query={quote(fulfillment.address)}'
    item_count = sum(item.qty for item in sale.items.all())
    customer_name = sale.customer.full_name or sale.customer.phone
    return (
        f'Book Pharm delivery, Order #{sale.id}: {item_count} item(s), GHS {sale.total}. '
        f'Customer: {customer_name} {sale.customer.phone}. Address: {fulfillment.address}. '
        f'Map: {maps_url}'
    )


@login_required
def order_list(request):
    orders = Sale.objects.filter(channel=Sale.Channel.ONLINE).exclude(
        payment_status=Sale.PaymentStatus.PENDING
    ).select_related('customer', 'fulfillment').order_by('-created_at')
    paginator = Paginator(orders, PAGE_SIZE)
    return render(request, 'portal/orders/list.html', {
        'active_nav': 'orders',
        'page_obj': paginator.get_page(request.GET.get('page')),
    })


@login_required
def order_detail(request, pk):
    sale = get_object_or_404(
        Sale.objects.select_related('customer', 'fulfillment').prefetch_related('items__book', 'payment_transactions'),
        pk=pk, channel=Sale.Channel.ONLINE,
    )
    return render(request, 'portal/orders/detail.html', {'active_nav': 'orders', 'sale': sale})


@login_required
def send_to_rider(request, pk):
    """Standard DELIVERY dispatch — not RIDER_DELIVERY (Yango/Bolt/Uber),
    which has its own booking flow (mark_rider_booked below) and never
    touches these fields. The attendant types in whoever's phone number is
    doing this delivery (no saved rider accounts) and an SMS with the order
    + a Google Maps link goes out immediately.

    Sent synchronously, a deliberate exception to "SMS never sends inline"
    (CLAUDE.md §8, apps/messaging/sms_client.py) — that rule exists because
    a bulk campaign loop could run long on shared hosting; this is exactly
    one bounded external call, the rider needs it now, and the existing
    "Send Now" campaign button already can't offer that (queues for the
    next 15-minute cron run instead) — owner decision, 2026-07-20.
    """
    sale = get_object_or_404(
        Sale.objects.select_related('customer', 'fulfillment').prefetch_related('items'),
        pk=pk, channel=Sale.Channel.ONLINE,
    )
    if request.method == 'POST' and sale.fulfillment.type == Fulfillment.Type.DELIVERY:
        try:
            phone = normalize_phone(request.POST.get('rider_phone', ''))
        except ValidationError as exc:
            messages.error(request, exc.message)
        else:
            try:
                send_sms(to=phone, message=_rider_sms_text(sale))
            except SmsError as exc:
                messages.error(request, f'Could not send SMS: {exc}')
            else:
                fulfillment = sale.fulfillment
                fulfillment.delivery_rider_phone = phone
                fulfillment.delivery_rider_sms_sent_at = timezone.now()
                fulfillment.delivery_rider_sms_sent_by = request.user
                fulfillment.save(update_fields=[
                    'delivery_rider_phone', 'delivery_rider_sms_sent_at', 'delivery_rider_sms_sent_by',
                ])
                messages.success(request, f'Order details sent to {phone}.')
    return redirect('portal:order_detail', pk=sale.pk)


@login_required
def rider_queue(request):
    pending = Fulfillment.objects.filter(
        type=Fulfillment.Type.RIDER_DELIVERY, rider_booked_at__isnull=True
    ).select_related('sale', 'sale__customer').order_by('sale__created_at')
    return render(request, 'portal/orders/rider_queue.html', {'active_nav': 'orders', 'pending': pending})


@login_required
def mark_rider_booked(request, pk):
    fulfillment = get_object_or_404(Fulfillment, pk=pk, type=Fulfillment.Type.RIDER_DELIVERY)
    if request.method == 'POST':
        fulfillment.rider_booked_at = timezone.now()
        fulfillment.rider_booked_by = request.user
        fulfillment.status = Fulfillment.Status.READY
        fulfillment.save(update_fields=['rider_booked_at', 'rider_booked_by', 'status'])
    return redirect('portal:rider_queue')
