from pyexpat.errors import messages
import tempfile, os

from django.shortcuts import render, redirect

from django.db import transaction
from django.urls import reverse
from django.utils import timezone
from django.conf import settings

import pandas as pd
import geopandas as gpd

from .forms import GeoUploadForm, MappingForm
from .utils import gpd_read_any

from common import models 
from watersupply import models

from django.db.models import Field, ForeignKey, OneToOneField, AutoField
from django.contrib.gis.db.models import GeometryField, MultiPolygonField


COORDINATE_SYSTEM = settings.COORDINATE_SYSTEM

# Helper: define which model fields are mappable and which are required
MODEL_REGISTRY = {
    'common.City': models.City,
    'watersupply.ConsumptionCapita': models.ConsumptionCapita,
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
    for f in fields:
        if isinstance(f, AutoField) or f.primary_key:
            continue  # never map PK directly
        
        # null=False and no default => likely required for create
        is_required = (not f.null) and (f.default is models.fields.NOT_PROVIDED)
        (required if is_required else optional).append(f.name)

    # geometry
    geom_fields = [f.name for f in fields if isinstance(f, GeometryField)]
    has_geometry = len(geom_fields) > 0

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
        'geometry_field': geom_fields[0] if geom_fields else None,
        'upsert_keys': None,                 # will fill with override or infer
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
    """
    Replaces the old hard-coded spec with introspected spec.
    """
    from django import forms
    spec = _get_model_spec(target_model)

    class _F(MappingForm):
        pass

    CHOICES = [('', '— none —')] + [(c, c) for c in columns]

    # Add selectors for required + optional
    # Tip: keep geometry field present even if not required (user might skip for non-geom import)
    for fld in (spec['required'] + [f for f in spec['optional'] if f not in spec['required']]):
        setattr(_F, f'map__{fld}',
                forms.ChoiceField(choices=CHOICES,
                                  required=(fld in spec['required']),
                                  label=fld))

    # Geometry target: let user pick target SRID
    if spec['has_geometry'] and spec['geometry_field']:
        default_srid = spec['target_srid_default'] or 4326
        setattr(_F, 'target_srid', forms.IntegerField(
            required=True, initial=default_srid,
            help_text=f'Target SRID to store geometry (e.g., {default_srid}).'
        ))

    setattr(_F, 'dry_run', forms.BooleanField(required=False, initial=True, label="Check mapping only (dry-run)"))
    return _F(data=data)

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
    - Casts values according to Django field types
    - Resolves FKs
    - Handles geometry (CRS + Polygon→MultiPolygon if target field is MultiPolygonField)
    - Upserts based on upsert_keys (overrides or unique constraints)
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

    # Geometry CRS adapt (GeoDataFrame already reprojected in the view if target_srid set)
    for idx, row in gdf.iterrows():
        try:
            # Build lookup for upsert
            lookup = {}
            for key in (spec['upsert_keys'] or []):
                src = colmap.get(key)
                if not src:
                    raise ValueError(f"Missing mapping for upsert key '{key}'")
                raw = row[src]

                f = field_by_name.get(key)
                if isinstance(f, (ForeignKey, OneToOneField)):
                    val = _resolve_fk(model, key, raw)
                    if val is None:
                        raise ValueError(f"FK not found for '{key}': {raw}")
                    lookup[key] = val
                else:
                    lookup[key] = _cast_value(raw, f)

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
                    # handled below
                    pass
                else:
                    defaults[fname] = _cast_value(raw, f)

            # Geometry handling (if any)
            if geom_field_name and hasattr(gdf, 'geometry'):
                shp = row.geometry
                geos = GEOSGeometry(shp.wkt) if shp is not None and not shp.is_empty else None

                # Coerce Polygon→MultiPolygon if target field is MultiPolygon
                if geos and isinstance(geom_field_obj, MultiPolygonField):
                    geos = _to_multipolygon(geos)

                if geos is None:
                    # If geometry required, skip; else allow null
                    if geom_field_name in spec['required']:
                        skipped += 1
                        continue
                else:
                    defaults[geom_field_name] = geos

            # get_or_create / update
            obj, was_created = model.objects.get_or_create(**lookup, defaults=defaults)
            if was_created:
                created += 1
            else:
                changed = False
                for k, v in defaults.items():
                    if getattr(obj, k) != v:
                        setattr(obj, k, v)
                        changed = True
                if changed:
                    obj.save()
                    updated += 1
                else:
                    # already identical
                    skipped += 1

        except Exception as e:
            errors += 1
            if len(sample_errors) < 10:
                sample_errors.append(f"Row {idx}: {e}")

    if dry_run:
        transaction.set_rollback(True)

    return {
        'target': opts.label,  # e.g., common_app.City
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
      GET  -> render Step 1 (upload form)
      POST (no 'stage') -> process Step 1, stash temp file, render Step 2 (mapping)
      POST (stage='map') -> process Step 2, dry-run or import, render Result
    Always returns a response; never silently falls through.
    """
    # --- STEP 1 (GET) ---
    if request.method == 'GET':
        form = GeoUploadForm()
        return render(request, 'importer/upload.html', {'form': form})

    # --- STEP 1 (POST, no stage) ---
    if request.method == 'POST' and not request.POST.get('stage'):
        form = GeoUploadForm(request.POST, request.FILES)
        if not form.is_valid():
            # Validation errors -> re-render Step 1 with messages
            return render(request, 'importer/upload.html', {'form': form})

        target_model = form.cleaned_data['target_model']
        source_crs = form.cleaned_data['source_crs']

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

        # --- Persist temp snapshot robustly ---
        # Prefer Parquet, but gracefully fall back to GeoJSON if pyarrow/fastparquet missing.
        tmp_path = None
        try:
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.parquet')
            gdf.to_parquet(tmp.name)  # requires pyarrow or fastparquet
            tmp_path = tmp.name
            storage_kind = 'parquet'
        except Exception:
            # Fallback: write a small GeoJSON snapshot (works everywhere)
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.geojson')
            # Keep size reasonable for very large inputs: write all rows (ok for most admin ops).
            gdf.to_file(tmp.name, driver='GeoJSON')
            tmp_path = tmp.name
            storage_kind = 'geojson'

        # Stash data in session
        request.session['uploader_tmp_path'] = tmp_path
        request.session['uploader_storage_kind'] = storage_kind
        request.session['uploader_target_model'] = target_model
        request.session['uploader_source_crs'] = (gdf.crs.to_epsg() if gdf.crs else None)
        request.session['uploader_columns'] = list(gdf.columns)
        request.session.modified = True

        # Build mapping form
        mapping_form = _build_mapping_form(target_model, gdf.columns, gdf.crs)
        return render(
            request,
            'importer/FieldMapping.html',
            {
                'mapping_form': mapping_form,
                'columns': gdf.columns,
                'sample': gdf.head(5).to_html(),
                'target_model': target_model,
            },
        )

    # --- STEP 2 (POST, stage='map') ---
    if request.method == 'POST' and request.POST.get('stage') == 'map':
        # Recover session state
        target_model = request.session.get('uploader_target_model')
        tmp_path = request.session.get('uploader_tmp_path')
        storage_kind = request.session.get('uploader_storage_kind')
        src_epsg = request.session.get('uploader_source_crs')

        if not all([target_model, tmp_path, storage_kind]):
            messages.error(request, "Session expired or incomplete. Please upload again.")
            return redirect(reverse('upload_geodata'))

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
        except Exception as e:
            messages.error(request, f"Could not reload the uploaded data: {e}")
            return redirect(reverse('upload_geodata'))

        # Build & validate mapping form
        mapping_form = _build_mapping_form(target_model, gdf.columns, gdf.crs, data=request.POST)
        if not mapping_form.is_valid():
            return render(
                request,
                'importer/FieldMapping.html',
                {
                    'mapping_form': mapping_form,
                    'columns': gdf.columns,
                    'sample': gdf.head(5).to_html(),
                    'target_model': target_model,
                },
            )

        dry_run = mapping_form.cleaned_data.get('dry_run')
        target_srid = mapping_form.cleaned_data.get('target_srid')

        # Build column mapping dict from dynamic form fields
        spec = _get_model_spec(target_model)
        colmap = {}
        for fld in (spec['required'] + [f for f in spec['optional'] if f not in spec['required']]):
            key = f'map__{fld}'
            if key in mapping_form.cleaned_data:
                colmap[fld] = mapping_form.cleaned_data[key] or None

        # Validate required mappings
        missing = [f for f in spec['required'] if not colmap.get(f)]
        if missing:
            mapping_form.add_error(None, f"Missing mappings for required fields: {', '.join(missing)}")
            return render(
                request,
                'importer/FieldMapping.html',
                {
                    'mapping_form': mapping_form,
                    'columns': gdf.columns,
                    'sample': gdf.head(5).to_html(),
                    'target_model': target_model,
                },
            )

        # Reproject if geometry target
        if spec.get('has_geometry') and spec.get('geometry_field') and target_srid and gdf.crs:
            try:
                gdf = gdf.to_crs(epsg=int(target_srid))
            except Exception as e:
                mapping_form.add_error('target_srid', f'CRS transform failed: {e}')
                return render(
                    request,
                    'importer/FieldMapping.html',
                    {
                        'mapping_form': mapping_form,
                        'columns': gdf.columns,
                        'sample': gdf.head(5).to_html(),
                        'target_model': target_model,
                    },
                )

        # Import (or dry-run)
        try:
            report = _generic_import(gdf, target_model, colmap, dry_run=dry_run, target_srid=target_srid)
        except Exception as e:
            messages.error(request, f"Import failed: {e}")
            return render(
                request,
                'importer/FieldMapping.html',
                {
                    'mapping_form': mapping_form,
                    'columns': gdf.columns,
                    'sample': gdf.head(5).to_html(),
                    'target_model': target_model,
                },
            )

        if dry_run:
            messages.info(request, "Dry-run completed. Nothing was saved.")
        else:
            messages.success(request, "Import completed successfully.")

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
    messages.warning(request, "Unexpected state. Starting over.")
    return redirect(reverse('upload_geodata'))