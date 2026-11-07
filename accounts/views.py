from .forms import RegistrationForm, EmailAuthenticationForm, ProfileUpdateForm
from django.views.generic import FormView
from django.contrib.auth import login
from django.contrib import messages
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.views import (
    LoginView as DjangoLoginView, 
    LogoutView as DjangoLogoutView, 
    PasswordChangeView as DjangoPasswordChangeView,
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

class ProfileUpdateView(LoginRequiredMixin, FormView):
    template_name = 'accounts/profile.html'
    form_class = ProfileUpdateForm  # ここで使用するフォームを指定
    success_url = reverse_lazy('accounts:profile')  # 更新後のリダイレクト先を指定

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['instance'] = self.request.user  # 現在のユーザーをフォームに渡す
        return kwargs

    def form_valid(self, form):
        form.save()  # フォームの保存処理を実行
        messages.success(self.request, _('プロフィールが更新されました'))
        return super().form_valid(form)

class PasswordChangeView(LoginRequiredMixin, DjangoPasswordChangeView):
    template_name = 'accounts/password_change.html'
    success_url = reverse_lazy('accounts:profile')

    def form_valid(self, form):
        messages.success(self.request, _('パスワードが変更されました'))
        return super().form_valid(form)