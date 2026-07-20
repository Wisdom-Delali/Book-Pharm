"""Owner-created in-store sales from the portal — the same create_sale()
path the desktop POS and its /api/sales/ endpoint use, just entered here
instead of on the register. allow_oversell defaults to False (unlike
Jumia's manual entry): this sale is happening live as the owner types, so
a stock shortfall should be caught and shown immediately, the same
reasoning CLAUDE.md gives for the desktop app's own connected path.
"""
from datetime import date as date_cls

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, render

from apps.catalog.models import Book
from apps.sales.models import Sale
from apps.sales.services import InsufficientStockError, create_sale

from .manual_sale_items import resolve_manual_items

PAGE_SIZE = 20


def _parse_date(value):
    try:
        return date_cls.fromisoformat(value) if value else None
    except ValueError:
        return None


@login_required
def register_create(request):
    errors = []
    if request.method == 'POST':
        items, errors = resolve_manual_items(request)
        phone = request.POST.get('customer_phone', '').strip()
        if not phone:
            errors.append('Customer phone is required.')
        if not items:
            errors.append('Add at least one book.')
        if not errors:
            try:
                sale, _created = create_sale(
                    channel=Sale.Channel.IN_STORE,
                    items=items,
                    payment_method=request.POST.get('payment_method', Sale.PaymentMethod.CASH),
                    customer_phone=phone,
                    customer_full_name=request.POST.get('customer_full_name', '').strip(),
                    customer_email=request.POST.get('customer_email', '').strip(),
                    customer_birthday=_parse_date(request.POST.get('customer_birthday')),
                    attendant=request.user,
                )
                return render(request, 'portal/register/receipt.html', {
                    'active_nav': 'register', 'sale': sale, 'just_created': True,
                })
            except InsufficientStockError as exc:
                errors.append(str(exc))
            except ValueError as exc:
                errors.append(str(exc))

    return render(request, 'portal/register/create.html', {
        'active_nav': 'register',
        'errors': errors,
        'books': Book.objects.filter(is_active=True, stock_qty__gt=0).order_by('title'),
        'payment_methods': [
            (v, l) for v, l in Sale.PaymentMethod.choices if v != Sale.PaymentMethod.MARKETPLACE
        ],
    })


@login_required
def register_list(request):
    # Both sources of an IN_STORE sale — the desktop POS and this same
    # portal's own register form — write through the same create_sale()
    # into the same Sale table (CLAUDE.md §6), so one query covers both;
    # there's nothing here that distinguishes "came from Electron" from
    # "came from portal/register/new" except who's in the attendant column.
    sales = Sale.objects.filter(channel=Sale.Channel.IN_STORE).exclude(
        status=Sale.Status.PENDING
    ).select_related('customer', 'attendant').order_by('-created_at')
    paginator = Paginator(sales, PAGE_SIZE)
    return render(request, 'portal/register/list.html', {
        'active_nav': 'register_list',
        'page_obj': paginator.get_page(request.GET.get('page')),
    })


@login_required
def register_receipt(request, pk):
    sale = get_object_or_404(
        Sale.objects.prefetch_related('items__book'), pk=pk, channel=Sale.Channel.IN_STORE,
    )
    return render(request, 'portal/register/receipt.html', {'active_nav': 'register_list', 'sale': sale})
