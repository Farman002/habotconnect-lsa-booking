from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path


def home(request):

    return JsonResponse(
        {
            "project": "HabotConnect LSA Booking API",
            "status": "running",
            "version": "v1",
            "message": "Backend API is running successfully",
        }
    )


urlpatterns = [

    path(
        "",
        home,
        name="home",
    ),

    path(
        "admin/",
        admin.site.urls,
    ),

    path(
        "api/v1/",
        include("booking.urls"),
    ),

    path(
        "api/v1/",
        include("payments.urls"),
    ),

]