from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.sales.models import StockDiscrepancy


@login_required
def reconciliation_list(request):
    return render(request, 'portal/reconciliation/list.html', {
        'active_nav': 'reconciliation',
        'unresolved': StockDiscrepancy.objects.filter(resolved=False).select_related(
            'book', 'sale_item__sale'
        ),
        'resolved': StockDiscrepancy.objects.filter(resolved=True).select_related(
            'book', 'sale_item__sale', 'resolved_by'
        )[:20],
    })


@login_required
def reconciliation_resolve(request, pk):
    discrepancy = get_object_or_404(StockDiscrepancy, pk=pk)
    if request.method == 'POST':
        discrepancy.resolved = True
        discrepancy.resolved_by = request.user
        discrepancy.resolved_at = timezone.now()
        discrepancy.resolution_notes = request.POST.get('notes', '')
        discrepancy.save()
    return redirect('portal:reconciliation_list')
