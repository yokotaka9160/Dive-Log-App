from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = 'divelogs'

urlpatterns = [
    path("", views.landing, name="landing"),
    path("logs/", views.LogListView.as_view(), name="log_list"),
    path("logs/new/", views.LogCreateView.as_view(), name="log_create"),
    path("logs/<int:pk>/", views.LogDetailView.as_view(), name="log_detail"),
    path("logs/<int:pk>/edit/", views.LogUpdateView.as_view(), name="log_update"),
    path("logs/<int:pk>/delete/", views.LogDeleteView.as_view(), name="log_delete"),
    path("dashboard/", views.DashboardView.as_view(), name="dashboard"),
    #path("logs/<int:pk>/favorite/", views.toggle_favorite, name="toggle_favorite"),
    # 認証
    # path("signup/", views.signup, name="register"),
    # path(
    #     "login/",
    #     auth_views.LoginView.as_view(template_name="accounts/login.html"),
    #     name="login",
    # ),
    # path("logout/", auth_views.LogoutView.as_view(), name="logout"),
]