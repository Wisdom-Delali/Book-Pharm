from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from apps.sales.forms import DiscountRuleForm
from apps.sales.models import DiscountRule

from .htmx import is_htmx as _is_htmx

CONTENT_TEMPLATE = 'portal/discounts/_content.html'
PAGE_TEMPLATE = 'portal/discounts/list.html'


def _list_context():
    return {
        'active_nav': 'discounts',
        'rules': DiscountRule.objects.select_related('category', 'book').all(),
        'panel_open': False,
        'form': None,
        'editing_rule': None,
    }


def _render_list(request, extra_context=None):
    context = _list_context()
    context.update(extra_context or {})
    template = CONTENT_TEMPLATE if _is_htmx(request) else PAGE_TEMPLATE
    return render(request, template, context)


@login_required
def discount_list(request):
    return _render_list(request)


@login_required
def discount_create(request):
    if request.method == 'POST':
        form = DiscountRuleForm(request.POST)
        if form.is_valid():
            form.save()
            return _render_list(request) if _is_htmx(request) else redirect('portal:discount_list')
    else:
        form = DiscountRuleForm()
    return _render_list(request, {'panel_open': True, 'form': form})


@login_required
def discount_update(request, pk):
    rule = get_object_or_404(DiscountRule, pk=pk)
    if request.method == 'POST':
        form = DiscountRuleForm(request.POST, instance=rule)
        if form.is_valid():
            form.save()
            return _render_list(request) if _is_htmx(request) else redirect('portal:discount_list')
    else:
        form = DiscountRuleForm(instance=rule)
    return _render_list(request, {'panel_open': True, 'form': form, 'editing_rule': rule})
