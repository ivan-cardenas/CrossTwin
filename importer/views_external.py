"""
views_external.py
=================
View for the External Data Import page.
Add this to your existing views.py or import from it.
"""
import json
import logging

from django.shortcuts import render, redirect
from django.urls import reverse
from django.contrib import messages as django_messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from .external_data import (
    EXTERNAL_DATA_CATALOG,
    CATALOG_BY_KEY,
    SOURCE_INFO,
    get_catalog_grouped,
    import_dataset,
)

logger = logging.getLogger(__name__)


def get_external_data(request):
    """
    Render the External Data catalog page.
    Users tick datasets they want, then POST to start the import.
    """
    catalog_grouped = get_catalog_grouped()

    # Build template-friendly structure
    sources = []
    for src_key in ["pdok", "sentinel2", "gee"]:
        info = SOURCE_INFO[src_key]
        categories = []
        for cat_name, datasets in catalog_grouped.get(src_key, {}).items():
            categories.append({
                "name": cat_name,
                "datasets": datasets,
            })
        # Sort categories alphabetically
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
                "source": d["source"],
                "format": d.get("format", "wfs"),
                "requires_bbox": d.get("requires_bbox", False),
                "requires_auth": d.get("requires_auth", False),
                "requires_date_range": d.get("requires_date_range", False),
                "enabled": d.get("enabled", True),
            } for d in EXTERNAL_DATA_CATALOG}
        ),
    }
    return render(request, "importer/external_data.html", context)


@require_POST
def start_external_import(request):
    """
    Receives the list of selected dataset keys via POST,
    validates them, and kicks off imports.
    Returns JSON for the async progress UI.
    """
    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    selected_keys = body.get("datasets", [])
    bbox = body.get("bbox", None)  # [xmin, ymin, xmax, ymax] in EPSG:28992
    gee_credentials = body.get("gee_credentials", None)  # Service account JSON string
    sentinel_token = body.get("sentinel_token", None)  # Copernicus token (future)
    date_from = body.get("date_from", None)  # YYYY-MM-DD
    date_to = body.get("date_to", None)  # YYYY-MM-DD

    if not selected_keys:
        return JsonResponse({"error": "No datasets selected."}, status=400)

    # Validate keys
    invalid = [k for k in selected_keys if k not in CATALOG_BY_KEY]
    if invalid:
        return JsonResponse({"error": f"Unknown datasets: {', '.join(invalid)}"}, status=400)

    # Check if any GEE dataset is selected but no credentials provided
    gee_selected = any(
        CATALOG_BY_KEY[k]["source"] == "gee" 
        for k in selected_keys 
        if k in CATALOG_BY_KEY
    )
    if gee_selected and not gee_credentials:
        return JsonResponse({
            "error": "Google Earth Engine datasets require authentication. Please paste your service account JSON."
        }, status=400)

    results = {}
    for key in selected_keys:
        ds = CATALOG_BY_KEY[key]

        # Run the import
        result = import_dataset(
            dataset_key=key,
            bbox=bbox,
            date_from=date_from,
            date_to=date_to,
            gee_credentials=gee_credentials,
            sentinel_token=sentinel_token,
        )

        results[key] = result.to_dict()
        
        # Log the result
        if result.status == "success":
            logger.info(f"Successfully imported {key}: {result.message}")
        elif result.status == "error":
            logger.error(f"Failed to import {key}: {result.message}")

    return JsonResponse({"results": results})
