from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from apps.accounts.forms import UserCreateForm
from apps.accounts.models import User

from .htmx import is_htmx as _is_htmx

CONTENT_TEMPLATE = 'portal/users/_content.html'
PAGE_TEMPLATE = 'portal/users/list.html'


def _list_context():
    return {
        'active_nav': 'users',
        # is_superuser=False isn't just a display filter — it's the actual
        # access boundary. A dev/admin account created via createsuperuser
        # must never be listable, editable, or revocable from here, even by
        # a crafted URL (see the same filter in user_toggle_active below).
        'users': User.objects.filter(is_superuser=False).order_by('full_name', 'email'),
        'panel_open': False,
        'form': None,
    }


def _render_list(request, extra_context=None):
    context = _list_context()
    context.update(extra_context or {})
    template = CONTENT_TEMPLATE if _is_htmx(request) else PAGE_TEMPLATE
    return render(request, template, context)


@login_required
def user_list(request):
    return _render_list(request)


@login_required
def user_create(request):
    if request.method == 'POST':
        form = UserCreateForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, f'{user.email} can now sign in as {user.get_role_display()}.')
            return _render_list(request) if _is_htmx(request) else redirect('portal:user_list')
    else:
        form = UserCreateForm()
    return _render_list(request, {'panel_open': True, 'form': form})


@login_required
def user_toggle_active(request, pk):
    user = get_object_or_404(User, pk=pk, is_superuser=False)
    if request.method == 'POST':
        if user.pk == request.user.pk:
            messages.error(request, "You can't revoke your own access.")
        else:
            user.is_active = not user.is_active
            user.save(update_fields=['is_active'])
            messages.success(request, f'{user.email} access {"restored" if user.is_active else "revoked"}.')
    return redirect('portal:user_list')
