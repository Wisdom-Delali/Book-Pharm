from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from apps.catalog.forms import BookForm, StockAdjustmentForm
from apps.catalog.models import Book, Category, StockAdjustment
from apps.sales.models import StockDiscrepancy

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
    return render(request, 'portal/dashboard.html', {
        'active_nav': 'dashboard',
        'low_stock_books': Book.objects.low_stock().select_related('category')[:10],
        'low_stock_count': Book.objects.low_stock().count(),
        'discrepancy_count': StockDiscrepancy.objects.filter(resolved=False).count(),
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
