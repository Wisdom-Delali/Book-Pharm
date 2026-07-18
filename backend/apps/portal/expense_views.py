from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render

from apps.expenses.forms import ExpenseForm
from apps.expenses.models import Expense

from .htmx import is_htmx as _is_htmx

CONTENT_TEMPLATE = 'portal/expenses/_content.html'
PAGE_TEMPLATE = 'portal/expenses/list.html'
PAGE_SIZE = 20


def _list_context(request):
    paginator = Paginator(Expense.objects.select_related('created_by'), PAGE_SIZE)
    return {
        'active_nav': 'expenses',
        'page_obj': paginator.get_page(request.GET.get('page')),
        'panel_open': False,
        'form': None,
        'editing_expense': None,
    }


def _render_list(request, extra_context=None):
    context = _list_context(request)
    context.update(extra_context or {})
    template = CONTENT_TEMPLATE if _is_htmx(request) else PAGE_TEMPLATE
    return render(request, template, context)


@login_required
def expense_list(request):
    return render(request, PAGE_TEMPLATE, _list_context(request))


@login_required
def expense_create(request):
    if request.method == 'POST':
        form = ExpenseForm(request.POST)
        if form.is_valid():
            expense = form.save(commit=False)
            expense.created_by = request.user
            expense.save()
            return _render_list(request) if _is_htmx(request) else redirect('portal:expense_list')
    else:
        form = ExpenseForm()
    return _render_list(request, {'panel_open': True, 'form': form})


@login_required
def expense_update(request, pk):
    expense = get_object_or_404(Expense, pk=pk)
    if request.method == 'POST':
        form = ExpenseForm(request.POST, instance=expense)
        if form.is_valid():
            form.save()
            return _render_list(request) if _is_htmx(request) else redirect('portal:expense_list')
    else:
        form = ExpenseForm(instance=expense)
    return _render_list(request, {'panel_open': True, 'form': form, 'editing_expense': expense})
