from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render

from apps.customers.forms import LoyaltyProgramForm
from apps.customers.models import Customer, LoyaltyProgram
from apps.sales.models import Sale

from .htmx import is_htmx as _is_htmx

CONTENT_TEMPLATE = 'portal/customers/_content.html'
PAGE_TEMPLATE = 'portal/customers/list.html'
PAGE_SIZE = 20


def _list_context(request):
    query = request.GET.get('q', '').strip()
    qs = Customer.objects.all()
    if query:
        qs = qs.filter(Q(full_name__icontains=query) | Q(phone__icontains=query) | Q(email__icontains=query))
    # Lifetime value only counts PAID sales — a pending/abandoned online
    # checkout isn't really "an order" from the owner's point of view.
    qs = qs.annotate(
        order_count=Count('sales', filter=Q(sales__payment_status=Sale.PaymentStatus.PAID)),
        total_spent=Sum('sales__total', filter=Q(sales__payment_status=Sale.PaymentStatus.PAID)),
    ).order_by('full_name', 'phone')

    paginator = Paginator(qs, PAGE_SIZE)
    return {
        'active_nav': 'customers',
        'page_obj': paginator.get_page(request.GET.get('page')),
        'query': query,
    }


def _render_list(request, extra_context=None):
    context = _list_context(request)
    context.update(extra_context or {})
    template = CONTENT_TEMPLATE if _is_htmx(request) else PAGE_TEMPLATE
    return render(request, template, context)


@login_required
def customer_list(request):
    return _render_list(request)


@login_required
def customer_detail(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    sales = customer.sales.select_related('fulfillment').prefetch_related('items').order_by('-created_at')
    loyalty_transactions = customer.loyalty_transactions.select_related('sale').order_by('-created_at')
    sales_page = Paginator(sales, PAGE_SIZE).get_page(request.GET.get('page'))
    loyalty_page = Paginator(loyalty_transactions, PAGE_SIZE).get_page(request.GET.get('loyalty_page'))
    return render(request, 'portal/customers/detail.html', {
        'active_nav': 'customers',
        'customer': customer,
        'sales_page': sales_page,
        'loyalty_page': loyalty_page,
    })


@login_required
def customer_toggle_opt_out(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    if request.method == 'POST':
        customer.sms_opt_out = not customer.sms_opt_out
        customer.save(update_fields=['sms_opt_out'])
        messages.success(
            request,
            f'{customer} {"opted out of" if customer.sms_opt_out else "opted back into"} SMS.',
        )
    return redirect('portal:customer_detail', pk=pk)


@login_required
def loyalty_settings(request):
    program = LoyaltyProgram.current() or LoyaltyProgram()
    if request.method == 'POST':
        form = LoyaltyProgramForm(request.POST, instance=program)
        if form.is_valid():
            form.save()
            messages.success(request, 'Loyalty program settings updated.')
            return redirect('portal:loyalty_settings')
    else:
        form = LoyaltyProgramForm(instance=program)
    return render(request, 'portal/customers/loyalty_settings.html', {
        'active_nav': 'customers',
        'form': form,
    })
