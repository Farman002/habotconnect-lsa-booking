from django.urls import path

from .views import BookingCreateAPIView, LSASearchAPIView

urlpatterns = [
    path("bookings/", BookingCreateAPIView.as_view(), name="booking-create"),
    path("lsas/search/", LSASearchAPIView.as_view(), name="lsa-search"),
]
