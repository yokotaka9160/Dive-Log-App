from .forms import RegistrationForm, EmailAuthenticationForm
from django.views.generic import FormView
from django.contrib.auth import login
from django.contrib import messages
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.views import (
    LoginView as DjangoLoginView, 
    LogoutView as DjangoLogoutView, 
)
# Create your views here.
class RegisterView(FormView):
    template_name = 'accounts/register.html'
    form_class = RegistrationForm
    success_url = reverse_lazy('divelogs:landing')

    def form_valid(self, form):
        user = form.save()
        login(self.request, user)
        messages.success(self.request, _('登録が完了しました'))
        return super().form_valid(form)

class LoginView(DjangoLoginView):
    template_name = 'accounts/login.html'
    authentication_form = EmailAuthenticationForm
    redirect_authenticated_user = True

    def form_valid(self, form):
        messages.success(self.request, _('ログインしました'))
        return super().form_valid(form)

class LogoutView(DjangoLogoutView):
    next_page = reverse_lazy('accounts:login')

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            messages.success(request, _('ログアウトしました'))
        return super().dispatch(request, *args, **kwargs)
