from django.contrib.auth import login, logout
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
