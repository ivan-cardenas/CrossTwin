from pyexpat.errors import messages
import tempfile, os
import uuid

from django.shortcuts import render, redirect
from django.db import transaction, connection
from django.db.models import fields as django_fields  
from django.urls import reverse
from django.utils import timezone
from django.conf import settings
from django.apps import apps

import pandas as pd
import geopandas as gpd

from .forms import GeoUploadForm, MappingForm, get_target_model_choices
from .utils import gpd_read_any
from core.utils import MODEL_REGISTRY

from django.db.models import Field, ForeignKey, OneToOneField, AutoField
from django.contrib.gis.db.models import GeometryField, RasterField, MultiPolygonField


import rasterio
from rasterio.warp import calculate_default_transform, reproject, Resampling
import numpy as np


COORDINATE_SYSTEM = settings.COORDINATE_SYSTEM


# Optional, tiny per-model overrides (only what can't be inferred)
MODEL_OVERRIDES = {
    'common.City': {
        'upsert_keys': ['cityName'],           # otherwise we try unique/unique_together
        'geometry_field': 'geom',              # which field stores geometry
        'target_srid_default': COORDINATE_SYSTEM,
    },
    'common.Region': {
        'upsert_keys': ['regionName'],
        'geometry_field': 'geom',
        'target_srid_default': COORDINATE_SYSTEM,
    },
    'common.Neighborhood': {
        'upsert_keys': ['neighborhoodName'],
        'geometry_field': 'geom',
        'target_srid_default': COORDINATE_SYSTEM,
    },
    'watersupply.ConsumptionCapita': {
        'upsert_keys': ['city', 'year'],       # logical business key
        'target_srid_default': COORDINATE_SYSTEM,           # no geometry in this model
    },
    'watersupply.TotalWaterDemand': {
        'upsert_keys': ['city', 'year'],
        'target_srid_default': COORDINATE_SYSTEM,
    },
    'watersupply.SupplySecurity': {
        'upsert_keys': ['city', 'year'],
        'target_srid_default': COORDINATE_SYSTEM,
    },
    'watersupply.PipeNetwork': {
        'upsert_keys': ['id'],
        'geometry_field': 'geom',
        'target_srid_default': COORDINATE_SYSTEM,
    },
}

def _get_expected_geom_type(field):
    """Return human-readable geometry type expected by the field."""
    from django.contrib.gis.db.models import (
        PointField, MultiPointField,
        LineStringField, MultiLineStringField,
        PolygonField, MultiPolygonField,
        GeometryField, RasterField
    )
    
    type_map = {
        PointField: 'Point',
        MultiPointField: 'MultiPoint or Point',
        LineStringField: 'LineString',
        MultiLineStringField: 'MultiLineString or LineString',
        PolygonField: 'Polygon',
        MultiPolygonField: 'MultiPolygon or Polygon',
        GeometryField: 'Any geometry type',
        RasterField: 'Raster',
    }
    
    return type_map.get(type(field), 'Unknown')

def _get_model_spec(label):
    """
    Derive field spec from the Django model itself.
    - required = non-nullable & no default & not AutoField/PK
    - optional = the rest (user can map if they want)
    - detect geometry fields & FK fields
    - infer unique constraints
    Then apply MODEL_OVERRIDES to fill gaps (e.g., upsert keys).
    """
    model = MODEL_REGISTRY[label]
    opts = model._meta

    fields = []
    for f in opts.get_fields():
        # Skip M2M and reverse relations
        if f.many_to_many or f.auto_created:
            continue
        # Real fields only
        if not isinstance(f, Field):
            continue
        fields.append(f)

    # required/optional
    required, optional = [], []
    field_help_texts = {}
    for f in fields:
        if isinstance(f, AutoField) or f.primary_key:
            continue  # never map PK directly
        if f.name == 'area_km2' or f.name == 'populationDensity' or f.name == 'last_updated':
            continue  # skip computed fields
        # null=False and no default => likely required for create
        is_required = (not f.null) and (f.default is django_fields.NOT_PROVIDED)
        (required if is_required else optional).append(f.name)
        
        if f.help_text:
            field_help_texts[f.name] = f.help_text
            
            

    # geometry
    raster_fields = [f.name for f in fields if isinstance(f, RasterField)]
    geom_fields = [f.name for f in fields if isinstance(f, GeometryField) or isinstance(f, RasterField) ]
    
    has_raster = len(raster_fields) > 0
    has_geometry = len(geom_fields) > 0
    
    
    # Model type: 'raster', 'vector', 'both', or 'tabular'
    if has_raster and has_geometry:
        model_type = 'both'
    elif has_raster:
        model_type = 'raster'
    elif has_geometry:
        model_type = 'vector'
    else:
        model_type = 'tabular'
    
    #Add geometry type information
    geom_type_info = None
    if geom_fields:
        geom_field_obj = next((f for f in fields if f.name == geom_fields[0]), None)
        if geom_field_obj:
            geom_type_info = {
                'field_name': geom_field_obj.name,
                'field_class': geom_field_obj.__class__.__name__,  # e.g., 'MultiPolygonField', 'PointField'
                'expected_type': _get_expected_geom_type(geom_field_obj),
            }

    # Add raster type information (for raster models)
    raster_type_info = None
    if raster_fields:
        raster_field_obj = next((f for f in fields if f.name == raster_fields[0]), None)
        if raster_field_obj:
            raster_type_info = {
                'field_name': raster_field_obj.name,
                'field_class': raster_field_obj.__class__.__name__,  # 'RasterField'
            }


    # uniques
    unique_together = list(getattr(opts, 'unique_together', [])) or []
    unique_fields = [f.name for f in fields if getattr(f, 'unique', False)]

    spec = {
        'model': model,
        'label': label,
        'required': required,
        'optional': optional,
        'fk_fields': [f.name for f in fields if isinstance(f, (ForeignKey, OneToOneField))],
        'geom_fields': geom_fields,
        'raster_fields': raster_fields,
        'has_geometry': has_geometry,
        'has_raster': has_raster,
        'model_type': model_type,  # 'raster', 'vector', 'both', or 'tabular'
        'unique_together': unique_together,  # list of tuples
        'unique_fields': unique_fields,      # list of field names
        'target_srid_default': None,
        'geom_type_info': geom_type_info,
        'raster_type_info': raster_type_info,  # NEW
        'geometry_field': geom_fields[0] if geom_fields else None,
        'raster_field': raster_fields[0] if raster_fields else None,  # NEW
        'upsert_keys': None,  # will fill with override or infer
        'field_help_texts': field_help_texts
    }

    # Apply per-model overrides (upsert keys, target SRID, geometry field)
    if label in MODEL_OVERRIDES:
        o = MODEL_OVERRIDES[label]
        for k, v in o.items():
            spec[k] = v

    # If no explicit upsert_keys, infer from unique_together/unique
    if not spec['upsert_keys']:
        if spec['unique_together']:
            spec['upsert_keys'] = list(spec['unique_together'][0])
        elif spec['unique_fields']:
            spec['upsert_keys'] = [spec['unique_fields'][0]]
        else:
            # Fallback: try first non-nullable char/int field (best-effort)
            fallback = next((f for f in spec['required'] if f not in spec['geom_fields']), None)
            spec['upsert_keys'] = [fallback] if fallback else []

    return spec


def _build_mapping_form(target_model, columns, gdf_crs, data=None):
    from django import forms

    spec = _get_model_spec(target_model)
    
    # Build fields dict BEFORE class creation
    fields = {}
    CHOICES = [('', '— none —')] + [(c, c) for c in columns]

    for fld in (spec['required'] + [f for f in spec['optional'] if f not in spec['required']]):
        help_text = spec.get('field_help_texts', {}).get(fld, '')
        
        fields[f'map__{fld}'] = forms.ChoiceField(
            choices=CHOICES,
            required=(fld in spec['required']),
            label=fld,
            help_text=help_text
        )

    if spec['has_geometry'] and spec['geometry_field']:
        default_srid = spec['target_srid_default'] or 4326
        fields['target_srid'] = forms.IntegerField(
            required=True, initial=default_srid,
            help_text=f'Target SRID to store geometry (e.g., {default_srid}).'
        )

    fields['source_crs'] = forms.IntegerField(
        required=False,
        initial=gdf_crs.to_epsg() if gdf_crs else None,
        help_text='Source CRS EPSG code (auto-detected if available).'
    )

    fields['dry_run'] = forms.BooleanField(required=False, initial=True, label="Check mapping only (dry-run)")

    # Create class with fields already defined
    _F = type('MappingForm', (MappingForm,), fields)

    return _F(data=data), spec


def _read_raster_file(file_obj, target_srid=None):
    """
    Read a raster file and optionally reproject it.
    Returns a dict with raster metadata and data.
    """
    import rasterio
    from rasterio.warp import calculate_default_transform, reproject, Resampling
    import numpy as np
    from datetime import datetime
    
    with rasterio.open(file_obj) as src:
        # Read the raster data
        data = src.read(1)  # Read first band
        
        # Get metadata
        meta = src.meta.copy()
        transform = src.transform
        crs = src.crs
        
        # Try to extract date from metadata or tags
        raster_date = None
        
        # Try to get date from GDAL metadata
        tags = src.tags()
        if 'TIFFTAG_DATETIME' in tags:
            try:
                raster_date = datetime.strptime(tags['TIFFTAG_DATETIME'], '%Y:%m:%d %H:%M:%S').date()
            except:
                pass
        
        # Try to get from other common metadata fields
        if not raster_date and 'acquisition_date' in tags:
            try:
                raster_date = datetime.strptime(tags['acquisition_date'], '%Y-%m-%d').date()
            except:
                pass
        
        # If no date found in metadata, use today as default
        if not raster_date:
            raster_date = datetime.now().date()
        
        # Reproject if needed
        if target_srid and crs and crs.to_epsg() != target_srid:
            dst_crs = f'EPSG:{target_srid}'
            transform, width, height = calculate_default_transform(
                crs, dst_crs, src.width, src.height, *src.bounds
            )
            
            # Create destination array
            dst_data = np.empty((height, width), dtype=data.dtype)
            
            # Reproject
            reproject(
                source=data,
                destination=dst_data,
                src_transform=src.transform,
                src_crs=crs,
                dst_transform=transform,
                dst_crs=dst_crs,
                resampling=Resampling.bilinear
            )
            
            data = dst_data
            meta.update({
                'crs': dst_crs,
                'transform': transform,
                'width': width,
                'height': height
            })
        
        return {
            'data': data,
            'meta': meta,
            'transform': transform,
            'crs': crs.to_epsg() if crs else None,
            'bounds': src.bounds,
            'width': src.width,
            'height': src.height,
            'nodata': src.nodata,
            'date': raster_date.isoformat() if raster_date else None  # ISO format for session storage
        }
# ---------- Generic importer ----------

def _cast_value(value, field):
    """Best-effort cast to Django field type."""
    from django.db.models import IntegerField, FloatField, BooleanField, DateField, DateTimeField, CharField, TextField

    if value is None or (isinstance(value, float) and value != value):  # NaN->None
        return None

    try:
        if isinstance(field, IntegerField):
            return int(value)
        if isinstance(field, FloatField):
            return float(value)
        if isinstance(field, BooleanField):
            # Accept 'true'/'false'/'1'/'0'
            if isinstance(value, str):
                return value.strip().lower() in ('1', 'true', 'yes', 'y')
            return bool(value)
        if isinstance(field, (DateField, DateTimeField)):
            # Let Django parse strings on assignment, else parse here if you want strictness
            return value
        if isinstance(field, (CharField, TextField)):
            return str(value)
        # Geometry & FK handled elsewhere
        return value
    except Exception:
        return value


def _resolve_fk(model, field_name, raw, prefer_name=True):
    """
    Resolve FK by name (case-insensitive) or id. Works for City-like foreign keys.
    - prefer_name=True: try '<RelatedModel>.objects.filter(<best_name_field>__iexact=raw)'
    - fallback: id=int(raw)
    When unsure of the best display field, we try common candidates: 'name', '<modelname>Name'
    """
    fk = model._meta.get_field(field_name)
    rel_model = fk.remote_field.model

    if raw is None:
        return None

    # Try by name (string)
    if isinstance(raw, str):
        candidates = ['name', f'{rel_model.__name__.lower()}Name', f'{rel_model.__name__}Name']
        for c in candidates:
            if c in [f.name for f in rel_model._meta.fields]:
                obj = rel_model.objects.filter(**{f"{c}__iexact": raw.strip()}).first()
                if obj:
                    return obj

    # Try by ID
    try:
        return rel_model.objects.get(id=int(raw))
    except Exception:
        return None


def _to_multipolygon(geos):
    if geos is None or geos.empty:
        return None
    if geos.geom_type == 'MultiPolygon':
        return geos
    if geos.geom_type == 'Polygon':
        from django.contrib.gis.geos import MultiPolygon
        return MultiPolygon([geos])
    return None  # skip non-area types


@transaction.atomic
def _generic_import(gdf, target_label, colmap, dry_run=True, target_srid=None):
    """
    One importer for all models in MODEL_REGISTRY.
    """
    from django.contrib.gis.geos import GEOSGeometry

    spec = _get_model_spec(target_label)
    model = spec['model']
    opts = model._meta

    total = len(gdf)
    created = updated = skipped = errors = 0
    sample_errors = []

    # Prepare a field lookup for type casting
    field_by_name = {f.name: f for f in opts.get_fields() if isinstance(f, GeometryField) or isinstance(f, RasterField)}

    geom_field_name = spec['geometry_field'] if spec['has_geometry'] else None
    geom_field_obj = field_by_name.get(geom_field_name) if geom_field_name else None

    print(f"=== IMPORT DEBUG ===")
    print(f"Model: {target_label}")
    print(f"Total rows: {total}")
    print(f"Column mapping: {colmap}")
    print(f"Upsert keys: {spec['upsert_keys']}")
    print(f"Geometry field: {geom_field_name}")
    print(f"Required fields: {spec['required']}")
    

    for idx, row in gdf.iterrows():
        sid=transaction.savepoint()
        try:
            print(f"\n--- Row {idx} ---")
            
            # Build lookup for upsert
            lookup = {}
            for key in (spec['upsert_keys'] or []):
                src = colmap.get(key)
                print(f"  Upsert key '{key}' -> source column '{src}'")
                if not src:
                    raise ValueError(f"Missing mapping for upsert key '{key}'")
                raw = row[src]
                print(f"  Raw value: {raw}")
                f = field_by_name.get(key)
                if isinstance(f, (ForeignKey, OneToOneField)):
                    val = _resolve_fk(model, key, raw)
                    if val is None:
                        raise ValueError(f"FK not found for '{key}': {raw}")
                    lookup[key] = val
                else:
                    lookup[key] = _cast_value(raw, f)
            
            print(f"  Lookup dict: {lookup}")

            # Defaults / updates
            defaults = {}
            for fname, f in field_by_name.items():
                if fname in lookup or fname == geom_field_name:
                    continue
                if fname not in colmap or not colmap[fname]:
                    continue
                raw = row[colmap[fname]]
                if isinstance(f, (ForeignKey, OneToOneField)):
                    defaults[fname] = _resolve_fk(model, fname, raw)
                elif isinstance(f, GeometryField):
                    pass
                else:
                    defaults[fname] = _cast_value(raw, f)


            # Geometry handling (if any)
            if geom_field_name and hasattr(gdf, 'geometry'):
                shp = row.geometry
                print(f"  Geometry type: {shp.geom_type if shp else 'None'}, empty: {shp.is_empty if shp else 'N/A'}")
                
                if shp is not None and not shp.is_empty:
                    # Get source SRID from GeoDataFrame
                    source_srid = gdf.crs.to_epsg() if gdf.crs else 4326
                    
                    # Create geometry WITH SRID
                    geos = GEOSGeometry(shp.wkt, srid=source_srid)
                    
                    # Transform to target SRID if different
                    if target_srid and source_srid != target_srid:
                        geos.transform(target_srid)
                else:
                    geos = None
                

                if geos and isinstance(geom_field_obj, MultiPolygonField):
                    geos = _to_multipolygon(geos)
                    print(f"  Converted to MultiPolygon: {geos is not None}")

                if geos is None:
                    if geom_field_name in spec['required']:
                        print(f"  SKIPPING: geometry is None/empty but required")
                        skipped += 1
                        continue
                else:
                    defaults[geom_field_name] = geos

            # get_or_create / update
            print(f"  Calling get_or_create with lookup={lookup}")
            obj, was_created = model.objects.update_or_create(**lookup, defaults=defaults)
            if was_created:
                print(f"  CREATED: {obj}")
                created += 1
            else:
                changed = False
                for k, v in defaults.items():
                    if getattr(obj, k) != v:
                        setattr(obj, k, v)
                        changed = True
                if changed:
                    obj.save()
                    print(f"  UPDATED: {obj}")
                    updated += 1
                else:
                    print(f"  SKIPPED (no changes): {obj}")
                    skipped += 1
            transaction.savepoint_commit(sid)

        except Exception as e:
            transaction.savepoint_rollback(sid)
            print(f"  ERROR: {e}")
            import traceback
            traceback.print_exc()
            errors += 1
            if len(sample_errors) < 10:
                sample_errors.append(f"Row {idx}: {e}")

    if dry_run:
        transaction.set_rollback(True)

    return {
        'target': opts.label,
        'total_rows': total,
        'created': created,
        'updated': updated,
        'skipped': skipped,
        'errors': errors,
        'sample_errors': sample_errors,
    }


@transaction.atomic
def _raster_import(raster_path, target_label, field_name, metadata_map, dry_run=True, target_srid=None, date=None):
    """
    Import a raster file into a Django model with RasterField stored in PostGIS.
    """
    from django.contrib.gis.gdal import GDALRaster
    import rasterio
    from rasterio.warp import calculate_default_transform, reproject, Resampling
    import tempfile
    import shutil
    
    print(f"=== _raster_import called ===")
    print(f"raster_path: {raster_path}")
    print(f"target_label: {target_label}")
    print(f"field_name: {field_name}")
    print(f"dry_run: {dry_run}")
    print(f"target_srid: {target_srid}")
    
    spec = _get_model_spec(target_label)
    model = spec['model']
    
    # Get the RasterField to check its SRID
    model_field = model._meta.get_field(field_name)
    model_srid = getattr(model_field, 'srid', None)
    print(f"Model RasterField SRID: {model_srid}")
    
    # Use model SRID if no target specified
    if not target_srid and model_srid:
        target_srid = model_srid
        print(f"Using model SRID as target: {target_srid}")
    
    temp_file = None
    writable_file = None
    
    try:
        # Get source CRS
        with rasterio.open(raster_path) as src:
            src_epsg = src.crs.to_epsg() if src.crs else None
            print(f"Source raster: {src.width}x{src.height}, EPSG: {src_epsg}")
        
        # Determine final SRID
        if not target_srid:
            target_srid = src_epsg if src_epsg else 28992
            print(f"No target SRID specified, using: {target_srid}")
        
        # Check if reprojection is needed
        needs_reproject = src_epsg and src_epsg != target_srid
        
        if needs_reproject:
            print(f"Reprojecting from EPSG:{src_epsg} to EPSG:{target_srid}")
            
            # Create temporary file for reprojected raster
            fd, temp_file = tempfile.mkstemp(suffix='.tif')
            os.close(fd)
            
            with rasterio.open(raster_path) as src:
                # Calculate destination transform
                dst_crs = f'EPSG:{target_srid}'
                transform, width, height = calculate_default_transform(
                    src.crs, dst_crs, src.width, src.height, *src.bounds
                )
                
                # Prepare destination metadata
                kwargs = src.meta.copy()
                kwargs.update({
                    'crs': dst_crs,
                    'transform': transform,
                    'width': width,
                    'height': height
                })
                
                # Write reprojected raster
                with rasterio.open(temp_file, 'w', **kwargs) as dst:
                    for i in range(1, src.count + 1):
                        reproject(
                            source=rasterio.band(src, i),
                            destination=rasterio.band(dst, i),
                            src_transform=src.transform,
                            src_crs=src.crs,
                            dst_transform=transform,
                            dst_crs=dst_crs,
                            resampling=Resampling.bilinear
                        )
            
            raster_file_to_load = temp_file
            print(f"Reprojection complete")
        else:
            # If source has no CRS but target_srid specified, need to add CRS
            if not src_epsg and target_srid:
                print(f"Source has no CRS, adding EPSG:{target_srid}")
                
                fd, temp_file = tempfile.mkstemp(suffix='.tif')
                os.close(fd)
                
                with rasterio.open(raster_path) as src:
                    kwargs = src.meta.copy()
                    kwargs['crs'] = f'EPSG:{target_srid}'
                    
                    with rasterio.open(temp_file, 'w', **kwargs) as dst:
                        for i in range(1, src.count + 1):
                            dst.write(src.read(i), i)
                
                raster_file_to_load = temp_file
            else:
                raster_file_to_load = raster_path
        
        # CRITICAL: Create a WRITABLE copy for GDALRaster
        # This is necessary because Django will try to set the SRID
        print(f"Creating writable copy of raster...")
        fd, writable_file = tempfile.mkstemp(suffix='.tif')
        os.close(fd)
        shutil.copy2(raster_file_to_load, writable_file)
        print(f"Writable copy created at: {writable_file}")
        
        # Load with GDALRaster in WRITE mode
        print(f"Loading raster with GDALRaster in write mode...")
        gdal_raster = GDALRaster(writable_file, write=True)
        
        print(f"Raster loaded: {gdal_raster.width}x{gdal_raster.height}, SRID: {gdal_raster.srid}")
        
        # Build instance data
        instance_data = {}
        
        # Add metadata fields
        for model_field, value in metadata_map.items():
            instance_data[model_field] = value
        
        
        
        # Check for upsert keys
        lookup = {}
        if spec.get('upsert_keys'):
            for key in spec['upsert_keys']:
                if key in metadata_map:
                    lookup[key] = metadata_map[key]
        
        print(f"Lookup: {lookup}")
        
        # Create or update the object
        if lookup:
            try:
                obj = model.objects.get(**lookup)
                created = False
                print(f"Found existing object: {obj}")
                
                # Update metadata fields
                for key, value in instance_data.items():
                    setattr(obj, key, value)
                
                # Update raster field
                setattr(obj, field_name, gdal_raster)
                obj.save()
                
            except model.DoesNotExist:
                # Create new object
                instance_data['raster'] = gdal_raster
                obj = model.objects.create(**instance_data)
                created = True
                print(f"Created new object: {obj}")
        else:
            # Create new object without upsert
            instance_data['raster'] = gdal_raster
            obj = model.objects.create(**instance_data)
            created = True
            print(f"Created new object: {obj}")
            
            
        print (f"Instance data: {instance_data}")
        print(f"Object {'created' if created else 'updated'}: {obj}")
        
        if dry_run:
            print("DRY RUN - rolling back transaction")
            transaction.set_rollback(True)
        
        report = {
            'target': model._meta.label,
            'total_rows': 1,
            'created': 1 if created else 0,
            'updated': 0 if created else 1,
            'skipped': 0,
            'errors': 0,
            'sample_errors': [],
        }
        
        print(f"Returning report: {report}")
        return report
        
    except Exception as e:
        print(f"ERROR in _raster_import: {e}")
        import traceback
        traceback.print_exc()
        
        report = {
            'target': model._meta.label,
            'total_rows': 1,
            'created': 0,
            'updated': 0,
            'skipped': 0,
            'errors': 1,
            'sample_errors': [str(e)],
        }
        
        print(f"Returning error report: {report}")
        return report
    
    finally:
        # Clean up temporary files
        # Close the GDAL raster first to release file handles
        if 'gdal_raster' in locals():
            try:
                del gdal_raster  # This should close the file
                print("Closed GDALRaster")
            except:
                pass
        
        # Now clean up temp files
        for tmp in [temp_file, writable_file]:
            if tmp and os.path.exists(tmp):
                try:
                    os.unlink(tmp)
                    print(f"Cleaned up temp file: {tmp}")
                except Exception as e:
                    print(f"Could not delete temp file {tmp}: {e}")
                    
                    
def upload_geodata(request):
    """
    Two-step wizard:
      GET              -> render Step 1 (upload form)
      POST (no 'stage') -> process Step 1, stash temp file, render Step 2 (mapping)
      POST (stage='map') -> process Step 2, dry-run or import, render Result

    Always returns a response; never silently falls through.
    """
    from django.contrib import messages as django_messages

    # --- STEP 1 (GET) ---
    if request.method == 'GET':
        print ("Step 1: GET")
        form = GeoUploadForm()
        grouped_models = get_target_model_choices()
        
        return render(request, 'importer/upload.html', {
            'form': form,
            'grouped_models': grouped_models,
            })

    # --- STEP 1 (POST, no stage) ---
    if request.method == 'POST' and not request.POST.get('stage'):
        form = GeoUploadForm(request.POST, request.FILES)
        print ("Step 1: POST (no stage)")
        if not form.is_valid():
            # Validation errors -> re-render Step 1 with messages
            return render(request, 'importer/upload.html', {'form': form})

        # Extract cleaned data
        target_model = form.cleaned_data['target_model']
        source_crs = form.cleaned_data.get('source_crs')

        # Check if target_model is in registry
        if target_model not in MODEL_REGISTRY:
            form.add_error('target_model', f'Model "{target_model}" is not configured for import. Available: {list(MODEL_REGISTRY.keys())}')
            return render(request, 'importer/upload.html', {'form': form})
        
        file_ext = os.path.splitext(request.FILES['file'].name)[1].lower()
        is_raster = file_ext in ['.tif', '.tiff', '.geotiff']

        spec = _get_model_spec(target_model)
       
        
        # Validate file type matches model type
        if is_raster:
            if spec['model_type'] == 'vector':
                form.add_error('target_model', 
                    f'Cannot import raster file to vector model "{target_model}". '
                    f'This model only accepts geometry data {spec["geom_type_info"]["expected_type"]}. '
                    f'Please select a model with RasterField support.'
                )
                return render(request, 'importer/upload.html', {'form': form})
            elif spec['model_type'] == 'tabular':
                form.add_error('target_model', 
                    f'Cannot import raster file to model "{target_model}". '
                    f'This model has no RasterField to store raster data.'
                )
                return render(request, 'importer/upload.html', {'form': form})
        else:
            # is_raster = False, so it's a vector file
            if spec['model_type'] == 'raster':
                form.add_error('target_model', 
                    f'Cannot import vector file (GeoJSON/Shapefile) to raster model "{target_model}". '
                    f'This model only accepts raster data (.tif files). '
                    f'Please select a model with GeometryField support.'
                )
                return render(request, 'importer/upload.html', {'form': form})
            elif spec['model_type'] == 'tabular':
                form.add_error('file', 
                    f'Cannot import spatial data to model "{target_model}". '
                    f'This model has no spatial fields (GeometryField or RasterField).'
                )
                return render(request, 'importer/upload.html', {'form': form})
        
        # import raster files
        if is_raster:
            print(f"Detected raster file: {request.FILES['file'].name}")
            # Handle raster files
            try:
                raster_info = _read_raster_file(request.FILES['file'])
                
                # Store raster-specific info in session
                request.session['uploader_file_type'] = 'raster'
                request.session['uploader_raster_crs'] = raster_info['crs']
                request.session['uploader_raster_bounds'] = list(raster_info['bounds'])
                request.session['uploader_raster_width'] = raster_info['width']
                request.session['uploader_raster_height'] = raster_info['height']
                request.session['uploader_raster_date'] = raster_info['date']
                
                # Save raster to temp location
                upload_dir = os.path.join(settings.BASE_DIR, 'temp_uploads')
                os.makedirs(upload_dir, exist_ok=True)
                tmp_path = os.path.join(upload_dir, f'upload_{uuid.uuid4().hex}.tif')
                
                # Write the file
                with open(tmp_path, 'wb') as f:
                    request.FILES['file'].seek(0)
                    f.write(request.FILES['file'].read())
                
                request.session['uploader_tmp_path'] = tmp_path
                request.session['uploader_storage_kind'] = 'raster'
                request.session['uploader_target_model'] = target_model
                request.session.modified = True
                
                # For rasters, create a simplified mapping form
                # (rasters typically just need: which model, which field, and metadata)
                return render(
                    request,
                    'importer/RasterMapping.html',  # You'll need to create this template
                    {
                        'target_model': target_model,
                        'raster_info': raster_info,
                        'crs': raster_info['crs'],
                    }
                )
                
            except Exception as e:
                form.add_error('file', f'Could not read raster file: {e}')
                return render(request, 'importer/upload.html', {'form': form})
                
        else:

            # Read the uploaded file with GeoPandas
            try:
                gdf = gpd_read_any(request.FILES['file'])
            
            except Exception as e:
                form.add_error('file', f'Could not read file with GeoPandas: {e}')
                return render(request, 'importer/upload.html', {'form': form})

            # Set CRS if missing & provided by user
            try:
                if gdf.crs is None and source_crs:
                    gdf.set_crs(epsg=source_crs, inplace=True)
            except Exception as e:
                form.add_error('source_crs', f'Could not apply CRS: {e}')
                return render(request, 'importer/upload.html', {'form': form})
        
            # Detect source geometry type
            source_geom_type = None
            if hasattr(gdf, 'geometry') and len(gdf) > 0:
                first_geom = gdf.geometry.iloc[0]
                if first_geom is not None:
                    source_geom_type = first_geom.geom_type
        

            # --- Persist temp snapshot robustly ---
            
            tmp_path = None
            
            
            try:
                # Create a unique filename in Django's temp/media directory
                upload_dir = os.path.join(settings.BASE_DIR, 'temp_uploads')
                os.makedirs(upload_dir, exist_ok=True)
                
                tmp_path = os.path.join(upload_dir, f'upload_{uuid.uuid4().hex}.geojson')
                
                # Write using GeoPandas
                gdf.to_file(tmp_path, driver='GeoJSON')
                storage_kind = 'geojson'
                
            except Exception as e:
                if tmp_path and os.path.exists(tmp_path):
                    try:
                        os.unlink(tmp_path)
                    except:
                        pass
                form.add_error('file', f'Could not save temporary snapshot: {e}')
                return render(request, 'importer/upload.html', {'form': form})
        
            # Stash data in session
            request.session['uploader_tmp_path'] = tmp_path
            request.session['uploader_storage_kind'] = storage_kind
            request.session['uploader_target_model'] = target_model
            request.session['uploader_source_crs'] = (gdf.crs.to_epsg() if gdf.crs else None)
            request.session['uploader_columns'] = list(gdf.columns)
            request.session.modified = True
            

            # Build mapping form
            mapping_form, spec = _build_mapping_form(target_model, gdf.columns, gdf.crs)
            
            print("=== STEP 1 POST PROCESSED ===")

            
            return render(
                request,
                'importer/FieldMapping.html',
                {
                    'mapping_form': mapping_form,
                    'columns': gdf.columns,
                    'sample': gdf.head(5).to_html(),
                    'crs': gdf.crs,
                    'target_model': target_model,
                    'geom_type_info': spec.get('geom_type_info'),
                    'source_geom_type': source_geom_type,
                },
            )

    # --- STEP 2 (POST, stage='map') ---
    if request.method == 'POST' and request.POST.get('stage') == 'map':
        print("=== STEP 2 POST RECEIVED ===")
        print("Session keys:", list(request.session.keys()))
        
        try:
            connection.ensure_connection()
            if connection.is_usable():
                pass
            else:
                connection.close()
        except:
            connection.close()
            
            
        # get file type from session   
        file_type = request.session.get('uploader_file_type', 'vector')
    
        target_model = request.session.get('uploader_target_model')
        tmp_path = request.session.get('uploader_tmp_path')
        storage_kind = request.session.get('uploader_storage_kind')
        src_epsg = request.session.get('uploader_source_crs')
        
        print(f"target_model: {target_model}")
        print(f"tmp_path: {tmp_path}")
        print(f"storage_kind: {storage_kind}")
        print(f"file_type: {file_type}")  # NEW: Log the file type
        
        if not all([target_model, tmp_path, storage_kind]):
            print("SESSION DATA MISSING - redirecting")
            django_messages.error(request, "Session expired or incomplete. Please upload again.")
            return redirect(reverse('importer:upload_geodata'))
        
        
        # 
        if file_type == 'raster':
            # ========================================================
            # RASTER IMPORT PATH
            # ========================================================
            print("=== PROCESSING RASTER IMPORT ===")
            
            # Get form data specific to raster
            target_srid = request.POST.get('target_srid')
            dry_run = request.POST.get('dry_run') == 'on'
            raster_date = request.POST.get('raster_date')
            raster_name = request.POST.get('raster_name')
            
            
            # Collect metadata mappings (if your form has any)
            metadata_map = {}
            
            if raster_date:
                from datetime import datetime
                try:
                    # Parse the date string from the form (YYYY-MM-DD)
                    date_obj = datetime.strptime(raster_date, '%Y-%m-%d').date()
                    metadata_map['date'] = date_obj  # Assuming your model has a 'date' field
                    print(f"Parsed date: {date_obj}")
                    
                    metadata_map['name'] = raster_name
                except ValueError as e:
                    print(f"Could not parse date '{raster_date}': {e}")
                    django_messages.error(request, f"Invalid date format: {raster_date}")
                    return redirect(reverse('importer:upload_geodata'))
            
            for key, value in request.POST.items():
                if key.startswith('meta__'):
                    field_name = key.replace('meta__', '')
                    metadata_map[field_name] = value
            
            print(f"Metadata mappings: {metadata_map}")
            
            # Execute raster import
            try:
                print("Starting raster import...")
                report = _raster_import(
                    tmp_path, 
                    target_model, 
                    'raster',
                    metadata_map,
                    dry_run=dry_run,
                    target_srid=int(target_srid) if target_srid else None
                )
                print("Raster import report:", report)
            except Exception as e:
                print(f"Raster import ERROR: {e}")
                import traceback
                traceback.print_exc()
                django_messages.error(request, f"Raster import failed: {e}")
                return redirect(reverse('importer:upload_geodata'))
            
            # Display results
            if dry_run:
                django_messages.info(request, "Dry-run completed. Nothing was saved.")
            else:
                django_messages.success(request, "Raster import completed successfully.")
            
            # Clean up temp file
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
            
            # Clear session
            for k in ['uploader_tmp_path', 'uploader_storage_kind', 'uploader_target_model', 
                    'uploader_source_crs', 'uploader_columns', 'uploader_file_type',
                    'uploader_raster_crs', 'uploader_raster_bounds', 'uploader_raster_width', 
                    'uploader_raster_height']:
                request.session.pop(k, None)
            request.session.modified = True
            
            return render(request, 'importer/upload_result.html', {'report': report, 'dry_run': dry_run})
        
        else: 
                
            target_model = request.session.get('uploader_target_model')
            tmp_path = request.session.get('uploader_tmp_path')
            storage_kind = request.session.get('uploader_storage_kind')
            src_epsg = request.session.get('uploader_source_crs')
            
            print(f"target_model: {target_model}")
            print(f"tmp_path: {tmp_path}")
            print(f"storage_kind: {storage_kind}")
            
            if not all([target_model, tmp_path, storage_kind]):
                print("SESSION DATA MISSING - redirecting")
                django_messages.error(request, "Session expired or incomplete. Please upload again.")
                return redirect(reverse('importer:upload_geodata'))
            
            # Rehydrate GeoDataFrame
            try:
                if storage_kind == 'parquet':
                    gdf = pd.read_parquet(tmp_path)
                    # If geometry column exists, re-wrap as GeoDataFrame
                    if 'geometry' in gdf.columns:
                        gdf = gpd.GeoDataFrame(gdf, geometry='geometry', crs=(f"EPSG:{src_epsg}" if src_epsg else None))
                    else:
                        gdf = gpd.GeoDataFrame(gdf, crs=(f"EPSG:{src_epsg}" if src_epsg else None))
                else:
                    # GeoJSON fallback
                    gdf = gpd.read_file(tmp_path)
                    print("Rehydrated GeoDataFrame from GeoJSON, CRS:", gdf.crs)
            except Exception as e:
                django_messages.error(request, f"Could not reload the uploaded data: {e}")
                return redirect(reverse('importer:upload_geodata'))

            # Build & validate mapping form
            mapping_form, spec = _build_mapping_form(target_model, gdf.columns, gdf.crs, data=request.POST)
            print("Form built, validating...")
            print("Form errors before is_valid:", mapping_form.errors)

            if not mapping_form.is_valid():
                print("FORM INVALID!")
                print("Form errors:", mapping_form.errors)
                return render(
                    request,
                    'importer/FieldMapping.html',
                    # ...
                )

            print("Form is valid!")
            print("Cleaned data:", mapping_form.cleaned_data)

            dry_run = mapping_form.cleaned_data.get('dry_run')
            target_srid = mapping_form.cleaned_data.get('target_srid')
            print(f"dry_run: {dry_run}, target_srid: {target_srid}")

            # Build column mapping dict from dynamic form fields
            spec = _get_model_spec(target_model)
            colmap = {}
            for fld in (spec['required'] + [f for f in spec['optional'] if f not in spec['required']]):
                key = f'map__{fld}'
                if key in mapping_form.cleaned_data:
                    colmap[fld] = mapping_form.cleaned_data[key] or None

            print("Column mapping:", colmap)

            # Validate required mappings
            missing = [f for f in spec['required'] if not colmap.get(f) and f not in spec['geom_fields']]
            print(f"Missing required fields: {missing}")

            if missing:
                mapping_form.add_error(None, f"Missing mappings for required fields: {', '.join(missing)}")
                return render(
                    request,
                    'importer/FieldMapping.html',
                    {
                        'mapping_form': mapping_form,
                        'columns': gdf.columns,
                        'sample': gdf.head(5).to_html(classes='dataframe'),
                        'target_model': target_model,
                    },
                )
                
            print("Passed missing fields check")


            # Reproject if geometry target
            print(f"Checking geometry reproject: has_geometry={spec.get('has_geometry')}, geometry_field={spec.get('geometry_field')}, target_srid={target_srid}, gdf.crs={gdf.crs}")

            if spec.get('has_geometry') and spec.get('geometry_field') and target_srid and gdf.crs:
                try:
                    gdf = gdf.to_crs(int(target_srid))
                    print("CRS transform successful")
                except Exception as e:
                    print(f"CRS transform FAILED: {e}")
                    mapping_form.add_error('target_srid', f'CRS transform failed: {e}')
                    return render(
                        request,
                        'importer/FieldMapping.html',
                        {
                            'mapping_form': mapping_form,
                            'columns': gdf.columns,
                            'sample': gdf.head(5).to_html(classes='dataframe'),
                            'target_model': target_model,
                        },
                    )
            print("About to start import...")
            # Import (or dry-run)
            try:
                print("Starting import...")
                report = _generic_import(gdf, target_model, colmap, dry_run=dry_run, target_srid=target_srid)
                print ("Import report:", report)
            except Exception as e:
                django_messages.error(request, f"Import failed: {e}")
                return render(
                    request,
                    'importer/FieldMapping.html',
                    {
                        'mapping_form': mapping_form,
                        'columns': gdf.columns,
                        'sample': gdf.head(5).to_html(),
                        'crs': gdf.crs,
                        'target_model': target_model,
                    },
                )

            if dry_run:
                django_messages.info(request, "Dry-run completed. Nothing was saved.")
            else:
                django_messages.success(request, "Import completed successfully.")

            # Clean temp file (best-effort)
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

            for k in ['uploader_tmp_path', 'uploader_storage_kind', 'uploader_target_model', 'uploader_source_crs', 'uploader_columns']:
                request.session.pop(k, None)
            request.session.modified = True

            return render(request, 'importer/upload_result.html', {'report': report, 'dry_run': dry_run})

    # Any other method/state → return Step 1
    django_messages.warning(request, "Unexpected state. Starting over.")
    return redirect(reverse('importer:upload_geodata'))