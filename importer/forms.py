from django import forms
from django.apps import apps
from django.contrib.gis.geos import GEOSGeometry
from django.contrib.gis.gdal import DataSource, SpatialReference

TARGET_MODELS = (
    ('common.City', 'City'),
    ('common.Neighborhood', 'Neighborhood'),
    ('common.Region', 'Region'),
    ('watersupply.Watersupply', 'ConsumptionCapita'),
    ('watersupply.Watersupply', 'TotalWaterDemand'),
    ('watersupply.Watersupply', 'SupplySecurity'),
    ('watersupply.Watersupply', 'UsersLocation'),
    ('watersupply.Watersupply', 'CoverageWaterSupply'),
    ('watersupply.Watersupply', 'MeteredResidential'),
    ('watersupply.Watersupply', 'ExtractionWater'),
    ('watersupply.Watersupply', 'ImportedWater'),
    ('watersupply.Watersupply', 'AvailableFreshWater'),
    ('watersupply.Watersupply', 'WaterTreatment'),
    ('watersupply.Watersupply', 'PipeNetwork'),
    ('watersupply.Watersupply', 'OPEX'),
    ('watersupply.Watersupply', 'AreaAffectedDrought')
)

class GeoUploadForm(forms.Form):
    file = forms.FileField(
        label='GeoJSON file',
        help_text="GeoJSON (.geojson) or Shapefile (.zip containing .shp, .dbf, .shx, .prj)",
    )
    target_model = forms.ChoiceField(choices=TARGET_MODELS)
    
    def clean_file(self):
        file = self.cleaned_data['file']
        name = file.name.lower()
        if not file.name.endswith('.geojson') or name.endswith('.json') or file.name.endswith('.zip'):
            raise forms.ValidationError("Please upload a GeoJSON or Shapefile.")
        return file


class MappingForm(forms.Form):
    pass 
    
    