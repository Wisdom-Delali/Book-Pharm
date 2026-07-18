import json
from datetime import timezone as dt_timezone
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Count, F, Sum
from django.db.models.functions import TruncDate, TruncMonth, TruncWeek
from django.shortcuts import render

from apps.catalog.models import Book
from apps.expenses.models import Expense
from apps.sales.models import Sale, SaleItem

from .utils import csv_response, parse_date_range, range_bounds_utc

# tzinfo=utc forces these to truncate on UTC boundaries directly rather than
# converting first (which needs MySQL's CONVERT_TZ / timezone tables — see
# range_bounds_utc's docstring). Correct, not just convenient: Africa/Accra
# is UTC+0 with no DST, so UTC boundaries and local-calendar boundaries are
# the same boundaries.
TRUNC_FUNCS = {'day': TruncDate, 'week': TruncWeek, 'month': TruncMonth}


def _base_context(start, end, granularity, tab):
    return {
        'active_nav': 'reports', 'report_tab': tab,
        'start': start, 'end': end, 'granularity': granularity,
    }


@login_required
def sales_report(request):
    start, end, granularity = parse_date_range(request)
    start_dt, end_dt = range_bounds_utc(start, end)
    channel = request.GET.get('channel', '').strip()

    # Unfiltered by channel — this is the "segmented by channel" breakdown
    # (ROADMAP Phase 7), always shown regardless of which channel (if any)
    # the period table below is scoped to.
    base_qs = Sale.objects.filter(status=Sale.Status.COMPLETED, created_at__gte=start_dt, created_at__lt=end_dt)
    channel_labels = dict(Sale.Channel.choices)
    by_channel = list(
        base_qs.values('channel').annotate(total=Sum('total'), sale_count=Count('id')).order_by('channel')
    )
    for row in by_channel:
        row['channel_label'] = channel_labels.get(row['channel'], row['channel'])

    qs = base_qs.filter(channel=channel) if channel else base_qs
    trunc = TRUNC_FUNCS[granularity]
    rows = list(
        qs.annotate(period=trunc('created_at', tzinfo=dt_timezone.utc))
        .values('period')
        .annotate(total=Sum('total'), subtotal=Sum('subtotal'), discount=Sum('discount_amount'), sale_count=Count('id'))
        .order_by('period')
    )
    totals = qs.aggregate(total=Sum('total'), subtotal=Sum('subtotal'), discount=Sum('discount_amount'), sale_count=Count('id'))

    if request.GET.get('format') == 'csv':
        return csv_response(
            'sales_report.csv',
            ['Period', 'Sales', 'Subtotal', 'Discount', 'Total'],
            [[r['period'], r['sale_count'], r['subtotal'], r['discount'], r['total']] for r in rows],
        )

    context = _base_context(start, end, granularity, 'sales')
    context.update({
        'rows': rows,
        'totals': totals,
        'by_channel': by_channel,
        'selected_channel': channel,
        'channel_choices': Sale.Channel.choices,
        'chart_labels': json.dumps([str(r['period']) for r in rows]),
        'chart_values': json.dumps([float(r['total'] or 0) for r in rows]),
    })
    return render(request, 'portal/reports/sales.html', context)


@login_required
def profit_report(request):
    start, end, granularity = parse_date_range(request)
    start_dt, end_dt = range_bounds_utc(start, end)
    qs = SaleItem.objects.filter(
        sale__status=Sale.Status.COMPLETED,
        sale__created_at__gte=start_dt,
        sale__created_at__lt=end_dt,
    )
    rows = list(
        qs.values('book__id', 'book__title')
        .annotate(
            qty_sold=Sum('qty'),
            revenue=Sum(F('unit_price') * F('qty') - F('line_discount')),
            cost=Sum(F('unit_cost_price') * F('qty')),
        )
        .annotate(profit=F('revenue') - F('cost'))
        .order_by('-profit')
    )
    for r in rows:
        r['margin_pct'] = (r['profit'] / r['revenue'] * 100) if r['revenue'] else Decimal('0')
    totals = {
        'qty_sold': sum(r['qty_sold'] for r in rows),
        'revenue': sum((r['revenue'] for r in rows), Decimal('0')),
        'cost': sum((r['cost'] for r in rows), Decimal('0')),
        'profit': sum((r['profit'] for r in rows), Decimal('0')),
    }

    if request.GET.get('format') == 'csv':
        return csv_response(
            'profit_margin_report.csv',
            ['Book', 'Qty Sold', 'Revenue', 'Cost', 'Profit', 'Margin %'],
            [[r['book__title'], r['qty_sold'], r['revenue'], r['cost'], r['profit'], f"{r['margin_pct']:.1f}"] for r in rows],
        )

    context = _base_context(start, end, granularity, 'profit')
    context.update({'rows': rows, 'totals': totals})
    return render(request, 'portal/reports/profit.html', context)


@login_required
def stock_report(request):
    books = Book.objects.select_related('category').annotate(
        cost_value=F('stock_qty') * F('cost_price'),
        retail_value=F('stock_qty') * F('selling_price'),
    ).order_by('title')
    totals = books.aggregate(
        cost_value=Sum(F('stock_qty') * F('cost_price')),
        retail_value=Sum(F('stock_qty') * F('selling_price')),
    )
    low_stock_count = books.low_stock().count()
    out_of_stock_count = books.filter(stock_qty__lte=0).count()

    if request.GET.get('format') == 'csv':
        return csv_response(
            'stock_levels_report.csv',
            ['Book', 'ISBN/Code', 'Category', 'Stock Qty', 'Cost Value', 'Retail Value'],
            [
                [b.title, b.isbn or b.internal_code, b.category.name, b.stock_qty,
                 b.stock_qty * b.cost_price, b.stock_qty * b.selling_price]
                for b in books
            ],
        )

    context = {
        'active_nav': 'reports', 'report_tab': 'stock',
        'books': books, 'totals': totals,
        'low_stock_count': low_stock_count, 'out_of_stock_count': out_of_stock_count,
        'total_books': books.count(),
    }
    return render(request, 'portal/reports/stock.html', context)


@login_required
def expense_report(request):
    start, end, granularity = parse_date_range(request)
    qs = Expense.objects.filter(date__gte=start, date__lte=end)
    business_total = qs.filter(is_personal_withdrawal=False).aggregate(t=Sum('amount'))['t'] or Decimal('0')
    personal_total = qs.filter(is_personal_withdrawal=True).aggregate(t=Sum('amount'))['t'] or Decimal('0')
    by_category = list(
        qs.filter(is_personal_withdrawal=False)
        .values('category')
        .annotate(total=Sum('amount'))
        .order_by('-total')
    )
    category_labels = dict(Expense.Category.choices)
    for row in by_category:
        row['category_label'] = category_labels.get(row['category'], row['category'])

    if request.GET.get('format') == 'csv':
        return csv_response(
            'expense_report.csv',
            ['Date', 'Category', 'Amount', 'Type', 'Notes'],
            [
                [e.date, e.get_category_display(), e.amount, 'Personal' if e.is_personal_withdrawal else 'Business', e.notes]
                for e in qs
            ],
        )

    context = _base_context(start, end, granularity, 'expenses')
    context.update({
        'business_total': business_total,
        'personal_total': personal_total,
        'by_category': by_category,
    })
    return render(request, 'portal/reports/expenses.html', context)
