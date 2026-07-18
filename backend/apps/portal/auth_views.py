from django.contrib.auth import login, logout
from django.shortcuts import redirect, render

from apps.accounts.forms import EmailLoginForm


def login_view(request):
    if request.user.is_authenticated:
        return redirect('portal:dashboard')

    if request.method == 'POST':
        form = EmailLoginForm(request, data=request.POST)
        if form.is_valid():
            login(request, form.user)
            next_url = request.POST.get('next') or request.GET.get('next') or 'portal:dashboard'
            return redirect(next_url)
    else:
        form = EmailLoginForm(request)

    return render(request, 'portal/login.html', {'form': form, 'next': request.GET.get('next', '')})


def logout_view(request):
    logout(request)
    return redirect('portal:login')
