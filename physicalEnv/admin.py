from django.contrib import admin
from .models import *

class LandCoverClassesAdmin(admin.ModelAdmin):
    model = LandCoverClasses
    search_fields = ['class_name', 'description']

class SurfaceMaterialPropertiesAdmin(admin.ModelAdmin):
    model = SurfaceMaterialProperties
    search_fields = ['material_name', 'description']

# Register your models here.
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
