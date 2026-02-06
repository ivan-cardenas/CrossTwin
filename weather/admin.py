from django.contrib import admin

from weather.models import *

# Register your models here.
admin.site.register(WeatherStation)
admin.site.register(Meteorology)
admin.site.register(PrecipitationRaster)
admin.site.register(TemperatureRaster)
admin.site.register(WindSpeedRaster)
admin.site.register(HumidityRaster)
