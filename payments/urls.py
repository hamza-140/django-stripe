from django.urls import path
from .views import (
    create_checkout_session, 
    payment_success, 
    payment_cancel, 
    stripe_webhook,
    verify_payment,
    dashboard,
)

urlpatterns = [
    # Authentication routes
    path("dashboard/", dashboard, name="dashboard"),
    
    # Payment routes
    path("create-checkout-session/", create_checkout_session, name="create-checkout-session"),
    path("success/", payment_success, name="payment_success"),
    path("cancel/", payment_cancel, name="payment_cancel"),
    path("verify/", verify_payment, name="verify_payment"),
    
    # Webhook
    path("webhook/", stripe_webhook, name="stripe_webhook"),
]
