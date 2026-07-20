from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render

from apps.catalog.models import Book
from apps.sales.models import Sale
from apps.sales.services import create_sale, return_sale

from .htmx import is_htmx as _is_htmx
from .manual_sale_items import resolve_manual_items

CONTENT_TEMPLATE = 'portal/marketplace/_content.html'
PAGE_TEMPLATE = 'portal/marketplace/list.html'
PAGE_SIZE = 20


def _list_context(request):
    qs = Sale.objects.filter(channel=Sale.Channel.JUMIA).select_related('customer').prefetch_related('items__book')
    paginator = Paginator(qs, PAGE_SIZE)
    return {
        'active_nav': 'marketplace',
        'page_obj': paginator.get_page(request.GET.get('page')),
        'panel_open': False,
        'form_errors': None,
        'books': None,
    }


def _render_list(request, extra_context=None):
    context = _list_context(request)
    context.update(extra_context or {})
    template = CONTENT_TEMPLATE if _is_htmx(request) else PAGE_TEMPLATE
    return render(request, template, context)


@login_required
def marketplace_list(request):
    return _render_list(request)


@login_required
def marketplace_create(request):
    errors = []
    if request.method == 'POST':
        external_ref = request.POST.get('external_ref', '').strip()
        items, errors = resolve_manual_items(request)
        if not items:
            errors.append('Add at least one book.')
        if not errors:
            try:
                # allow_oversell=True: the Jumia sale already genuinely
                # happened (often already shipped/paid) — Book Pharm is just
                # recording it after the fact. Blocking that recording over
                # a stock mismatch would be exactly what CLAUDE.md §7 warns
                # against for the offline-sync case; a mismatch here gets
                # the same StockDiscrepancy flag for the owner to reconcile.
                sale, _created = create_sale(
                    channel=Sale.Channel.JUMIA,
                    items=items,
                    payment_method=Sale.PaymentMethod.MARKETPLACE,
                    allow_oversell=True,
                    external_ref=external_ref,
                )
                messages.success(request, f'Jumia order #{sale.id} recorded.')
                return _render_list(request) if _is_htmx(request) else redirect('portal:marketplace_list')
            except ValueError as exc:
                errors.append(str(exc))

    return _render_list(request, {
        'panel_open': True,
        'form_errors': errors,
        'books': Book.objects.filter(is_active=True).order_by('title'),
    })


@login_required
def marketplace_detail(request, pk):
    sale = get_object_or_404(
        Sale.objects.prefetch_related('items__book'), pk=pk, channel=Sale.Channel.JUMIA,
    )
    return render(request, 'portal/marketplace/detail.html', {'active_nav': 'marketplace', 'sale': sale})


@login_required
def marketplace_return(request, pk):
    sale = get_object_or_404(Sale, pk=pk, channel=Sale.Channel.JUMIA)
    if request.method == 'POST':
        return_sale(sale)
        messages.success(request, f'Order #{sale.id} marked as returned — stock restored, excluded from revenue.')
    return redirect('portal:marketplace_detail', pk=pk)
