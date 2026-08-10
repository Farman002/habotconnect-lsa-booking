from django.urls import path

from .views import (
    MockPaymentGatewayAPIView,
    PaymentWebhookAPIView,
)


urlpatterns = [

    path(
        "mock-gateway/charge/",
        MockPaymentGatewayAPIView.as_view(),
        name="mock-gateway-charge",
    ),

    path(
        "payments/webhook/",
        PaymentWebhookAPIView.as_view(),
        name="payment-webhook",
    ),

]