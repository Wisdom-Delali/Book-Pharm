from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.fulfillment.models import Fulfillment
from apps.sales.models import Sale

PAGE_SIZE = 20


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
