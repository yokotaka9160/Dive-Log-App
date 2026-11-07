from django.urls import path

from .views import LoginView, LogoutView, RegisterView, ProfileUpdateView, PasswordChangeView
app_name = 'accounts'

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('profile/', ProfileUpdateView.as_view(), name='profile'),  # ユーザープロフィールページへのURLパターンを追加
    path('password_change/', PasswordChangeView.as_view(), name='password_change'),
    ]
