from django.contrib import admin
from .models import *
# Register your models here.
admin.site.register(Building)
admin.site.register(Street)
admin.site.register(Park)
admin.site.register(ZoningArea)
admin.site.register(Facility)
admin.site.register(Property)