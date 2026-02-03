from django.contrib import admin
from .models import *

class RegionAdmin(admin.ModelAdmin):
    model = Region
    list_display = ['regionName', 'currentPopulation', 'populationDensity', 'area_km2', ]
    search_fields = ['regionName']
    
class CityAdmin(admin.ModelAdmin):
    model = City
    list_display = ['cityName', 'currentPopulation', 'populationDensity', 'area_km2', ]
    search_fields = ['cityName']
    
class NeighborhoodAdmin(admin.ModelAdmin):
    model = Neighborhood
    list_display = ['neighborhoodName', 'currentPopulation', 'populationDensity', 'area_km2', ]
    search_fields = ['neighborhoodName']

# Register your models here.
admin.site.register(Region, RegionAdmin)
admin.site.register(City, CityAdmin)
admin.site.register(Neighborhood, NeighborhoodAdmin)
admin.site.register(ElectricityCost)