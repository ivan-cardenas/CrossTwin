from django.contrib import admin
from .models import *


class WMSLayerAdmin(admin.ModelAdmin):
    list_display = ['name', 'url', 'layers_param', 'is_active']
    search_fields = ('name', 'layers_param')



admin.site.register(WMSLayer)
admin.site.register(ConsumptionCapita)
admin.site.register(TotalWaterDemand)
admin.site.register(SupplySecurity)
admin.site.register(PipeNetwork)
admin.site.register(UsersLocation)
admin.site.register(MeteredResidential)
admin.site.register(AvailableFreshWater)
admin.site.register(ExtractionWater)
admin.site.register(ImportedWater)
admin.site.register(WaterTreatment)
admin.site.register(CoverageWaterSupply)
admin.site.register(NonRevenueWater)

