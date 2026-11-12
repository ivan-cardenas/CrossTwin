import logging
import threading
from contextlib import contextmanager

from django.db import connection, transaction
from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.db.models import Max, Q
from django.utils import timezone

from core.cache import bump_layer_version
from .calculations.dsm_patches import (DEFAULT_FOREST_CANOPY_M, building_height, record_change,
                          record_vegetation_change, tree_crown, tree_height)
from .calculations.dsm_edited import schedule_refresh as schedule_dsm_refresh
from .calculations.landcover import (green_area, refresh_percentages, release_green_area, release_ring, release_street,
                                     street_area, urbanize_around)
from .models import (DigitalSurfaceModel, DSMBuildingPatch, DSMEdit, DSMVegetationPatch, LandCoverClasses, LandCoverVector,
                     SatelliteImagery)
from builtup.models import Building, Street
from nature.models import Forests, GreenSpaces, Tree
from administrative.models import Neighborhood, District, City, Province
# Reused from administrative's own population cascade rather than
# duplicated -- see administrative/signals.py for the shared aggregation
# logic this re-enters after writing Neighborhood.urban_area below.
from administrative.signals import _recompute_population

logger = logging.getLogger(__name__)

URBAN_AREA_KEYWORDS = ["urban fabric", "road", "rail", "transport"]

# Per-thread set of city ids whose recompute is postponed; None when not deferring.
_deferred = threading.local()


def _urban_area_filter():
    """Q object: land_cover_type.class_name case-insensitively contains
    any of URBAN_AREA_KEYWORDS. class_name is a free-form lookup value
    populated at import time (see importer/external_catalog.py's
    pdok_landcover_brt entry), not a fixed enum, so substring matching is
    used rather than exact equality -- matching the same convention as
    mainMap/styles/landCoverStyles.py's KEYWORD_COLORS. The set-based SQL in
    _recompute_neighborhood_urban_area applies the same rule as
    `class_name ILIKE ANY(...)`."""
    q = Q()
    for kw in URBAN_AREA_KEYWORDS:
        q |= Q(land_cover_type__class_name__icontains=kw)
    return q


def _area_sql(expr):
    """ST_Area in m²: planar for a projected storage CRS (RD New), geography for a geodetic one."""
    if LandCoverVector._meta.get_field("geom").geodetic(connection):
        return f"ST_Area(({expr})::geography)"
    return f"ST_Area({expr})"


def _recompute_neighborhood_urban_area(city_id):
    """
    Recompute urban_area for every Neighborhood under city_id, from the
    most recent LandCoverVector year available for that city, then
    manually re-enter administrative/signals.py's population/urban_area
    cascade. The UPDATE below does not fire post_save, so nothing else will
    push this change up to District/City/Province.

    One set-based statement for all neighborhoods of the city (instead of an
    Intersection aggregate + UPDATE per neighborhood). Land-cover polygons
    that lie entirely inside a neighborhood contribute their own area; only
    the ones crossing its boundary are clipped with ST_Intersection. The
    cascade then runs once per district and once for the city and province,
    not once per district all the way up. See docs/PERFORMANCE.md §2.
    """
    latest_year = LandCoverVector.objects.filter(city_id=city_id).aggregate(
        latest=Max('year')
    )['latest']
    # No LandCoverVector rows left for this city (e.g. the last one was just
    # deleted) -- don't bail out early, still recompute so existing
    # Neighborhoods reset to 0.0 instead of keeping a stale value. A NULL
    # year matches no land cover, so every neighborhood gets 0.

    neighborhoods = Neighborhood._meta.db_table
    districts = District._meta.db_table
    landcover = LandCoverVector._meta.db_table
    classes = LandCoverClasses._meta.db_table
    area_inside = _area_sql("l.geom")
    area_clipped = _area_sql("ST_Intersection(l.geom, h.geom)")

    sql = f"""
        WITH hood AS (
            SELECT n.id, n.district_id, n.geom
            FROM "{neighborhoods}" n
            JOIN "{districts}" d ON d.id = n.district_id
            WHERE d.city_id = %(city)s
        ), urban AS (
            SELECT h.id,
                   SUM(CASE WHEN ST_Within(l.geom, h.geom) THEN {area_inside}
                            ELSE {area_clipped} END) AS area_m2
            FROM hood h
            JOIN "{landcover}" l ON l.geom && h.geom AND ST_Intersects(l.geom, h.geom)
            JOIN "{classes}" c ON c.id = l.land_cover_type_id
            WHERE l.city_id = %(city)s
              AND l.year = %(year)s
              AND c.class_name ILIKE ANY(%(patterns)s)
            GROUP BY h.id
        )
        UPDATE "{neighborhoods}" n
        SET urban_area = COALESCE(urban.area_m2, 0) / 1e6,
            last_updated = %(now)s
        FROM hood
        LEFT JOIN urban ON urban.id = hood.id
        WHERE n.id = hood.id
        RETURNING hood.district_id
    """
    with connection.cursor() as cursor:
        cursor.execute(sql, {
            "city": city_id,
            "year": latest_year,
            "patterns": [f"%{kw}%" for kw in URBAN_AREA_KEYWORDS],
            "now": timezone.now(),
        })
        district_ids = {row[0] for row in cursor.fetchall()}

    if not district_ids:
        return
    bump_layer_version(Neighborhood)

    city_pk = None
    for district_id in district_ids:
        city_pk = _recompute_population(
            District, district_id,
            child_model=Neighborhood, child_fk='district_id', parent_fk='city_id',
        ) or city_pk
    if not city_pk:
        return
    province_pk = _recompute_population(
        City, city_pk,
        child_model=District, child_fk='city_id', parent_fk='province_id',
    )
    if province_pk:
        _recompute_population(Province, province_pk, child_model=City, child_fk='province_id')


@contextmanager
def deferred_urban_area():
    """
    Postpone the urban-area recompute until the block ends, then run it once
    per affected city. A bulk land-cover import otherwise re-runs the whole
    per-city recompute for every polygon it saves (N polygons x M
    neighborhoods of work). Nested uses defer to the outermost one.
    """
    if getattr(_deferred, "cities", None) is not None:
        yield
        return

    _deferred.cities = set()
    try:
        yield
    except BaseException:
        cities, _deferred.cities = _deferred.cities, None
        try:
            for city_id in cities:
                _recompute_neighborhood_urban_area(city_id)
        except Exception:
            # e.g. the transaction is already broken; don't mask the original error
            logger.exception("Deferred urban-area recompute failed after an aborted block")
        raise
    else:
        cities, _deferred.cities = _deferred.cities, None
        for city_id in cities:
            _recompute_neighborhood_urban_area(city_id)


def schedule_urban_area_recompute(city_id):
    """Recompute a city's urban area now, or at the end of the enclosing deferred_urban_area()."""
    if not city_id:
        return
    cities = getattr(_deferred, "cities", None)
    if cities is not None:
        cities.add(city_id)
    else:
        _recompute_neighborhood_urban_area(city_id)


@receiver(pre_save, sender=LandCoverVector, dispatch_uid="physicalEnv_landcover_percentage")
def landcover_percentage(sender, instance, raw=False, **kwargs):
    """
    percentage = polygon area / its City's area_km2 * 100, for every save
    (file upload, admin, map editor), so it no longer depends on the import
    path setting it. A pre_save receiver rather than a save() override:
    LandCoverVector is bulk-written (importer/batching.py), and the bulk
    finalizer refreshes the same value set-based (refresh_percentages).
    Without a city (or a city without area) the given value is kept.
    Raw saves (fixtures, map-editing Restore) keep the stored value.
    """
    if raw or instance.geom is None or not instance.city_id:
        return
    city_km2 = City.objects.filter(pk=instance.city_id).values_list("area_km2", flat=True).first()
    if city_km2:
        if instance.geom.srid != City._meta.get_field("geom").srid:
            geom = instance.geom.transform(City._meta.get_field("geom").srid, clone=True)
        else:
            geom = instance.geom
        # Same planar area as City.area_km2 (geom.area in the storage CRS)
        instance.percentage = geom.area / 1e6 / city_km2 * 100


@receiver(pre_save, sender=LandCoverVector, dispatch_uid="physicalEnv_landcover_albedo")
def landcover_albedo(sender, instance, raw=False, **kwargs):
    """
    Albedo bookkeeping on every save (physicalEnv/calculations/albedo.py):
    - no material: the class's default material (its albedo is the polygon's
      default, LandCoverVector.effective_albedo);
    - a changed geometry drops a measured albedo: the satellite saw the old
      shape, so the class default applies until the next measurement.
    Raw saves (fixtures, map-editing Restore) keep the stored values.
    """
    if raw:
        return
    if instance.material_id is None and instance.land_cover_type_id:
        instance.material_id = (LandCoverClasses.objects.filter(pk=instance.land_cover_type_id)
                                .values_list("default_material_id", flat=True).first())
    if instance.pk is not None and instance.albedo is not None and instance.geom is not None:
        stored = LandCoverVector.objects.filter(pk=instance.pk).values_list("geom", flat=True).first()
        if stored is not None and not stored.equals_exact(instance.geom, tolerance=1e-6):
            instance.albedo = instance.albedo_source = instance.albedo_date = None


@receiver(post_save, sender=SatelliteImagery, dispatch_uid="physicalEnv_albedo_imagery_saved")
def albedo_imagery_saved(sender, instance, raw=False, **kwargs):
    """
    DAG edge: RS_Imagery -> LandCover (albedo attribute). A saved Sentinel-2
    ALBEDO raster writes its zonal mean onto the land-cover polygons it
    covers (albedo.measure). A failure never blocks the import.
    """
    from .calculations.albedo import ALBEDO_INDEX, measure
    if raw or (instance.index or "").upper() != ALBEDO_INDEX or instance.raster is None:
        return
    _guarded(lambda: measure(instance), f"Albedo from imagery {instance.pk}")


@receiver(pre_save, sender=City, dispatch_uid="physicalEnv_city_area_presave")
def city_area_presave(sender, instance, raw=False, **kwargs):
    """Remember the stored area so city_area_saved only refreshes when the boundary changed."""
    instance._old_area_km2 = (None if raw or instance.pk is None else
                              City.objects.filter(pk=instance.pk).values_list("area_km2", flat=True).first())


@receiver(post_save, sender=City, dispatch_uid="physicalEnv_city_area_saved")
def city_area_saved(sender, instance, created, raw=False, **kwargs):
    """A changed city area changes every land-cover percentage of the city."""
    if raw or created or getattr(instance, "_old_area_km2", None) == instance.area_km2:
        return
    refresh_percentages(instance.pk)


@receiver(post_save, sender=LandCoverVector, dispatch_uid="landcover_save_to_neighborhood_urban_area")
@receiver(post_delete, sender=LandCoverVector, dispatch_uid="landcover_delete_to_neighborhood_urban_area")
def landcover_changed(sender, instance, **kwargs):
    # Bulk imports wrap their writes in deferred_urban_area() (see
    # importer/batching.py), so this recomputes once per city per import
    # instead of once per saved polygon.
    schedule_urban_area_recompute(instance.city_id)


def _city_of(building):
    """City of a building: through its neighborhood (Building.save() sets it), else the city containing its centroid."""
    if building.neighborhood_id:
        city_id = (Neighborhood.objects.filter(pk=building.neighborhood_id)
                   .values_list("district__city_id", flat=True).first())
        if city_id:
            return city_id
    return City.objects.filter(geom__contains=building.geom.centroid).values_list("pk", flat=True).first()


def _is_editor_building(instance):
    """Drawn in the map editor: negative id (core/editing.py::_next_negative_pk)."""
    return instance.pk is not None and instance.pk < 0


def _urbanize(instance):
    city_id = _city_of(instance)
    if not city_id:
        return
    land_use = instance.get_buildingType_display() if instance.buildingType else "Built-up"
    roof = instance.roofMaterial if instance.roofMaterial_id else None
    urbanize_around(instance.geom, city_id, land_use=land_use, building_id=instance.pk, roof_material=roof)


def _guarded(step, what):
    """Run one side effect in its own savepoint; a failure never blocks the building's save."""
    try:
        with transaction.atomic():
            step()
    except Exception:
        logger.exception("%s failed", what)


def _land_cover_step(instance, step, action):
    _guarded(step, f"Urban-fabric buffer {action} for building {instance.pk}")


@receiver(pre_save, sender=Building, dispatch_uid="physicalEnv_building_presave")
def building_presave(sender, instance, raw=False, **kwargs):
    """
    Remember the stored footprint and height of a building the editor
    changes, so post_save can tell a move or a new height from an attribute
    edit (land-cover ring, DSM patch).
    """
    from core.editing import is_editor_change
    if raw or not (_is_editor_building(instance) or is_editor_change()):
        return
    stored = Building.objects.filter(pk=instance.pk).values("geom", "height_m", "numberFloors").first()
    instance._stored = stored
    instance._stored_geom = stored["geom"] if stored else None


@receiver(post_save, sender=Building, dispatch_uid="physicalEnv_building_saved")
def building_created(sender, instance, created, raw=False, **kwargs):
    """
    DAG edge: Buildings -> LandCover. A building drawn in the map editor
    turns a BUILDING_BUFFER_M buffer around it into urban fabric
    (landcover.urbanize_around); moving it gives the old ring's land back
    (landcover.release_ring) and urbanizes around the new footprint. Only
    editor buildings (negative id): BAG imports already match the land
    cover, and an attribute-only edit leaves it alone. Buildings of a
    generated neighbourhood (source_project) get no ring: the project's
    outline is their urban fabric (landcover.project_area).
    """
    if raw or not _is_editor_building(instance) or not instance.geom or instance.source_project is not None:
        return
    if created:
        _land_cover_step(instance, lambda: _urbanize(instance), "creation")
        return
    stored = getattr(instance, "_stored_geom", None)
    if stored is not None and stored.equals_exact(instance.geom, tolerance=1e-6):
        return

    def move():
        release_ring(instance.pk)
        _urbanize(instance)
    _land_cover_step(instance, move, "move")


@receiver(post_delete, sender=Building, dispatch_uid="physicalEnv_building_deleted")
def building_deleted(sender, instance, **kwargs):
    """
    DAG edge: Buildings -> LandCover (inverse). Deleting an editor building
    gives its ring's land back to the polygons it was cut from. Skipped while
    the editor's backup restore runs: it puts the land-cover rows back itself.
    """
    from core.editing import is_restoring
    if not _is_editor_building(instance) or is_restoring() or instance.source_project is not None:
        return
    _land_cover_step(instance, lambda: release_ring(instance.pk), "release")


@receiver(pre_save, sender=GreenSpaces, dispatch_uid="physicalEnv_green_space_presave")
def green_space_presave(sender, instance, raw=False, **kwargs):
    """Remember the stored outline of a green space the editor changes, so post_save can tell a move from an attribute edit."""
    from core.editing import is_editor_change
    if raw or not is_editor_change() or instance.pk is None:
        return
    instance._stored_geom = GreenSpaces.objects.filter(pk=instance.pk).values_list("geom", flat=True).first()


def _green(instance):
    city_id = instance.city_id or _city_of(instance)
    if city_id:
        green_area(instance.geom, city_id, instance.pk, name=instance.name, vegetation_type=instance.vegetationType)


@receiver(post_save, sender=GreenSpaces, dispatch_uid="physicalEnv_green_space_saved")
def green_space_saved(sender, instance, created, raw=False, **kwargs):
    """
    DAG edge: New_Green_Area -> LandCover. A green space (a park is one of
    type 'park') drawn or reshaped in the map editor turns its outline into
    green urban area in the city's latest land cover (landcover.green_area);
    a move first gives the old area back (release_green_area). Imports and
    raw saves are skipped, and an attribute-only edit leaves the land cover alone.
    """
    from core.editing import is_editor_change
    if raw or not is_editor_change() or not instance.geom:
        return
    if created:
        _guarded(lambda: _green(instance), f"Green area for green space {instance.pk}")
        return
    stored = getattr(instance, "_stored_geom", None)
    if stored is not None and stored.equals_exact(instance.geom, tolerance=1e-6):
        return

    def move():
        release_green_area(instance.pk)
        _green(instance)
    _guarded(move, f"Green area move for green space {instance.pk}")


@receiver(post_delete, sender=GreenSpaces, dispatch_uid="physicalEnv_green_space_deleted")
def green_space_deleted(sender, instance, **kwargs):
    """
    DAG edge: New_Green_Area -> LandCover (inverse). Deleting a green space in
    the editor gives its green area back to the polygons it was cut from.
    Skipped while the editor's backup restore runs (it restores the rows).
    """
    from core.editing import is_editor_change, is_restoring
    if not is_editor_change() or is_restoring():
        return
    _guarded(lambda: release_green_area(instance.pk), f"Green area release for green space {instance.pk}")


@receiver(pre_save, sender=Street, dispatch_uid="physicalEnv_street_presave")
def street_presave(sender, instance, raw=False, **kwargs):
    """Remember the stored line and width of a street the editor changes, so post_save can tell a move from a rename."""
    from core.editing import is_editor_change
    if raw or not is_editor_change() or instance.pk is None:
        return
    instance._stored = Street.objects.filter(pk=instance.pk).values("geom", "width", "classification").first()


def _street_width(street):
    """Street.width when typed in, else the class default of the canyon equations (builtup/calculations/chain.py)."""
    from builtup.calculations.chain import DEFAULT_WIDTH_M, FALLBACK_WIDTH_M
    if street.width and street.width > 0:
        return float(street.width)
    return DEFAULT_WIDTH_M.get(street.classification, FALLBACK_WIDTH_M)


def _pave(street):
    city_id = City.objects.filter(geom__intersects=street.geom).values_list("pk", flat=True).first()
    if city_id:
        street_area(street.geom, city_id, street.pk, _street_width(street), name=street.name)


@receiver(post_save, sender=Street, dispatch_uid="physicalEnv_street_landcover_saved")
def street_landcover_saved(sender, instance, created, raw=False, **kwargs):
    """
    DAG edge: Streets -> LandCover. A street drawn, generated or reshaped in
    the map editor turns its surface (line buffered by half its width) into
    road land cover in the city's latest year (landcover.street_area); a move
    or a new width/class first gives the old surface back (release_street).
    Imports and raw saves are skipped: imported streets already lie on the
    imported land cover.
    """
    from core.editing import is_editor_change
    if raw or not is_editor_change() or not instance.geom:
        return
    if created:
        _guarded(lambda: _pave(instance), f"Road surface for street {instance.pk}")
        return
    stored = getattr(instance, "_stored", None)
    if stored is not None and stored["geom"] is not None and stored["geom"].equals_exact(instance.geom, tolerance=1e-6)             and stored["width"] == instance.width and stored["classification"] == instance.classification:
        return

    def move():
        release_street(instance.pk)
        _pave(instance)
    _guarded(move, f"Road surface move for street {instance.pk}")


@receiver(post_delete, sender=Street, dispatch_uid="physicalEnv_street_landcover_deleted")
def street_landcover_deleted(sender, instance, **kwargs):
    """
    DAG edge: Streets -> LandCover (inverse). Deleting a street in the editor
    gives its road surface back to the polygons it was cut from. Skipped while
    the editor's backup restore runs (it restores the rows).
    """
    from core.editing import is_editor_change, is_restoring
    if not is_editor_change() or is_restoring():
        return
    _guarded(lambda: release_street(instance.pk), f"Road surface release for street {instance.pk}")


@receiver(post_save, sender=Building, dispatch_uid="physicalEnv_building_dsm_saved")
def building_dsm_saved(sender, instance, created, raw=False, **kwargs):
    """
    DAG edge: Buildings -> DSM. A building created, reshaped or re-heighted
    in the map editor patches the DSM over its footprint
    (dsm_patches.record_change). Imports and raw saves (backup Restore puts the
    patch rows back itself) are skipped.
    """
    from types import SimpleNamespace

    from core.editing import is_editor_change
    if raw or not is_editor_change() or not instance.geom:
        return
    stored = getattr(instance, "_stored", None)
    height = building_height(instance)
    # 1 cm: the editor's WGS84 round trip moves vertices by far less than a DSM cell.
    if (stored and stored["geom"] is not None and stored["geom"].equals_exact(instance.geom, tolerance=0.01)
            and building_height(SimpleNamespace(**stored)) == height):
        return
    before = stored["geom"] if stored else None
    _guarded(lambda: record_change(instance.pk, before, instance.geom, height),
             f"DSM patch for building {instance.pk}")


@receiver(post_delete, sender=Building, dispatch_uid="physicalEnv_building_dsm_deleted")
def building_dsm_deleted(sender, instance, **kwargs):
    """DAG edge: Buildings -> DSM. Deleting a building in the editor lowers its footprint to the ground."""
    from core.editing import is_editor_change
    if not is_editor_change():
        return
    _guarded(lambda: record_change(instance.pk, instance.geom, None, None),
             f"DSM patch for deleted building {instance.pk}")


# Geometry fields of each DSM overlay model: (original, current).
_PATCH_GEOMS = {DSMBuildingPatch: ("original_footprint", "footprint"),
                DSMVegetationPatch: ("original_geom", "geom")}


@receiver(pre_save, sender=DSMBuildingPatch, dispatch_uid="physicalEnv_dsm_patch_presave")
@receiver(pre_save, sender=DSMVegetationPatch, dispatch_uid="physicalEnv_veg_patch_presave")
def dsm_patch_presave(sender, instance, **kwargs):
    """The geometry the overlay held before this save (raw saves too: Restore moves it back)."""
    current = _PATCH_GEOMS[sender][1]
    instance._stored_footprint = (sender.objects.filter(pk=instance.pk)
                                  .values_list(current, flat=True).first() if instance.pk else None)


@receiver(post_save, sender=DSMBuildingPatch, dispatch_uid="physicalEnv_dsm_patch_saved")
@receiver(post_delete, sender=DSMBuildingPatch, dispatch_uid="physicalEnv_dsm_patch_deleted")
@receiver(post_save, sender=DSMVegetationPatch, dispatch_uid="physicalEnv_veg_patch_saved")
@receiver(post_delete, sender=DSMVegetationPatch, dispatch_uid="physicalEnv_veg_patch_deleted")
def dsm_patch_changed(sender, instance, **kwargs):
    """
    Log the area where the DSM overlay changed (DSMEdit), raw saves and
    Restore's deletes included, so results calculated before it are flagged
    as stale. Building and vegetation patches alike.
    """
    from django.contrib.gis.geos import Polygon

    original, current = _PATCH_GEOMS[sender]
    geoms = [g for g in (getattr(instance, original), getattr(instance, current),
                         getattr(instance, "_stored_footprint", None)) if g is not None and not g.empty]
    if not geoms:
        return
    extents = [g.extent for g in geoms]
    area = Polygon.from_bbox((min(e[0] for e in extents), min(e[1] for e in extents),
                              max(e[2] for e in extents), max(e[3] for e in extents)))
    area.srid = geoms[0].srid
    DSMEdit.objects.create(area=area)
    # Burn the change into the DSM the map shows once the edit commits
    # (dsm_edited.py; analyses already read the patches).
    schedule_dsm_refresh()


@receiver(pre_save, sender=DigitalSurfaceModel, dispatch_uid="physicalEnv_dsm_cog_presave")
def dsm_cog_presave(sender, instance, raw=False, **kwargs):
    """Remember the stored COG path: a new one (re-import) invalidates the edited copy."""
    instance._stored_cog_path = (sender.objects.filter(pk=instance.pk).values_list("cog_path", flat=True).first()
                                 if instance.pk and not raw else None)


@receiver(post_save, sender=DigitalSurfaceModel, dispatch_uid="physicalEnv_dsm_cog_saved")
def dsm_cog_saved(sender, instance, created, raw=False, **kwargs):
    """
    DAG edges: Buildings -> DSM, Vegetation_Coverage -> DSM. A DSM whose COG
    was (re)exported gets its edited copy rebuilt from all stored patches.
    """
    if raw or not instance.cog_path or getattr(instance, "_stored_cog_path", None) == instance.cog_path:
        return
    if instance.edited_cog_path or instance.edited_upto is not None:
        sender.objects.filter(pk=instance.pk).update(edited_cog_path=None, edited_upto=None)
    schedule_dsm_refresh(instance.pk)


# ── Vegetation_Coverage -> DSM ───────────────────────────────────────
# Editor changes only (core.editing.is_editor_change): imported trees and
# forests are already in AHN's DSM. Tree and Forests are bulk-imported
# (importer/batching.py::BULK_IMPORT_MODELS) without a finalizer for these
# receivers on purpose: an import never patches the DSM.

def _tree_crown(values):
    return tree_crown(values["geom"], values["height_m"], values["crownDiameter_m"])


@receiver(pre_save, sender=Tree, dispatch_uid="physicalEnv_tree_presave")
@receiver(pre_save, sender=Forests, dispatch_uid="physicalEnv_forest_presave")
def vegetation_presave(sender, instance, raw=False, **kwargs):
    """Remember the stored tree / forest, so post_save can tell a move or resize from an attribute edit."""
    from core.editing import is_editor_change
    if raw or not is_editor_change() or instance.pk is None:
        return
    fields = ("geom", "height_m", "crownDiameter_m") if sender is Tree else ("geom",)
    instance._veg_stored = sender.objects.filter(pk=instance.pk).values(*fields).first()


def _veg_label(sender):
    return f"{sender._meta.app_label}.{sender.__name__}"


@receiver(post_save, sender=Tree, dispatch_uid="physicalEnv_tree_dsm_saved")
def tree_dsm_saved(sender, instance, created, raw=False, **kwargs):
    """
    DAG edge: Vegetation_Coverage -> DSM. A tree planted, moved or resized in
    the map editor clears its old crown and raises its new one
    (dsm_patches.record_vegetation_change).
    """
    from core.editing import is_editor_change
    if raw or not is_editor_change() or not instance.geom:
        return
    stored = getattr(instance, "_veg_stored", None)
    current = {"geom": instance.geom, "height_m": instance.height_m, "crownDiameter_m": instance.crownDiameter_m}
    if (stored and stored["geom"] is not None and stored["geom"].equals_exact(instance.geom, tolerance=0.01)
            and stored["height_m"] == instance.height_m and stored["crownDiameter_m"] == instance.crownDiameter_m):
        return
    before = _tree_crown(stored) if stored and stored["geom"] is not None else None
    _guarded(lambda: record_vegetation_change(_veg_label(sender), instance.pk, before,
                                              _tree_crown(current), tree_height(instance)),
             f"DSM patch for tree {instance.pk}")


@receiver(post_delete, sender=Tree, dispatch_uid="physicalEnv_tree_dsm_deleted")
def tree_dsm_deleted(sender, instance, **kwargs):
    """DAG edge: Vegetation_Coverage -> DSM. A tree felled in the editor clears its crown."""
    from core.editing import is_editor_change
    if not is_editor_change() or not instance.geom:
        return
    crown = _tree_crown({"geom": instance.geom, "height_m": instance.height_m,
                         "crownDiameter_m": instance.crownDiameter_m})
    _guarded(lambda: record_vegetation_change(_veg_label(sender), instance.pk, crown, None, None),
             f"DSM patch for deleted tree {instance.pk}")


@receiver(post_save, sender=Forests, dispatch_uid="physicalEnv_forest_dsm_saved")
def forest_dsm_saved(sender, instance, created, raw=False, **kwargs):
    """
    DAG edge: Vegetation_Coverage -> DSM. A forest drawn or reshaped in the
    map editor clears the tall vegetation of the area it gave up and plants
    DEFAULT_FOREST_CANOPY_M on the area it gained.
    """
    from core.editing import is_editor_change
    if raw or not is_editor_change() or not instance.geom:
        return
    stored = getattr(instance, "_veg_stored", None)
    before = stored["geom"] if stored else None
    if before is not None and before.equals_exact(instance.geom, tolerance=0.01):
        return
    _guarded(lambda: record_vegetation_change(_veg_label(sender), instance.pk, before, instance.geom,
                                              DEFAULT_FOREST_CANOPY_M),
             f"DSM patch for forest {instance.pk}")


@receiver(post_delete, sender=Forests, dispatch_uid="physicalEnv_forest_dsm_deleted")
def forest_dsm_deleted(sender, instance, **kwargs):
    """DAG edge: Vegetation_Coverage -> DSM. A forest deleted in the editor clears its tall vegetation."""
    from core.editing import is_editor_change
    if not is_editor_change() or not instance.geom:
        return
    _guarded(lambda: record_vegetation_change(_veg_label(sender), instance.pk, instance.geom, None, None),
             f"DSM patch for deleted forest {instance.pk}")
