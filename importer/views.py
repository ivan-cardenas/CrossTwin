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

from .forms import GeoUploadForm, MappingForm, TARGET_MODELS, get_target_model_choices
from .utils import gpd_read_any


from django.db.models import Field, ForeignKey, OneToOneField, AutoField
from django.contrib.gis.db.models import GeometryField, MultiPolygonField


COORDINATE_SYSTEM = settings.COORDINATE_SYSTEM

# Build MODEL_REGISTRY from TARGET_MODELS in forms.py
MODEL_REGISTRY = TARGET_MODELS

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
        GeometryField
    )
    
    type_map = {
        PointField: 'Point',
        MultiPointField: 'MultiPoint or Point',
        LineStringField: 'LineString',
        MultiLineStringField: 'MultiLineString or LineString',
        PolygonField: 'Polygon',
        MultiPolygonField: 'MultiPolygon or Polygon',
        GeometryField: 'Any geometry type',
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
    geom_fields = [f.name for f in fields if isinstance(f, GeometryField)]
    has_geometry = len(geom_fields) > 0
    
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
        'has_geometry': has_geometry,
        'unique_together': unique_together,  # list of tuples
        'unique_fields': unique_fields,      # list of field names
        'target_srid_default': None,
        'geom_type_info': geom_type_info,
        'geometry_field': geom_fields[0] if geom_fields else None,
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
    field_by_name = {f.name: f for f in opts.get_fields() if isinstance(f, Field)}

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
        form = GeoUploadForm()
        grouped_models = get_target_model_choices()
        return render(request, 'importer/upload.html', {
            'form': form,
            'grouped_models': grouped_models,
            })

    # --- STEP 1 (POST, no stage) ---
    if request.method == 'POST' and not request.POST.get('stage'):
        form = GeoUploadForm(request.POST, request.FILES)
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