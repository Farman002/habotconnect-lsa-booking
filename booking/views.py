import logging

from django.db import IntegrityError
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Booking
from .selectors import search_available_lsas
from .serializers import BookingCreateSerializer, BookingResponseSerializer, LSASearchSerializer
from .services import BookingService

logger = logging.getLogger(__name__)


class BookingCreateAPIView(APIView):
    def post(self, request):
        serializer = BookingCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            booking = serializer.save()
            booking = BookingService.process_payment(booking.id)
        except IntegrityError:
            logger.exception("Booking creation integrity error")
            return Response(
                {"detail": "Booking could not be created because the request conflicts with existing data."},
                status=status.HTTP_409_CONFLICT,
            )

        booking = Booking.objects.select_related("parent", "lsa").prefetch_related("payment").get(pk=booking.pk)
        response_status = status.HTTP_201_CREATED if booking.status == Booking.Status.CONFIRMED else status.HTTP_402_PAYMENT_REQUIRED
        return Response(BookingResponseSerializer(booking).data, status=response_status)


class LSASearchAPIView(APIView):
    def get(self, request):
        raw_skills = request.query_params.get("skills", "")
        skills = [value for value in raw_skills.split(",") if value.strip()]
        qs = search_available_lsas(
            skills=skills,
            session_date=request.query_params.get("session_date"),
            start_time=request.query_params.get("start_time"),
            end_time=request.query_params.get("end_time"),
        )
        return Response({"count": qs.count(), "results": LSASearchSerializer(qs, many=True).data})
