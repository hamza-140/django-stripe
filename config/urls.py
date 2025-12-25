from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView
from payments.views import login_view, logout_view, register

urlpatterns = [
    path("admin/", admin.site.urls),
    
    # Authentication
    path("login/", login_view, name="login"),
    path("logout/", logout_view, name="logout"),
    path("register/", register, name="register"),
    
    # Home page
    path("", TemplateView.as_view(template_name='home.html'), name="home"),
    
    # Payments
    path("payments/", include("payments.urls")),
]
