from django import forms
from django.apps import apps
from django.contrib.gis.geos import GEOSGeometry
from django.contrib.gis.gdal import DataSource, SpatialReference


# FIXED: Correct model references (app_label.ModelName format)
TARGET_MODELS = (
    ('common.City', 'City'),
    ('common.Neighborhood', 'Neighborhood'),
    ('common.Region', 'Region'),
    ('watersupply.ConsumptionCapita', 'ConsumptionCapita'),
    ('watersupply.TotalWaterDemand', 'TotalWaterDemand'),
    ('watersupply.SupplySecurity', 'SupplySecurity'),
    ('watersupply.UsersLocation', 'UsersLocation'),
    ('watersupply.CoverageWaterSupply', 'CoverageWaterSupply'),
    ('watersupply.MeteredResidential', 'MeteredResidential'),
    ('watersupply.ExtractionWater', 'ExtractionWater'),
    ('watersupply.ImportedWater', 'ImportedWater'),
    ('watersupply.AvailableFreshWater', 'AvailableFreshWater'),
    ('watersupply.WaterTreatment', 'WaterTreatment'),
    ('watersupply.PipeNetwork', 'PipeNetwork'),
    ('watersupply.OPEX', 'OPEX'),
    ('watersupply.AreaAffectedDrought', 'AreaAffectedDrought'),
)


class GeoUploadForm(forms.Form):
    """Form for uploading geodata files (GeoJSON or Shapefile)."""
    
    file = forms.FileField(
        label='GeoJSON or Shapefile',
        help_text="GeoJSON (.geojson, .json) or Shapefile (.zip containing .shp, .dbf, .shx, .prj)",
        widget=forms.FileInput(attrs={
            'accept': '.geojson,.json,.zip,.shp',
            'class': 'file-input',
        })
    )
    
    target_model = forms.ChoiceField(
        choices=TARGET_MODELS,
        label='Target Model',
        help_text="Select the database model to import data into",
        widget=forms.Select(attrs={
            'class': 'select-input',
        })
    )
    
    source_crs = forms.IntegerField(
        required=False,
        label='Source CRS (EPSG)',
        help_text="Optional: Specify the source coordinate system if not embedded in the file (e.g., 4326 for WGS84, 28992 for RD New)",
        widget=forms.NumberInput(attrs={
            'placeholder': 'e.g., 4326',
            'class': 'number-input',
        })
    )

    def clean_file(self):
        """Validate uploaded file has correct extension."""
        file = self.cleaned_data['file']
        name = file.name.lower()
        
        # FIXED: Correct validation logic (was inverted before)
        valid_extensions = ('.geojson', '.json', '.zip', '.shp')
        if not name.endswith(valid_extensions):
            raise forms.ValidationError(
                "Please upload a GeoJSON (.geojson, .json) or Shapefile (.zip or .shp)."
            )
        
        # Additional validation for file size (optional, 100MB limit)
        max_size = 100 * 1024 * 1024  # 100 MB
        if file.size > max_size:
            raise forms.ValidationError(
                f"File size exceeds maximum allowed ({max_size // (1024*1024)} MB)."
            )
        
        return file
    
    def clean_source_crs(self):
        """Validate source CRS is a valid EPSG code."""
        crs = self.cleaned_data.get('source_crs')
        
        if crs is not None:
            # Common EPSG codes range check
            if crs < 1000 or crs > 100000:
                raise forms.ValidationError(
                    "EPSG code should be between 1000 and 100000. "
                    "Common codes: 4326 (WGS84), 28992 (RD New), 3857 (Web Mercator)."
                )
        
        return crs


class MappingForm(forms.Form):
    """
    Dynamic form for field mapping.
    Fields are added dynamically in the view based on the target model.
    """
    pass