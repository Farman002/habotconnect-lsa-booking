from django.contrib import admin

from .models import Booking, LSAProfile, Parent, Payment, Skill

admin.site.register(Parent)
admin.site.register(Skill)
admin.site.register(LSAProfile)
admin.site.register(Booking)
admin.site.register(Payment)
