"""
views_external.py
=================
View for the External Data Import page.
Renders the catalog UI and dispatches imports via external_data.import_dataset.
"""
import json
import logging

from django.apps import apps
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
    source_order = ["pdok", "CBS", "sentinel2", "gee", "rivm"]

    sources_present = {ds["source"] for datasets in catalog_grouped.values() for ds in datasets}
    all_sources = [
        {"key": src_key, "info": SOURCE_INFO[src_key]}
        for src_key in source_order
        if src_key in sources_present
    ]

    # Datasets keep the source's display name and icon alongside them (used
    # to be a separate per-source sub-section; now it's just a line on the
    # dataset row — see the template) rather than mutating the catalog's own
    # dicts, which are shared module-level state reused across requests.
    def with_source_info(ds):
        return {**ds, "source_label": SOURCE_INFO[ds["source"]]["name"], "source_icon": SOURCE_INFO[ds["source"]]["icon"]}

    categories = []
    for cat_name in sorted(catalog_grouped.keys()):
        datasets = sorted(
            catalog_grouped[cat_name],
            key=lambda ds: source_order.index(ds["source"]) if ds["source"] in source_order else len(source_order),
        )
        categories.append({
            "name": cat_name,
            "datasets": [with_source_info(ds) for ds in datasets],
            "dataset_count": len(datasets),
        })

    context = {
        "categories": categories,
        "all_sources": all_sources,
        "mapbox_access_token": settings.MAPBOX_ACCESS_TOKEN,
        "coordinate_system": settings.COORDINATE_SYSTEM,
        "catalog_json": json.dumps(
            {d["key"]: {
                "name": d["name"],
                "source": d["source"],
                "target_model": d["target_model"],
                "requires_bbox": d.get("requires_bbox", False),
                "draw_bbox": d.get("draw_bbox", False),
                "requires_auth": d.get("requires_auth", False),
                "requires_date_range": d.get("requires_date_range", False),
                "enabled": d.get("enabled", True),
                "slow": d.get("slow", False),
                "slow_reason": d.get("slow_reason", ""),
            } for d in EXTERNAL_DATA_CATALOG}
        ),
    }
    return render(request, "importer/external_data.html", context)


def get_cities_geojson(request):
    """
    Return all cities from common.City as a GeoJSON FeatureCollection in WGS84.
    Used by the external data import map so the user can click a city to set the
    area of interest (bbox) instead of drawing a rectangle manually.
    """
    from common.models import City

    features = []
    for city in City.objects.only('id', 'cityName', 'geom'):
        try:
            geom_wgs84 = city.geom.transform(4326, clone=True)
            # extent → (xmin, ymin, xmax, ymax) = (west, south, east, north) in WGS84
            bbox = list(geom_wgs84.extent)
            features.append({
                'type': 'Feature',
                'geometry': json.loads(geom_wgs84.geojson),
                'properties': {
                    'id': city.id,
                    'name': city.cityName,
                    'bbox': bbox,
                },
            })
        except Exception as e:
            logger.warning(f"Skipping city {city.id} ({city.cityName}) from GeoJSON: {e}")

    return JsonResponse({'type': 'FeatureCollection', 'features': features})


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
    openeo_client_id = body.get("openeo_client_id", None)
    openeo_client_secret = body.get("openeo_client_secret", None)
    date_from = body.get("date_from", None)
    date_to = body.get("date_to", None)

    if not selected_keys:
        return JsonResponse({"error": "No datasets selected."}, status=400)

    invalid = [k for k in selected_keys if k not in CATALOG_BY_KEY]
    if invalid:
        return JsonResponse({"error": f"Unknown datasets: {', '.join(invalid)}"}, status=400)

    results = {}

    for key in selected_keys:
        # Check that required prerequisite model has records before importing
        ds = CATALOG_BY_KEY[key]
        req_model_path = ds.get("requires_model")
        if req_model_path:
            try:
                app_label, model_name = req_model_path.split(".")
                ReqModel = apps.get_model(app_label, model_name)
                if not ReqModel.objects.exists():
                    results[key] = {
                        "status": "error",
                        "message": (
                            f"No {model_name} records found in the database. "
                            f"Please import or upload {model_name} data first."
                        ),
                    }
                    continue
            except LookupError:
                pass  # model not registered yet — let the import attempt and fail naturally

        result = import_dataset(
            dataset_key=key,
            bbox=bbox,
            date_from=date_from,
            date_to=date_to,
            gee_credentials=gee_credentials,
            openeo_client_id=openeo_client_id,
            openeo_client_secret=openeo_client_secret,
        )
        results[key] = result.to_dict()

    return JsonResponse({"results": results})
