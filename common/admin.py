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

class LandCoverClassesAdmin(admin.ModelAdmin):
    model = LandCoverClasses
    search_fields = ['class_name', 'description']
    
class SurfaceMaterialPropertiesAdmin(admin.ModelAdmin):
    model = SurfaceMaterialProperties
    search_fields = ['material_name', 'description']

# Register your models here.
admin.site.register(Region, RegionAdmin)
admin.site.register(City, CityAdmin)
admin.site.register(Neighborhood, NeighborhoodAdmin)
admin.site.register(LandCoverClasses, LandCoverClassesAdmin)
admin.site.register(SurfaceMaterialProperties)
admin.site.register(WallMaterialProperties)
admin.site.register(LandCoverVector)
admin.site.register(LandCoverRaster)
admin.site.register(LandCoverWMS)
admin.site.register(DigitalElevationModel)
admin.site.register(DigitalElevationModelWMS)
admin.site.register(DigitalSurfaceModel)
admin.site.register(DigitalSurfaceModelWMS)