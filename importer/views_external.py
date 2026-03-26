"""
views_external.py
=================
View for the External Data Import page.
Renders the catalog UI and dispatches imports via external_data.import_dataset.
"""
import json
import logging

from django.conf import settings
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from .external_catalog import (
    EXTERNAL_DATA_CATALOG,
    CATALOG_BY_KEY,
    SOURCE_INFO,
    get_catalog_grouped,
)
from .external_data import import_dataset

logger = logging.getLogger(__name__)


def get_external_data(request):
    """
    Render the External Data catalog page.
    Users tick datasets they want, then POST to start the import.
    """
    catalog_grouped = get_catalog_grouped()

    sources = []
    for src_key in ["pdok", "CBS", "sentinel2", "gee"]:
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
        "mapbox_access_token": settings.MAPBOX_ACCESS_TOKEN,
        "coordinate_system": settings.COORDINATE_SYSTEM,
        "catalog_json": json.dumps(
            {d["key"]: {
                "name": d["name"],
                "source": d["source"],
                "target_model": d["target_model"],
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
    Receives selected dataset keys via POST JSON, fetches data, imports it.
    Dispatches each dataset to external_data.import_dataset().
    """
    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    selected_keys = body.get("datasets", [])
    bbox = body.get("bbox", None)
    gee_credentials = body.get("gee_credentials", None)
    sentinel_token = body.get("sentinel_token", None)
    date_from = body.get("date_from", None)
    date_to = body.get("date_to", None)

    if not selected_keys:
        return JsonResponse({"error": "No datasets selected."}, status=400)

    invalid = [k for k in selected_keys if k not in CATALOG_BY_KEY]
    if invalid:
        return JsonResponse({"error": f"Unknown datasets: {', '.join(invalid)}"}, status=400)

    results = {}

    for key in selected_keys:
        result = import_dataset(
            dataset_key=key,
            bbox=bbox,
            date_from=date_from,
            date_to=date_to,
            gee_credentials=gee_credentials,
            sentinel_token=sentinel_token,
        )
        results[key] = result.to_dict()

    return JsonResponse({"results": results})
