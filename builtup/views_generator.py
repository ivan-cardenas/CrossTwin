"""
Map card for the neighbourhood generator (core/static/js/GeneratorTool.js).

GET  /builtup/generator/projects/   housing projects with their outline and stored parameters (open)
POST /builtup/generator/preview/    layout of an outline + parameters as GeoJSON; never writes (what-if)
POST /builtup/generator/commit/     store the layout on a housing project, completed (staff)
POST /builtup/generator/remove/     set a project back to planned, removing its generated rows (staff)

Bodies are JSON: {"outline": <GeoJSON geometry, WGS84>, "params": {...},
"project_id": <id or null>, "name": "...", "year_expected_completion": 2030}.
Geometry: builtup/calculations/generative.py; storage: housing/signals.py ->
builtup/calculations/materialise.py.
"""
import json

from django.conf import settings
from django.contrib.gis.geos import GEOSGeometry, MultiPolygon
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

PROJECT_KEY = "housing.HousingProject"
# Largest outline the preview accepts (km²): keeps a request well under a second.
MAX_OUTLINE_KM2 = 4.0


def _json(data, status=200):
    return JsonResponse(data, status=status, json_dumps_params={"default": str})


def _body(request):
    try:
        return json.loads(request.body or b"{}")
    except ValueError as exc:
        raise ValueError(f"Invalid JSON body: {exc}")


def _outline(data):
    """The request's outline in the storage CRS (MultiPolygon), checked for size."""
    raw = data.get("outline")
    if not raw:
        raise ValueError("Draw an outline or pick a housing project first.")
    geom = GEOSGeometry(json.dumps(raw) if isinstance(raw, dict) else raw, srid=4326)
    if geom.geom_type == "Polygon":
        geom = MultiPolygon(geom, srid=4326)
    if geom.geom_type != "MultiPolygon":
        raise ValueError("The outline must be a polygon.")
    geom.transform(settings.COORDINATE_SYSTEM)
    if not geom.valid:
        geom = geom.buffer(0)
        if geom.geom_type == "Polygon":
            geom = MultiPolygon(geom, srid=settings.COORDINATE_SYSTEM)
    if geom.srs and geom.srs.geographic:
        raise ValueError("The neighbourhood generator needs a metric COORDINATE_SYSTEM.")
    if geom.area / 1e6 > MAX_OUTLINE_KM2:
        raise ValueError(f"The outline is {geom.area / 1e6:.1f} km²; the generator takes at most {MAX_OUTLINE_KM2:g} km².")
    return geom


def _feature(shape, srid, kind, **props):
    geom = GEOSGeometry(memoryview(shape.wkb), srid=srid)
    geom.transform(4326)
    return {"type": "Feature", "geometry": json.loads(geom.geojson), "properties": {"kind": kind, **props}}


def _project_json(project):
    geom = project.geom.transform(4326, clone=True)
    return {
        "id": project.pk,
        "name": project.project_name,
        "status": project.status,
        "units": project.project_units,
        "year_expected_completion": project.year_expected_completion,
        "params": project.generator_params,
        "outline": json.loads(geom.geojson),
    }


@require_GET
def generator_projects(request):
    from housing.models import HousingProject

    projects = [_project_json(p) for p in HousingProject.objects.order_by("project_name", "pk")]
    return _json({"projects": projects, "can_commit": request.user.is_staff})


@require_POST
def generator_preview(request):
    """
    What-if: the site check, the generated layout on the buildable part, its
    metrics and the regulation findings. Writes nothing (DAG rule 8).
    """
    from shapely import wkb
    from shapely.geometry import Polygon

    from .calculations import generative, regulations
    from .calculations.site import site_constraints

    try:
        data = _body(request)
        outline = _outline(data)
        site = site_constraints(outline)
        shape = lambda g: wkb.loads(bytes(g.wkb))
        layout = generative.generate(shape(outline), data.get("params"),
                                     buildable=Polygon() if site.buildable.empty else shape(site.buildable))
    except ValueError as exc:
        return _json({"error": str(exc)}, status=400)
    srid = outline.srid
    site_features = []
    if site.excluded is not None and not site.excluded.empty:
        site_features.append(_feature(shape(site.excluded), srid, "excluded"))
    site_features += [_feature(shape(geom), srid, "warning", label=label) for geom, label in site.warned if not geom.empty]
    features = (
        [_feature(b, srid, "block") for b in layout.blocks]
        + [_feature(p, srid, "plot") for p in layout.plots]
        + [_feature(s, srid, "street", width=layout.params["street_width"]) for s in layout.streets]
        + [_feature(b["geom"], srid, "building", height_m=b["height_m"], floors=b["floors"], units=b["units"],
                    typology=b["typology"])
           for b in layout.buildings]
    )
    return _json({
        "layout": {"type": "FeatureCollection", "features": site_features + features},
        "metrics": layout.metrics,
        "params": layout.params,
        "site": {"findings": site.findings, "blocked": site.blocked},
        "regulations": regulations.check(layout.buildings, layout.params["unit_gfa_m2"]),
    })


@require_POST
def generator_commit(request):
    """
    Save the outline + parameters on a housing project (new or existing) as
    completed; housing/signals.py then stores the layout
    (DAG edge New_Units -> Buildings). Journalled for the editor's Restore.
    Refused (400) when the site check blocks; its summary is stored in
    generator_params["site_check"]. A failing layout rolls the project back.
    """
    if not request.user.is_staff:
        return _json({"error": "Log in as a staff user to store a generated neighbourhood."}, status=403)
    from administrative.models import Neighborhood
    from core.editing import editor_change, journal
    from housing.models import HousingProject

    from django.db import transaction

    from .calculations import generative
    from .calculations.site import site_constraints

    try:
        data = _body(request)
        outline = _outline(data)
        params = generative.resolve_params(data.get("params"))
    except ValueError as exc:
        return _json({"error": str(exc)}, status=400)
    site = site_constraints(outline)
    if site.blocked:
        reasons = "; ".join(f["message"] for f in site.findings if f["severity"] == "block")
        return _json({"error": f"Cannot build here: {reasons}", "site": {"findings": site.findings, "blocked": True}},
                     status=400)
    params["site_check"] = site.summary

    project_id = data.get("project_id")
    project = HousingProject.objects.filter(pk=project_id).first() if project_id else None
    if project_id and project is None:
        return _json({"error": f"Housing project {project_id} does not exist."}, status=404)
    neighborhood = Neighborhood.objects.filter(geom__contains=outline.point_on_surface).first()
    if project is None and neighborhood is None:
        return _json({"error": "The outline lies outside every stored neighbourhood."}, status=400)

    class LayoutFailed(Exception):
        pass

    creating = project is None
    try:
        with transaction.atomic():
            if creating:
                project = HousingProject(year=timezone.now().year)
            else:
                journal(PROJECT_KEY, HousingProject, project.pk)
            project.neighborhood = neighborhood or project.neighborhood
            project.project_name = (data.get("name") or project.project_name or "Generated neighbourhood")[:100]
            project.year_expected_completion = int(data.get("year_expected_completion")
                                                   or project.year_expected_completion or timezone.now().year)
            project.geom = outline
            project.project_area = outline.area
            project.status = "completed"
            project.generator_params = params
            if params.get("target_units"):
                project.project_units = int(params["target_units"])
            elif not project.project_units:
                project.project_units = 0
            with editor_change():
                project.save()
            if creating:
                journal(PROJECT_KEY, HousingProject, project.pk, created=True)
            if getattr(project, "_layout_error", None):
                raise LayoutFailed(project._layout_error)
    except LayoutFailed as exc:
        return _json({"error": f"Nothing was stored: the layout failed ({exc})."}, status=500)
    result = getattr(project, "_layout_result", None) or {}
    return _json({"project": _project_json(project), "result": {k: v for k, v in result.items() if k != "params"}})


@require_POST
def generator_remove(request):
    """Set a project back to planned: its generated streets, buildings and dwellings are deleted (journalled)."""
    if not request.user.is_staff:
        return _json({"error": "Log in as a staff user to remove a generated neighbourhood."}, status=403)
    from core.editing import editor_change, journal
    from housing.models import HousingProject

    try:
        data = _body(request)
    except ValueError as exc:
        return _json({"error": str(exc)}, status=400)
    project = HousingProject.objects.filter(pk=data.get("project_id")).first()
    if project is None:
        return _json({"error": "Pick a housing project."}, status=404)
    journal(PROJECT_KEY, HousingProject, project.pk)
    project.status = "planned"
    with editor_change():
        project.save()
    error = getattr(project, "_layout_error", None)
    if error:
        return _json({"error": error}, status=500)
    return _json({"project": _project_json(project)})
