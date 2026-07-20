from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from apps.fulfillment.forms import DeliveryPricingRuleForm, ShopLocationForm
from apps.fulfillment.models import DeliveryPricingRule, ShopLocation

from .htmx import is_htmx as _is_htmx

CONTENT_TEMPLATE = 'portal/delivery/_content.html'
PAGE_TEMPLATE = 'portal/delivery/list.html'


def _list_context():
    return {
        'active_nav': 'delivery',
        'shop_location': ShopLocation.load(),
        'location_form': ShopLocationForm(instance=ShopLocation.load()),
        'rules': DeliveryPricingRule.objects.all(),
        'panel_open': False,
        'rule_form': None,
        'editing_rule': None,
    }


def _render_list(request, extra_context=None):
    context = _list_context()
    context.update(extra_context or {})
    template = CONTENT_TEMPLATE if _is_htmx(request) else PAGE_TEMPLATE
    return render(request, template, context)


@login_required
def delivery_settings(request):
    return _render_list(request)


@login_required
def shop_location_update(request):
    if request.method == 'POST':
        form = ShopLocationForm(request.POST, instance=ShopLocation.load())
        if form.is_valid():
            form.save()
            messages.success(request, 'Shop location updated.')
            return redirect('portal:delivery_settings')
        return _render_list(request, {'location_form': form})
    return redirect('portal:delivery_settings')


@login_required
def pricing_rule_create(request):
    if request.method == 'POST':
        form = DeliveryPricingRuleForm(request.POST)
        if form.is_valid():
            form.save()
            return _render_list(request) if _is_htmx(request) else redirect('portal:delivery_settings')
    else:
        form = DeliveryPricingRuleForm(initial={'method': DeliveryPricingRule.Method.DISTANCE_BASED})
    return _render_list(request, {'panel_open': True, 'rule_form': form})


@login_required
def pricing_rule_update(request, pk):
    rule = get_object_or_404(DeliveryPricingRule, pk=pk)
    if request.method == 'POST':
        form = DeliveryPricingRuleForm(request.POST, instance=rule)
        if form.is_valid():
            form.save()
            return _render_list(request) if _is_htmx(request) else redirect('portal:delivery_settings')
    else:
        form = DeliveryPricingRuleForm(instance=rule)
    return _render_list(request, {'panel_open': True, 'rule_form': form, 'editing_rule': rule})


@login_required
def pricing_rule_toggle_active(request, pk):
    # Toggle, not delete — same reasoning as user/discount deactivation
    # elsewhere in the portal: a rule that priced a past order must stay
    # addressable (Fulfillment.pricing_rule FK), just no longer selectable
    # for new ones.
    rule = get_object_or_404(DeliveryPricingRule, pk=pk)
    if request.method == 'POST':
        rule.is_active = not rule.is_active
        rule.save(update_fields=['is_active'])
    return _render_list(request) if _is_htmx(request) else redirect('portal:delivery_settings')
