"""
views_external.py
=================
View for the External Data Import page.
Handles PDOK WFS fetches and passes to _generic_import.
"""
import json
import logging
import tempfile
import os

import geopandas as gpd
import pandas as pd
import requests

from django.shortcuts import render, redirect
from django.urls import reverse
from django.contrib import messages as django_messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.conf import settings

from .external_data import (
    EXTERNAL_DATA_CATALOG,
    CATALOG_BY_KEY,
    SOURCE_INFO,
    get_catalog_grouped,
)
from .views import _generic_import, _get_model_spec

logger = logging.getLogger(__name__)

COORDINATE_SYSTEM = settings.COORDINATE_SYSTEM  # 28992


# ---------------------------------------------------------------------------
# Page view
# ---------------------------------------------------------------------------

def get_external_data(request):
    """
    Render the External Data catalog page.
    Users tick datasets they want, then POST to start the import.
    """
    catalog_grouped = get_catalog_grouped()

    sources = []
    for src_key in ["pdok", "sentinel2", "gee"]:
        info = SOURCE_INFO[src_key]
        categories = []
        for cat_name, datasets in catalog_grouped.get(src_key, {}).items():
            categories.append({
                "name": cat_name,
                "datasets": datasets,
            })
        categories.sort(key=lambda c: c["name"])
        sources.append({
            "key": src_key,
            "info": info,
            "categories": categories,
            "dataset_count": sum(len(c["datasets"]) for c in categories),
        })

    context = {
        "sources": sources,
        "catalog_json": json.dumps(
            {d["key"]: {
                "name": d["name"],
                "target_model": d["target_model"],
                "requires_bbox": d.get("requires_bbox", False),
                "requires_auth": d.get("requires_auth", False),
                "enabled": d.get("enabled", True),
            } for d in EXTERNAL_DATA_CATALOG}
        ),
    }
    return render(request, "importer/external_data.html", context)


# ---------------------------------------------------------------------------
# WFS fetch helpers
# ---------------------------------------------------------------------------

def _fetch_pdok_wfs(ds, bbox=None, max_features=50000):
    """
    Fetch features from a PDOK WFS endpoint and return a GeoDataFrame
    with the CRS **explicitly set to EPSG:28992** (the srsName we request).

    Key insight: PDOK WFS with outputFormat=json returns coordinates in the
    requested srsName (28992), but the GeoJSON wrapper may not include a
    CRS member (GeoJSON RFC 7946 assumes 4326). GeoPandas will therefore
    either tag the result as EPSG:4326 or leave CRS as None.

    We override the CRS after reading so the coordinates (which are actually
    in RD New meters) are correctly labelled.
    """
    params = {
        "service": "WFS",
        "version": "2.0.0",
        "request": "GetFeature",
        "typeName": ds["layer"],
        "outputFormat": "json",
        "srsName": ds["params"].get("srsName", "EPSG:28992"),
        "count": max_features,
    }

    if bbox:
        # bbox expected as [xmin, ymin, xmax, ymax] in EPSG:28992
        params["bbox"] = f"{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]},urn:ogc:def:crs:EPSG::28992"

    logger.info("Fetching WFS: %s  layer=%s", ds["url"], ds["layer"])
    resp = requests.get(ds["url"], params=params, timeout=120)
    resp.raise_for_status()

    # Write to a temp file so GeoPandas can read it cleanly
    fd, tmp = tempfile.mkstemp(suffix=".geojson")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(resp.text)

        gdf = gpd.read_file(tmp)
    finally:
        os.unlink(tmp)

    if gdf.empty:
        raise ValueError(f"WFS returned 0 features for {ds['layer']}")

    # ──────────────────────────────────────────────────────────────────
    # CRITICAL FIX: Force the correct CRS.
    #
    # The coordinates ARE in EPSG:28992 (we requested srsName=EPSG:28992)
    # but GeoJSON spec says coords are WGS84, so GeoPandas tags them
    # as EPSG:4326 or None.
    #
    # We must use set_crs(allow_override=True) — NOT to_crs() —
    # because the coordinates are already in 28992, they just have the
    # wrong label. to_crs() would try to reproject 155000,463000 from
    # degrees to meters → "Invalid coordinate (2049)" error.
    # ──────────────────────────────────────────────────────────────────
    requested_epsg = int(ds["params"].get("srsName", "EPSG:28992").split(":")[-1])
    gdf = gdf.set_crs(epsg=requested_epsg, allow_override=True)

    logger.info("Fetched %d features, CRS set to EPSG:%s", len(gdf), requested_epsg)
    return gdf


# ---------------------------------------------------------------------------
# Column-mapping builders per catalog entry
# ---------------------------------------------------------------------------

def _build_colmap_provinces(gdf, spec):
    """Map PDOK Provinciegebied columns → common.Province fields."""
    colmap = {}
    cols = {c.lower(): c for c in gdf.columns}

    for candidate in ["naam", "provincienaam", "name"]:
        if candidate in cols:
            colmap["provinceName"] = cols[candidate]
            break

    for candidate in ["code", "provinciecode"]:
        if candidate in cols:
            colmap["provinceCode"] = cols[candidate]
            break

    return colmap


def _build_colmap_cities(gdf, spec):
    """Map PDOK Gemeentegebied columns → common.City fields."""
    colmap = {}
    cols = {c.lower(): c for c in gdf.columns}

    for candidate in ["naam", "gemeentenaam", "name"]:
        if candidate in cols:
            colmap["cityName"] = cols[candidate]
            break

    for candidate in ["code", "gemeentecode"]:
        if candidate in cols:
            colmap["cityCode"] = cols[candidate]
            break

    return colmap


def _build_colmap_neighborhoods(gdf, spec):
    """Map PDOK buurten columns → common.Neighborhood fields."""
    colmap = {}
    cols = {c.lower(): c for c in gdf.columns}

    for candidate in ["buurtnaam", "naam", "name"]:
        if candidate in cols:
            colmap["neighborhoodName"] = cols[candidate]
            break

    for candidate in ["buurtcode", "code"]:
        if candidate in cols:
            colmap["neighborhoodCode"] = cols[candidate]
            break

    for candidate in ["gemeentenaam", "gm_naam"]:
        if candidate in cols:
            colmap["city"] = cols[candidate]
            break

    return colmap


def _build_colmap_protected_areas(gdf, spec):
    """Map PDOK Natura 2000 columns → nature.ProtectedArea fields."""
    colmap = {}
    cols = {c.lower(): c for c in gdf.columns}

    for candidate in ["naam", "naamgebied", "name", "site_name"]:
        if candidate in cols:
            colmap["name"] = cols[candidate]
            break

    for candidate in ["code", "gebiedcode", "site_code"]:
        if candidate in cols:
            colmap["code"] = cols[candidate]
            break

    for candidate in ["type", "gebiedtype"]:
        if candidate in cols:
            colmap["type"] = cols[candidate]
            break

    return colmap


def _build_colmap_buildings(gdf, spec):
    """Map PDOK BAG pand columns → builtup.Building fields."""
    colmap = {}
    cols = {c.lower(): c for c in gdf.columns}

    for candidate in ["identificatie", "pandid", "id"]:
        if candidate in cols:
            colmap["buildingId"] = cols[candidate]
            break

    for candidate in ["bouwjaar", "oorspronkelijkbouwjaar"]:
        if candidate in cols:
            colmap["yearBuilt"] = cols[candidate]
            break

    for candidate in ["status", "pandstatus"]:
        if candidate in cols:
            colmap["status"] = cols[candidate]
            break

    return colmap


def _build_colmap_waterbodies(gdf, spec):
    """Map PDOK Waterdeel_Vlak columns → nature.WaterBodies fields."""
    colmap = {}
    cols = {c.lower(): c for c in gdf.columns}

    for candidate in ["naam", "name", "naamofficieel"]:
        if candidate in cols:
            colmap["name"] = cols[candidate]
            break

    for candidate in ["typewater", "type", "functie"]:
        if candidate in cols:
            colmap["type"] = cols[candidate]
            break

    return colmap


def _build_colmap_waterways(gdf, spec):
    """Map PDOK Waterdeel_Lijn columns → nature.WaterWays fields."""
    colmap = {}
    cols = {c.lower(): c for c in gdf.columns}

    for candidate in ["naam", "name", "naamofficieel"]:
        if candidate in cols:
            colmap["name"] = cols[candidate]
            break

    for candidate in ["typewater", "type"]:
        if candidate in cols:
            colmap["type"] = cols[candidate]
            break

    return colmap


def _build_colmap_streets(gdf, spec):
    """Map PDOK NWB wegvakken columns → builtup.Street fields."""
    colmap = {}
    cols = {c.lower(): c for c in gdf.columns}

    for candidate in ["stt_naam", "straatnaam", "naam", "name"]:
        if candidate in cols:
            colmap["name"] = cols[candidate]
            break

    for candidate in ["wegnummer", "wegtype"]:
        if candidate in cols:
            colmap["roadType"] = cols[candidate]
            break

    return colmap


def _build_colmap_energy_labels(gdf, spec):
    """Map PDOK EP-Online columns → Energy.EnergyEfficiencyLabels fields."""
    colmap = {}
    cols = {c.lower(): c for c in gdf.columns}

    for candidate in ["energielabelklasse", "labelklasse", "label"]:
        if candidate in cols:
            colmap["label"] = cols[candidate]
            break

    for candidate in ["postcode"]:
        if candidate in cols:
            colmap["postcode"] = cols[candidate]
            break

    for candidate in ["registratiedatum", "opnamedatum"]:
        if candidate in cols:
            colmap["registrationDate"] = cols[candidate]
            break

    return colmap


# Registry: catalog key → colmap builder
COLMAP_BUILDERS = {
    "pdok_provinces": _build_colmap_provinces,
    "pdok_cities": _build_colmap_cities,
    "pdok_neighborhoods": _build_colmap_neighborhoods,
    "pdok_protected_areas": _build_colmap_protected_areas,
    "pdok_buildings": _build_colmap_buildings,
    "pdok_waterbodies": _build_colmap_waterbodies,
    "pdok_waterways": _build_colmap_waterways,
    "pdok_roads": _build_colmap_streets,
    "pdok_energy_labels": _build_colmap_energy_labels,
}


def _auto_colmap(gdf, spec):
    """
    Fallback: try to match GDF columns to model fields by name.
    Case-insensitive matching.
    """
    colmap = {}
    gdf_cols_lower = {c.lower(): c for c in gdf.columns}
    all_fields = spec["required"] + spec["optional"]

    for field_name in all_fields:
        if field_name in spec.get("geom_fields", []):
            continue
        fl = field_name.lower()
        if fl in gdf_cols_lower:
            colmap[field_name] = gdf_cols_lower[fl]

    return colmap


# ---------------------------------------------------------------------------
# Import dispatcher
# ---------------------------------------------------------------------------

@require_POST
def start_external_import(request):
    """
    Receives selected dataset keys via POST JSON, fetches data, imports it.
    """
    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    selected_keys = body.get("datasets", [])
    bbox = body.get("bbox", None)

    if not selected_keys:
        return JsonResponse({"error": "No datasets selected."}, status=400)

    invalid = [k for k in selected_keys if k not in CATALOG_BY_KEY]
    if invalid:
        return JsonResponse({"error": f"Unknown datasets: {', '.join(invalid)}"}, status=400)

    results = {}

    for key in selected_keys:
        ds = CATALOG_BY_KEY[key]

        # ── Guard: disabled / auth ────────────────────────────────
        if not ds.get("enabled", True):
            results[key] = {
                "status": "skipped",
                "message": "Not yet enabled — requires authentication or configuration.",
            }
            continue

        if ds.get("requires_bbox") and not bbox:
            results[key] = {
                "status": "skipped",
                "message": "Requires a bounding box. Please draw an area of interest.",
            }
            continue

        # ── WMS-only datasets: just store the endpoint reference ──
        if ds.get("format") == "wms":
            results[key] = _handle_wms_dataset(ds)
            continue

        # ── WFS vector datasets ───────────────────────────────────
        if ds["source"] == "pdok":
            results[key] = _handle_pdok_vector(ds, bbox)
            continue

        # ── Fallback ──────────────────────────────────────────────
        results[key] = {
            "status": "skipped",
            "message": f"No handler for source '{ds['source']}' / format '{ds.get('format')}'.",
        }

    return JsonResponse({"results": results})


# ---------------------------------------------------------------------------
# Handler: PDOK WFS → _generic_import
# ---------------------------------------------------------------------------

def _handle_pdok_vector(ds, bbox=None):
    """
    Fetch a PDOK WFS layer, build a column mapping, and run _generic_import.
    """
    key = ds["key"]
    target_label = ds["target_model"]
    target_srid = int(ds["params"].get("srsName", "EPSG:28992").split(":")[-1])

    try:
        gdf = _fetch_pdok_wfs(ds, bbox=bbox)
    except Exception as e:
        logger.exception("WFS fetch failed for %s", key)
        return {
            "status": "error",
            "message": f"Failed to fetch data from PDOK: {e}",
        }

    # Log columns for debugging
    logger.info("Columns for %s: %s", key, list(gdf.columns))
    logger.info("CRS after fetch: %s", gdf.crs)
    if len(gdf) > 0:
        logger.info("Sample row:\n%s", gdf.iloc[0])
        # Sanity check: first geometry's bounds should be in RD New range
        bounds = gdf.geometry.iloc[0].bounds
        logger.info("First geometry bounds: %s", bounds)
        if bounds[0] < 0 or bounds[0] > 300000:
            logger.warning("Bounds look suspicious for EPSG:28992 — check CRS!")

    # Build column mapping
    spec = _get_model_spec(target_label)
    builder = COLMAP_BUILDERS.get(key)
    if builder:
        colmap = builder(gdf, spec)
    else:
        colmap = _auto_colmap(gdf, spec)

    if not colmap:
        return {
            "status": "error",
            "message": f"Could not map WFS columns {list(gdf.columns)} to model fields {spec['required']}.",
        }

    logger.info("Column mapping for %s: %s", key, colmap)

    # Run import
    try:
        report = _generic_import(
            gdf,
            target_label,
            colmap,
            dry_run=False,
            target_srid=target_srid,
        )
    except Exception as e:
        logger.exception("Import failed for %s", key)
        return {
            "status": "error",
            "message": f"Import failed: {e}",
        }

    return {
        "status": "success" if report["errors"] == 0 else "partial",
        "message": (
            f"Imported {report['created']} created, {report['updated']} updated, "
            f"{report['skipped']} skipped, {report['errors']} errors."
        ),
        "report": report,
    }


# ---------------------------------------------------------------------------
# Handler: WMS datasets — just store the layer reference
# ---------------------------------------------------------------------------

def _handle_wms_dataset(ds):
    """
    For WMS datasets we don't download raster tiles — we store the
    WMS endpoint URL and layer name so the frontend can display them.
    """
    target_label = ds["target_model"]

    # TODO: Create or update the WMS model instance with:
    #   url   = ds["url"]
    #   layer = ds["layer"]
    #   name  = ds["name"]

    return {
        "status": "skipped",
        "message": (
            f"WMS layer registered: {ds['layer']} @ {ds['url']}. "
            f"Target model: {target_label}. Actual save not yet implemented."
        ),
    }
