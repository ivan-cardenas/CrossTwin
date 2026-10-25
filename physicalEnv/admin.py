from django.contrib import admin
from .models import *

class LandCoverClassesAdmin(admin.ModelAdmin):
    model = LandCoverClasses
    search_fields = ['class_name', 'description']

class HILUCSLandUseAdmin(admin.ModelAdmin):
    model = HILUCSLandUse
    list_display = ['code', 'label']
    search_fields = ['code', 'label', 'description']

class SoilTypeAdmin(admin.ModelAdmin):
    model = SoilType
    list_display = ['code', 'name', 'soilGroup', 'infiltrationMin_mm_h', 'infiltrationMax_mm_h']
    list_filter = ['soilGroup']
    search_fields = ['code', 'name']

class SurfaceMaterialPropertiesAdmin(admin.ModelAdmin):
    model = SurfaceMaterialProperties
    search_fields = ['material_name', 'description']

# Register your models here.
admin.site.register(LandCoverClasses, LandCoverClassesAdmin)
admin.site.register(HILUCSLandUse, HILUCSLandUseAdmin)
admin.site.register(SoilType, SoilTypeAdmin)
admin.site.register(SoilArea)
admin.site.register(GroundwaterDepth)
admin.site.register(SurfaceMaterialProperties)
admin.site.register(WallMaterialProperties)
admin.site.register(LandCoverVector)
admin.site.register(LandCoverRaster)
admin.site.register(LandCoverWMS)
admin.site.register(DigitalElevationModel)
admin.site.register(DigitalElevationModelWMS)
admin.site.register(DigitalSurfaceModel)
admin.site.register(DigitalSurfaceModelWMS)
