from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.sales.models import StockDiscrepancy

PAGE_SIZE = 20


@login_required
def reconciliation_list(request):
    # unresolved is deliberately not paginated — it's an action list (same
    # reasoning as low-stock alerts elsewhere), not a browsable history;
    # paging it risks an item silently sitting unseen on page 2.
    resolved_qs = StockDiscrepancy.objects.filter(resolved=True).select_related(
        'book', 'sale_item__sale', 'resolved_by'
    )
    paginator = Paginator(resolved_qs, PAGE_SIZE)
    return render(request, 'portal/reconciliation/list.html', {
        'active_nav': 'reconciliation',
        'unresolved': StockDiscrepancy.objects.filter(resolved=False).select_related(
            'book', 'sale_item__sale'
        ),
        'page_obj': paginator.get_page(request.GET.get('page')),
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
