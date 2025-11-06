from django.forms import BooleanField, IntegerField
from django.shortcuts import render, redirect
import json
from django.contrib import messages
from django.contrib.gis.geos import GEOSGeometry, MultiPolygon, Polygon
from django.contrib.gis.gdal import DataSource, SpatialReference
from django.db import transaction
from django.urls import reverse
from django.utils import timezone
from django.conf import COORDINATE_SYSTEM

from .forms import GeoUploadForm, MappingForm
from .utils import gpd_read_any

from common.models import City, Neighborhood, Region
from watersupply.models import ConsumptionCapita

from django.db.models import Field, ForeignKey, OneToOneField, AutoField
from django.contrib.gis.db.models import GeometryField, MultiPolygonField, PolygonField


# Helper: define which model fields are mappable and which are required
MODEL_REGISTRY = {
    'common.City': City,
    'watersupply.ConsumptionCapita': ConsumptionCapita,
}

# Optional, tiny per-model overrides (only what can’t be inferred)
MODEL_OVERRIDES = {
    'common_app.City': {
        'upsert_keys': ['cityName'],          # otherwise we try unique/unique_together
        'geometry_field': 'geom',             # which field stores geometry
        'target_srid_default': COORDINATE_SYSTEM,
    },
    'watersupply_app.ConsumptionCapita': {
        'upsert_keys': ['city', 'year'],      # logical business key
        'target_srid_default': None,          # no geometry in this model
    },
}


def upload_geodata(request):
    # Step 1 submit: read file, stash gdf head & columns in session
    if request.method == 'GET':
        form = GeoUploadForm()
        return render(request, 'importer/upload.html', {'form': form})
    
    if request.method == 'POST' and 'stage' not in request.POST:
        form = GeoUploadForm(request.POST, request.FILES)
        if  form.is_valid():# Get the target model
            target_model = form.cleaned_data['target_model']
    
        # read with geopandas
    
        try:
            gdf = gpd_read_any(file_obj=request.FILES['file'])
        except Exception as e:
            form.add_error('file', f"Error reading file: {e}")
            return render(request, 'importer/upload.html', {'form': form})
        
        # set CRS if missing (shouldn't be missing, but just in case)
        if gdf.crs is None:
            gdf.set_crs(epsg=COORDINATE_SYSTEM)

        # put into session as JSON-serializable snapshot
        # (store a temporary parquet on disk to reload later without re-upload)
        import tempfile, os
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.parquet')
        gdf.to_parquet(tmp.name)
        request.session['uploader_tmp_path'] = tmp.name
        request.session['uploader_target_model'] = target_model
        request.session['uploader_gdf_head'] = gdf.head().to_dict()
        request.session['uploader_gdf_columns'] = gdf.columns.to_list()
        request.session.modified = True
        
        mapping_form = _build_mapping_form(target_model, gdf.columns, gdf.crs)
        return render(request, 'importer/upload.html', {
            'mapping_form': mapping_form,
            'columns': gdf.columns,
            'sample': gdf.head().to_html(index=False),
            'target_model': target_model,
            })
        
    # Step 2 submit: map columns
    if request.method == 'POST' and request.POST.get('stage') == 'mapping':
        
        target_model = request.session.get('uploader_target_model')
        tmp_path = request.session.get('uploader_tmp_path')
        
        if not (target_model and tmp_path):
            messages.error(request, 'Something went wrong. Please try again.')
            return redirect(reverse('importer:upload_geodata'))
        
        import geopandas as gpd
        import pandas
        gdf = gpd.read_parquet(tmp_path)
        # re-materrialize as GeoDataFrame if gemetry is present
        try:
            gdf = gpd.GeoDataFrame(gdf, geometry='geometry' if 'geometry' in gdf.columns else None)
        except Exception as e:
            messages.error(request, f'Error reading file: {e}')
            pass
        
        mapping_form = _build_mapping_form(target_model, gdf.columns, gdf.crs, data=request.POST)
        if not mapping_form.is_valid():
            return render(request, 'importer/mapping_fields.html', {
                'mapping_form': mapping_form,
                'columns': gdf.columns,
                'sample': gdf.head().to_html(index=False),
                'target_model': target_model,
                })
        
        dry_run = mapping_form.cleaned_data.get('dry_run')
        
        # Build Column mapping dict
        spec = MODEL_FIELD_SPECS[target_model]
        colmap = {}
        for field in (spec['required'] + spec['optional']):
            colmap[field] = mapping_form.cleaned_data.get(field)
            # Add geometry if present
            if spec['has_geometry']:
                colmap['geometry'] = mapping_form.cleaned_data.get('geometry')
                
        # Perform dry-run / import

        report = _import_dispatch(gdf, target_model, colmap, dry_run=dry_run)
        if dry_run:
            messages.info(request, "Dry-run completed. Nothing was saved.")
        else:
            messages.success(request, "Import completed successfully.")

        return render(request, 'uploader_app/upload_result.html', {
            'report': report,
            'dry_run': dry_run,
        })
        
def _build_mapping_form(target_model, columns, crs, data=None):
    spec = MODEL_FIELD_SPECS[target_model]
    class _F(MappingForm):
        pass
    
    
    CHOICES = [('','- none -')] + [(c,c) for c in columns]
    
    # Add selector per model field
    for field in spec['required'] + spec['optional']:
        required  = field in spec['required']
        setattr(_F, field, choices=CHOICES, required=required, label=field)
        
    if spec.get('has_geometry'):
        default_srid = spec.get('target_srid_default', COORDINATE_SYSTEM)
        setattr(_F, 'target_srid', IntegerField(
            required=True, initial=default_srid,
            help_text=f'Target SRID to store geometry (e.g., {4326}).')
        )
        
    # A dry-run toggle
    setattr(_F, 'dry_run', BooleanField(
        
        required=False, initial=True, label="Check mapping only (dry-run)")
    )
    
    return _F(data=data)

def import_dispatch(gdf, target_model_key, colmap, dry_run=True):
    spec = MODEL_SPECS[target_model_key]
    return import_generic(gdf, spec, colmap, dry_run=dry_run)

def _to_multipolygon(geom):
    if geom.geom_type == 'Polygon':
        return MultiPolygon([geom])
    if geom.geom_type == 'MultiPolygon':
        return geom
    
    return None

@transaction.atomic
def _import_cities(gdf, colmap, dry_run=True):
    required = ['cityName', 'geom']
    for r in required:
        assert colmap[r], f"Missing required column: {r}"
        
    total = len(gdf)
    created, updated, skipped, errors = 0, 0, 0, 0
    sample_errors = []
    
    for i, row in gdf.iterrows():
        try:
            city_name = str(row[colmap['cityName']].strip)
            
            # build GEOS geometry (if GDF has a geometry col)
            geos = None
            if hasattr(row, 'geometry') and row.geometry is not None:
                shp = row.geometry
                if shp is not None and not shp.is_empty:
                    geos = GEOSGeometry(shp.wkt, srid=colmap['target_srid'])
                    geos = _to_multipolygon(geos)
                else: 
                    geos = None
            else:
                pass
        
            if geos is None:
                skipped += 1
                continue
            
            defaults={}
            for f in ['area_km2', 'populationDensity', 'currentPopulation', 'PopYR2020', 'popGrowthRate']:
                col = colmap.get(f)
                if col:
                    val = row[col]
                    defaults[f] = val if val is not None else None
                    
            # Upsert by name
            obj, exists = City.objects.update_or_create(
                city_name=city_name,
                defaults={**defaults, 'geom': geos, 'last_updated': timezone.now()},
            )
            if exists:
                created =+1
            else:
                # update
                for k, v in defaults.items():
                    setattr(obj, k, v)
                obj.geom = geos
                obj.last_updated = timezone.now()
                
                obj.save()
                updated += 1
        
                        
        except Exception as e:
            errors += 1
            if len(sample_errors) < 10:
                sample_errors.append(f"Row {i}: {e}")
                
    if dry_run:
        #rollback
        transaction.set_rollback(True)
        
    return {
        'target' : 'City',
        'created': created,
        'updated': updated,
        'skipped': skipped,
        'errors': errors,
        'sample_errors': sample_errors
    }