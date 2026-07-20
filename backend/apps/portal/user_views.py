from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render

from apps.accounts.forms import AdminResetPasswordForm, UserCreateForm
from apps.accounts.models import User

from .htmx import is_htmx as _is_htmx

CONTENT_TEMPLATE = 'portal/users/_content.html'
PAGE_TEMPLATE = 'portal/users/list.html'
PAGE_SIZE = 20


def _list_context(request):
    # is_superuser=False isn't just a display filter — it's the actual
    # access boundary. A dev/admin account created via createsuperuser must
    # never be listable, editable, or revocable from here, even by a
    # crafted URL (see the same filter in user_toggle_active below).
    qs = User.objects.filter(is_superuser=False).order_by('full_name', 'email')
    paginator = Paginator(qs, PAGE_SIZE)
    return {
        'active_nav': 'users',
        'page_obj': paginator.get_page(request.GET.get('page')),
        'panel_open': False,
        'form': None,
        'reset_form': None,
        'resetting_user': None,
    }


def _render_list(request, extra_context=None):
    context = _list_context(request)
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


@login_required
def user_reset_password(request, pk):
    # Attendant only — "admin can reset attendant password" was the actual
    # ask (owner, 2026-07-20). Owner-to-owner resets are a different,
    # bigger permission question (which owner is trusted to do that to
    # another?) that wasn't part of this request, so it isn't built here.
    user = get_object_or_404(User, pk=pk, is_superuser=False, role=User.Role.ATTENDANT)
    if request.method == 'POST':
        form = AdminResetPasswordForm(request.POST)
        if form.is_valid():
            user.set_password(form.cleaned_data['password1'])
            user.save(update_fields=['password'])
            messages.success(request, f"{user.email}'s password has been reset.")
            return _render_list(request) if _is_htmx(request) else redirect('portal:user_list')
    else:
        form = AdminResetPasswordForm()
    return _render_list(request, {'panel_open': True, 'reset_form': form, 'resetting_user': user})
