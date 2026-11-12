"""
Store a generated neighbourhood layout (builtup/calculations/generative.py) as
real streets, buildings and dwellings, or remove it again.

Called by housing/signals.py when a housing.HousingProject with a generated
layout is completed, changed or deleted (DAG edge New_Units -> Buildings);
builtup never imports housing, so the project arrives as plain values.

Land cover: the project's outline first becomes one urban-fabric polygon
(physicalEnv/calculations/landcover.py::project_area, Buildings -> LandCover
for all its buildings at once; a 10 m ring per building would re-cut its
neighbours hundreds of times). Then every row is written as a map-editor
change (core.editing.editor_change), so the existing receivers run as for a
hand-drawn object:
    Street   -> road surface cut out of the project polygon (Streets -> LandCover), canyons
    Building -> DSM patch (Buildings -> DSM), canyons, Degree of Urbanisation
                (no ring of its own: physicalEnv.signals.building_created skips source_project)
    Property -> residents (Household_Size -> Property)
and every row is journalled (core.editing.journal), so the editor's Restore
removes a generated layout like any other edit. All of it runs inside
importer.batching.deferred_cascades(), so the cascades run once per city.

Buildings get negative ids (editor objects, core.editing._next_negative_pk),
usage function woonfunctie, numberUnits, numberFloors, height_m and the
project's completion year; one Property per dwelling sits on the building's
point on surface with GFA / units as its gross area.

DAG edges: New_Units -> Buildings (the buildings and dwellings),
Streets -> Buildings (footprints fill the blocks the street layout leaves).
"""
import logging

from django.contrib.gis.geos import GEOSGeometry, MultiLineString, MultiPolygon
from django.db import transaction

logger = logging.getLogger(__name__)

DWELLING_CODE = "woonfunctie"
STREET_KEY = "builtup.Street"
BUILDING_KEY = "builtup.Building"
PROPERTY_KEY = "builtup.Property"


def _to_shapely(geom):
    from shapely import wkb
    return wkb.loads(bytes(geom.wkb))


def _to_geos(shape, srid, multi):
    geom = GEOSGeometry(memoryview(shape.wkb), srid=srid)
    if geom.geom_type != multi.__name__:
        geom = multi(geom, srid=srid)
    return geom


def _journal_if_backup():
    """core.editing.journal, or a no-op when there is no restore point (one query instead of one per row)."""
    from core.editing import active_backup, journal
    return journal if active_backup() is not None else (lambda *args, **kwargs: None)


def remove(project_id):
    """
    Delete the streets, buildings and dwellings generated for a project
    (journalled; the streets give their road surface back to the project
    polygon), then give the project polygon's land back
    (landcover.release_owner). Returns the number of rows deleted.
    """
    from core.editing import editor_change
    from importer.batching import deferred_cascades
    from physicalEnv.calculations.landcover import Owner, release_owner
    from ..models import Building, Property, Street

    journal = _journal_if_backup()
    deleted = 0
    with transaction.atomic(), deferred_cascades(), editor_change():
        properties = Property.objects.filter(building__source_project=project_id)
        for prop in properties:
            journal(PROPERTY_KEY, Property, prop.pk)
            prop.delete()
            deleted += 1
        for building in Building.objects.filter(source_project=project_id):
            journal(BUILDING_KEY, Building, building.pk)
            building.delete()
            deleted += 1
        for street in Street.objects.filter(source_project=project_id):
            journal(STREET_KEY, Street, street.pk)
            street.delete()
            deleted += 1
        release_owner(Owner("project", project_id))
    return deleted


def materialise(project_id, outline, params, name="Project", completion_year=None):
    """
    Replace the project's generated rows with a fresh layout of `outline`
    (GEOS polygon in the storage CRS, metres) and `params`
    (generative.resolve_params). The site check runs first
    (site.site_constraints): protected nature is cut out, and a site with a
    blocking finding raises ValueError before anything is written. Returns
    the layout's metrics plus the number of streets, buildings and dwellings
    written, and the site check summary.

    DAG edges: New_Units -> Buildings, Streets -> Buildings
    """
    from administrative.models import City
    from core.editing import _next_negative_pk, editor_change
    from importer.batching import deferred_cascades
    from physicalEnv.calculations.landcover import project_area
    from ..models import Building, Property, Street
    from . import generative
    from .site import site_constraints

    if outline.srs is not None and outline.srs.geographic:
        raise ValueError("The neighbourhood generator needs a metric storage CRS (COORDINATE_SYSTEM)")
    srid = outline.srid
    site = site_constraints(outline)
    if site.blocked:
        raise ValueError("; ".join(f["message"] for f in site.findings if f["severity"] == "block"))
    buildable = site.buildable
    layout = generative.generate(_to_shapely(outline), params, buildable=_to_shapely(buildable))

    journal = _journal_if_backup()
    counts = {"streets": 0, "buildings": 0, "dwellings": 0}
    with transaction.atomic(), deferred_cascades(), editor_change():
        remove(project_id)
        city_id = City.objects.filter(geom__intersects=outline.point_on_surface).values_list("pk", flat=True).first()
        if city_id:
            project_area(_to_geos(_to_shapely(buildable), srid, MultiPolygon), city_id, project_id, footprint_m2=layout.metrics["footprint_m2"], name=name)
        for i, line in enumerate(layout.streets, start=1):
            street = Street(
                name=f"{name} street {i}"[:100],
                classification="residential",
                width=layout.params["street_width"],
                source_project=project_id,
                geom=_to_geos(line, srid, MultiLineString),
            )
            street.save()
            journal(STREET_KEY, Street, street.pk, created=True)
            counts["streets"] += 1

        next_pk = _next_negative_pk(Building)
        for i, spec in enumerate(layout.buildings, start=1):
            footprint = _to_geos(spec["geom"], srid, MultiPolygon)
            building = Building(
                id=next_pk,
                name=f"{name} {spec['typology']} {i}"[:100],
                usageFunction=[DWELLING_CODE],
                buildingType="residential",
                numberUnits=spec["units"],
                numberFloors=spec["floors"],
                height_m=spec["height_m"],
                constructionYear=completion_year,
                source_project=project_id,
                geom=footprint,
            )
            building.save(force_insert=True)
            journal(BUILDING_KEY, Building, building.pk, created=True)
            next_pk -= 1
            counts["buildings"] += 1

            point = footprint.point_on_surface
            gross = spec["geom"].area * spec["floors"] / spec["units"]
            for unit in range(1, spec["units"] + 1):
                # Flats are spread over the floors in order (floor 0 = ground floor).
                floor = (unit - 1) * spec["floors"] // spec["units"]
                label = f"unit {unit}" if spec["units"] == 1 else f"floor {floor} unit {unit}"
                prop = Property(
                    name=f"{building.name} {label}"[:100],
                    building=building,
                    usageFunction=[DWELLING_CODE],
                    grossArea=round(gross, 1),
                    geom=point,
                )
                prop.save()
                if prop.building_id != building.pk:
                    # Property.save() takes the first building containing the point;
                    # an older building under the new footprint must not claim the dwelling.
                    Property.objects.filter(pk=prop.pk).update(building=building)
                journal(PROPERTY_KEY, Property, prop.pk, created=True)
                counts["dwellings"] += 1
    logger.info("Neighbourhood generator: project %s -> %s", project_id, counts)
    return {**layout.metrics, **counts, "params": layout.params, "site_check": site.summary}
