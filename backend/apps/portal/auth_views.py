from django.contrib import messages
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.shortcuts import redirect, render

from apps.accounts.forms import EmailLoginForm
from apps.accounts.models import User


def login_view(request):
    if request.user.is_authenticated:
        return redirect('portal:dashboard')

    if request.method == 'POST':
        form = EmailLoginForm(request, data=request.POST)
        if form.is_valid():
            # Attendant accounts are desktop-POS-only (User.Role docstring) —
            # checked here, not in EmailLoginForm itself, since that form is
            # a generic "authenticate by email/password" utility and this is
            # a portal-specific access policy, not a login-correctness one.
            if form.user.role == User.Role.ATTENDANT:
                form.add_error(None, 'Attendant accounts sign in through the desktop POS, not the portal.')
            else:
                login(request, form.user)
                next_url = request.POST.get('next') or request.GET.get('next') or 'portal:dashboard'
                return redirect(next_url)
    else:
        form = EmailLoginForm(request)

    return render(request, 'portal/login.html', {'form': form, 'next': request.GET.get('next', '')})


def logout_view(request):
    logout(request)
    return redirect('portal:login')


@login_required
def change_password(request):
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            # Changing the password rotates Django's session auth hash —
            # without this the user is silently logged out by their own
            # successful password change, which reads as a bug.
            update_session_auth_hash(request, user)
            messages.success(request, 'Password updated.')
            return redirect('portal:dashboard')
    else:
        form = PasswordChangeForm(request.user)
    return render(request, 'portal/change_password.html', {'active_nav': '', 'form': form})
