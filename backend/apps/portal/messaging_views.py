from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.messaging.forms import SmsCampaignForm
from apps.messaging.models import SmsCampaign

from .htmx import is_htmx as _is_htmx

CONTENT_TEMPLATE = 'portal/messaging/_content.html'
PAGE_TEMPLATE = 'portal/messaging/list.html'


def _list_context():
    return {
        'active_nav': 'messaging',
        'campaigns': SmsCampaign.objects.all()[:50],
        'panel_open': False,
        'form': None,
        'editing_campaign': None,
    }


def _render_list(request, extra_context=None):
    context = _list_context()
    context.update(extra_context or {})
    template = CONTENT_TEMPLATE if _is_htmx(request) else PAGE_TEMPLATE
    return render(request, template, context)


@login_required
def campaign_list(request):
    return _render_list(request)


@login_required
def campaign_create(request):
    if request.method == 'POST':
        form = SmsCampaignForm(request.POST)
        if form.is_valid():
            form.save()
            return _render_list(request) if _is_htmx(request) else redirect('portal:campaign_list')
    else:
        form = SmsCampaignForm()
    return _render_list(request, {'panel_open': True, 'form': form})


@login_required
def campaign_update(request, pk):
    campaign = get_object_or_404(SmsCampaign, pk=pk)
    if request.method == 'POST':
        form = SmsCampaignForm(request.POST, instance=campaign)
        if form.is_valid():
            form.save()
            return _render_list(request) if _is_htmx(request) else redirect('portal:campaign_list')
    else:
        form = SmsCampaignForm(instance=campaign)
    return _render_list(request, {'panel_open': True, 'form': form, 'editing_campaign': campaign})


@login_required
def campaign_send_now(request, pk):
    """Marks the campaign SCHEDULED with scheduled_for=now. CLAUDE.md §8:
    SMS must never send inline in a request/response cycle — the cron-driven
    send_sms_campaigns command (docs/deployment.md) picks this up on its
    next run."""
    campaign = get_object_or_404(SmsCampaign, pk=pk)
    if request.method == 'POST' and campaign.status == SmsCampaign.Status.DRAFT:
        campaign.status = SmsCampaign.Status.SCHEDULED
        campaign.scheduled_for = timezone.now()
        campaign.save(update_fields=['status', 'scheduled_for'])
        messages.success(request, f'"{campaign.name}" is queued — it will send on the next scheduled run.')
    return redirect('portal:campaign_list')
