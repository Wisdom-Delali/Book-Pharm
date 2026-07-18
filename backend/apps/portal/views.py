import json
from datetime import timedelta
from datetime import timezone as dt_timezone
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import F, Q, Sum
from django.db.models.functions import TruncDate
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.catalog.forms import BookForm, StockAdjustmentForm
from apps.catalog.models import Book, Category, StockAdjustment
from apps.reports.utils import range_bounds_utc
from apps.sales.models import Sale, SaleItem, StockDiscrepancy

from .htmx import is_htmx as _is_htmx

CONTENT_TEMPLATE = 'portal/catalog/_catalog_content.html'
PAGE_TEMPLATE = 'portal/catalog/book_list.html'
PAGE_SIZE = 20


def _filtered_books(request):
    qs = Book.objects.select_related('category').all()
    query = request.GET.get('q', '').strip()
    if query:
        qs = qs.filter(
            Q(title__icontains=query)
            | Q(author__icontains=query)
            | Q(isbn__icontains=query)
            | Q(internal_code__icontains=query)
        )
    category_id = request.GET.get('category', '').strip()
    if category_id:
        qs = qs.filter(category_id=category_id)
    if request.GET.get('low_stock') == '1':
        qs = qs.low_stock()
    return qs.order_by('title')


def _list_context(request):
    paginator = Paginator(_filtered_books(request), PAGE_SIZE)
    return {
        'active_nav': 'catalog',
        'page_obj': paginator.get_page(request.GET.get('page')),
        'categories': Category.objects.all(),
        'query': request.GET.get('q', ''),
        'selected_category': request.GET.get('category', ''),
        'low_stock_only': request.GET.get('low_stock') == '1',
        'panel_open': False,
        'book_form': None,
        'editing_book': None,
        'adjustment_form': None,
        'adjusting_book': None,
    }


def _render_list(request, extra_context=None):
    """HTMX requests get just the swappable fragment; anything else
    (direct navigation, JS disabled) gets the full page."""
    context = _list_context(request)
    context.update(extra_context or {})
    template = CONTENT_TEMPLATE if _is_htmx(request) else PAGE_TEMPLATE
    return render(request, template, context)


@login_required
def dashboard(request):
    today = timezone.localdate()
    week_start = today - timedelta(days=today.weekday())
    month_start = today.replace(day=1)
    completed = Sale.objects.filter(status=Sale.Status.COMPLETED)

    # range_bounds_utc, not created_at__date=/__gte= — see its docstring:
    # __date lookups need MySQL's CONVERT_TZ, which needs timezone tables
    # this box (and possibly the cPanel host) doesn't have loaded.
    today_start, today_end = range_bounds_utc(today, today)
    today_sales = completed.filter(created_at__gte=today_start, created_at__lt=today_end).aggregate(
        t=Sum('total')
    )['t'] or Decimal('0')

    week_start_dt, week_end_dt = range_bounds_utc(week_start, today)
    week_orders = completed.filter(created_at__gte=week_start_dt, created_at__lt=week_end_dt).count()

    month_start_dt, month_end_dt = range_bounds_utc(month_start, today)
    month_totals = SaleItem.objects.filter(
        sale__status=Sale.Status.COMPLETED,
        sale__created_at__gte=month_start_dt,
        sale__created_at__lt=month_end_dt,
    ).aggregate(
        revenue=Sum(F('unit_price') * F('qty') - F('line_discount')),
        cost=Sum(F('unit_cost_price') * F('qty')),
    )
    revenue = month_totals['revenue'] or Decimal('0')
    cost = month_totals['cost'] or Decimal('0')
    profit_margin_pct = ((revenue - cost) / revenue * 100) if revenue else Decimal('0')

    trend_start = today - timedelta(days=6)
    trend_start_dt, trend_end_dt = range_bounds_utc(trend_start, today)
    trend_rows = (
        completed.filter(created_at__gte=trend_start_dt, created_at__lt=trend_end_dt)
        .annotate(day=TruncDate('created_at', tzinfo=dt_timezone.utc))
        .values('day')
        .annotate(total=Sum('total'))
    )
    trend_map = {row['day']: float(row['total'] or 0) for row in trend_rows}
    chart_labels, chart_values = [], []
    d = trend_start
    while d <= today:
        chart_labels.append(d.strftime('%a'))
        chart_values.append(trend_map.get(d, 0.0))
        d += timedelta(days=1)

    return render(request, 'portal/dashboard.html', {
        'active_nav': 'dashboard',
        'today_sales': today_sales,
        'week_orders': week_orders,
        'profit_margin_pct': profit_margin_pct,
        'low_stock_books': Book.objects.low_stock().select_related('category')[:10],
        'low_stock_count': Book.objects.low_stock().count(),
        'discrepancy_count': StockDiscrepancy.objects.filter(resolved=False).count(),
        'chart_labels': json.dumps(chart_labels),
        'chart_values': json.dumps(chart_values),
    })


@login_required
def book_list(request):
    return render(request, PAGE_TEMPLATE, _list_context(request))


@login_required
def book_create(request):
    if request.method == 'POST':
        form = BookForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return _render_list(request) if _is_htmx(request) else redirect('portal:book_list')
    else:
        form = BookForm()
    return _render_list(request, {'panel_open': True, 'book_form': form})


@login_required
def book_update(request, pk):
    book = get_object_or_404(Book, pk=pk)
    if request.method == 'POST':
        form = BookForm(request.POST, request.FILES, instance=book)
        if form.is_valid():
            form.save()
            return _render_list(request) if _is_htmx(request) else redirect('portal:book_list')
    else:
        form = BookForm(instance=book)
    return _render_list(request, {'panel_open': True, 'book_form': form, 'editing_book': book})


@login_required
def stock_adjust(request, pk):
    book = get_object_or_404(Book, pk=pk)
    if request.method == 'POST':
        form = StockAdjustmentForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                book.stock_qty += form.cleaned_data['delta']
                book.save(update_fields=['stock_qty', 'updated_at'])
                StockAdjustment.objects.create(
                    book=book,
                    delta=form.cleaned_data['delta'],
                    resulting_qty=book.stock_qty,
                    reason=form.cleaned_data['reason'],
                    notes=form.cleaned_data['notes'],
                    adjusted_by=request.user,
                )
            return _render_list(request) if _is_htmx(request) else redirect('portal:book_list')
    else:
        form = StockAdjustmentForm()
    return _render_list(request, {'panel_open': True, 'adjustment_form': form, 'adjusting_book': book})
