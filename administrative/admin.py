from django.contrib import admin
from .models import Province, City, Neighborhood

class ProvinceAdmin(admin.ModelAdmin):
    model = Province
    list_display = ['ProvinceName', 'currentPopulation', 'populationDensity', 'area_km2', ]
    search_fields = ['ProvinceName']

class CityAdmin(admin.ModelAdmin):
    model = City
    list_display = ['cityName', 'currentPopulation', 'populationDensity', 'area_km2', ]
    search_fields = ['cityName']

class NeighborhoodAdmin(admin.ModelAdmin):
    model = Neighborhood
    list_display = ['neighborhoodName', 'currentPopulation', 'populationDensity', 'area_km2', ]
    search_fields = ['neighborhoodName']

# Register your models here.
admin.site.register(Province, ProvinceAdmin)
admin.site.register(City, CityAdmin)
admin.site.register(Neighborhood, NeighborhoodAdmin)
