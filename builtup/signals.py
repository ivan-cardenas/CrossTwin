"""
Street canyon refresh (builtup.StreetCanyon).

DAG edges:
    Streets   -> Canyon_Aspect   a street saved -> its canyon; deleted -> canyon deleted
    Buildings -> Canyon_Aspect   a building saved/moved/deleted -> the canyons of
                                 the streets within canyon.SEARCH_M of its old
                                 and new footprint

Every refresh goes through refresh_canyons(): one SQL statement for the inputs
(builtup/canyon.py), the equations of builtup/chain.py applied per row by
StreetCanyon.apply() (the same code StreetCanyon.save() runs), then one
bulk upsert. bulk_create fires no post_save, so the layer cache is bumped here
and canyons_changed announces the refreshed streets to downstream apps.

Bulk imports run inside deferred_canyon_refresh() (registered in
importer/batching.py::deferred_cascades): the streets and footprint extents are
collected and refreshed once when the block ends. The bulk Street import
replays street_saved through importer/batching.py::_refresh_canyons_over.

Map editing: rows a refresh changes or creates during an editor change are
announced with canyon_rewriting / canyon_created (journalled by
mainMap/signals.py), so Restore puts them back with the edit (receivers skip
raw saves, so Restore itself refreshes nothing).
"""
import logging
import threading
from contextlib import contextmanager

from django.db.models.signals import post_delete, post_save, pre_delete, pre_save
from django.dispatch import Signal, receiver

from .models import Building, Property, Street, StreetCanyon

logger = logging.getLogger(__name__)

# Sent with street_ids=[...] after canyons were refreshed (bulk upsert, no post_save).
canyons_changed = Signal()
# Same contract as physicalEnv.dsm_patches.dsm_patch_rewriting / dsm_patch_created.
canyon_rewriting = Signal()
canyon_created = Signal()

CHUNK = 500

_deferred = threading.local()


@contextmanager
def deferred_canyon_refresh():
    """
    Postpone canyon refreshes until the block ends, then run them once over
    the collected streets and footprint extents. Nested uses defer to the
    outermost one; the flush also runs if the block raises (errors logged).
    """
    if getattr(_deferred, "streets", None) is not None:
        yield
        return
    _deferred.streets, _deferred.extents = set(), []
    try:
        yield
    except BaseException:
        streets, extents = _deferred.streets, _deferred.extents
        _deferred.streets = _deferred.extents = None
        try:
            _flush(streets, extents)
        except Exception:
            logger.exception("Deferred canyon refresh failed after an aborted block")
        raise
    else:
        streets, extents = _deferred.streets, _deferred.extents
        _deferred.streets = _deferred.extents = None
        _flush(streets, extents)


def _flush(street_ids, extents):
    ids = set(street_ids)
    if extents:
        ids |= set(streets_in_extent(extents))
    if ids:
        refresh_canyons(ids)


def streets_in_extent(extents):
    """Streets within canyon.SEARCH_M of the box around all `extents` (one box: imports are local)."""
    from django.conf import settings
    from django.contrib.gis.geos import Polygon

    from .canyon import SEARCH_M

    box = Polygon.from_bbox((min(e[0] for e in extents) - SEARCH_M, min(e[1] for e in extents) - SEARCH_M,
                             max(e[2] for e in extents) + SEARCH_M, max(e[3] for e in extents) + SEARCH_M))
    box.srid = int(settings.COORDINATE_SYSTEM)
    return Street.objects.filter(geom__bboverlaps=box).values_list("pk", flat=True)


def schedule_streets(street_ids):
    """Refresh these streets' canyons now, or when the enclosing deferral ends."""
    if getattr(_deferred, "streets", None) is not None:
        _deferred.streets.update(street_ids)
        return
    refresh_canyons(street_ids)


def schedule_footprints(geoms):
    """Refresh the canyons around these footprints now, or when the enclosing deferral ends."""
    geoms = [g for g in geoms if g is not None and not g.empty]
    if not geoms:
        return
    if getattr(_deferred, "extents", None) is not None:
        _deferred.extents.extend(g.extent for g in geoms)
        return
    from .canyon import streets_near
    refresh_canyons(streets_near(geoms))


def refresh_canyons(street_ids):
    """
    Recompute and upsert the StreetCanyon of every street in `street_ids`.
    Returns the number of canyons written. Failures are logged, never raised
    (they must not block the save of the street or building that caused them).
    """
    try:
        return _refresh(sorted({int(i) for i in street_ids}))
    except Exception:
        logger.exception("Street canyon refresh failed")
        return 0


def _refresh(ids):
    from django.utils import timezone

    from core.cache import bump_layer_version
    from core.editing import is_editor_change

    from .canyon import street_inputs

    if not ids:
        return 0
    editor = is_editor_change()
    written = 0
    for start in range(0, len(ids), CHUNK):
        chunk = ids[start:start + CHUNK]
        streets = list(Street.objects.filter(pk__in=chunk).exclude(geom=None)
                       .only("width", "classification", "geom"))
        if not streets:
            continue
        inputs = street_inputs([s.pk for s in streets])
        existing = dict(StreetCanyon.objects.filter(street_id__in=[s.pk for s in streets])
                        .values_list("street_id", "pk"))
        if editor and existing:
            canyon_rewriting.send(sender=StreetCanyon, pks=list(existing.values()))
        now = timezone.now()
        rows = []
        for street in streets:
            canyon = StreetCanyon(street_id=street.pk, updated=now)
            canyon.apply(street, inputs[street.pk])
            rows.append(canyon)
        StreetCanyon.objects.bulk_create(
            rows, update_conflicts=True, unique_fields=["street"],
            update_fields=["h_left_m", "h_right_m", "w_facade_m", "n_left", "n_right", "height_m",
                           "width_m", "width_source", "aspect_ratio", "updated", "geom"])
        written += len(rows)
        if editor:
            new = [s.pk for s in streets if s.pk not in existing]
            if new:
                canyon_created.send(sender=StreetCanyon, pks=list(
                    StreetCanyon.objects.filter(street_id__in=new).values_list("pk", flat=True)))
    bump_layer_version(StreetCanyon)
    canyons_changed.send(sender=StreetCanyon, street_ids=ids)
    return written


# ── Streets -> Canyon_Aspect ─────────────────────────────────────────

@receiver(post_save, sender=Street, dispatch_uid="builtup_street_saved")
def street_saved(sender, instance, raw=False, **kwargs):
    """DAG edge: Streets -> Canyon_Aspect. A saved street (line, width, class) refreshes its canyon."""
    if raw:
        return
    schedule_streets([instance.pk])


@receiver(pre_delete, sender=Street, dispatch_uid="builtup_street_deleted")
def street_deleted(sender, instance, **kwargs):
    """DAG edge: Streets -> Canyon_Aspect. A deleted street takes its canyon with it (FK is DO_NOTHING)."""
    from core.cache import bump_layer_version
    from core.editing import is_editor_change

    pks = list(StreetCanyon.objects.filter(street_id=instance.pk).values_list("pk", flat=True))
    if not pks:
        return
    if is_editor_change():
        canyon_rewriting.send(sender=StreetCanyon, pks=pks)
    StreetCanyon.objects.filter(pk__in=pks).delete()
    bump_layer_version(StreetCanyon)


# ── Buildings -> Canyon_Aspect ───────────────────────────────────────

@receiver(pre_save, sender=Building, dispatch_uid="builtup_building_canyon_presave")
def building_canyon_presave(sender, instance, raw=False, **kwargs):
    """The stored footprint and height, to tell whether a save changes any canyon."""
    if raw or instance.pk is None:
        return
    instance._canyon_stored = (Building.objects.filter(pk=instance.pk)
                               .values("geom", "height_m", "numberFloors").first())


@receiver(post_save, sender=Building, dispatch_uid="builtup_building_canyon_saved")
def building_canyon_saved(sender, instance, created, raw=False, **kwargs):
    """
    DAG edge: Buildings -> Canyon_Aspect. A building created, moved, reshaped
    or re-heighted refreshes the canyons around its old and new footprint;
    an attribute-only edit refreshes nothing.
    """
    if raw:
        return
    stored = getattr(instance, "_canyon_stored", None)
    if stored and not created:
        same_geom = (stored["geom"] is not None and instance.geom is not None
                     and stored["geom"].equals_exact(instance.geom, tolerance=0.01))
        if (same_geom and stored["height_m"] == instance.height_m
                and stored["numberFloors"] == instance.numberFloors):
            return
    schedule_footprints([instance.geom, stored["geom"] if stored else None])


@receiver(post_delete, sender=Building, dispatch_uid="builtup_building_canyon_deleted")
def building_canyon_deleted(sender, instance, **kwargs):
    """DAG edge: Buildings -> Canyon_Aspect. A deleted building opens up the canyons around it."""
    schedule_footprints([instance.geom])


# ── Degree of Urbanisation ───────────────────────────────────────────
#
# DAG edges: Total_Population -> Degree_Urbanisation (neighborhood population,
#            residential properties), Buildings -> Degree_Urbanisation
#            (built-up share), LandCover -> Degree_Urbanisation (settlement
#            mask, water). The receivers only schedule the neighborhoods to
#            re-allocate; builtup/urbanisation.py::refresh does the work (once
#            per deferred_cascades() block) and Urbanisation.save() holds the
#            unit equations. Nothing runs until the grid was built from the map.
#
# Restore (core.editing.restore_backup) re-saves rows raw. These rows are a
# pure derivation of their sources, so instead of journalling them the
# receivers also react to raw saves while a restore runs: the refresh then
# recomputes the restored state once, when restore's deferred_cascades() ends.

def _skip_raw(raw):
    from core.editing import is_restoring

    return raw and not is_restoring()


def _schedule_hoods(ids=(), geoms=(), landcover=()):
    """Schedule the neighborhoods `ids` + those under `geoms`, and the land cover over the `landcover` geometries."""
    from .urbanisation import neighborhoods_at, schedule

    try:
        schedule(set(ids) | neighborhoods_at(geoms), landcover=[g for g in landcover if g is not None])
    except Exception:
        logger.exception("Degree of Urbanisation scheduling failed")


@receiver(pre_save, sender="administrative.Neighborhood", dispatch_uid="builtup_neighborhood_urbanisation_presave")
def neighborhood_urbanisation_presave(sender, instance, raw=False, **kwargs):
    if instance.pk is None:
        return
    instance._urbanisation_stored = (sender.objects.filter(pk=instance.pk)
                                     .values("currentPopulation", "geom").first())


@receiver(post_save, sender="administrative.Neighborhood", dispatch_uid="builtup_neighborhood_urbanisation_saved")
def neighborhood_urbanisation_saved(sender, instance, created, raw=False, **kwargs):
    """DAG edge: Total_Population -> Degree_Urbanisation. New population or outline -> re-allocate it."""
    if _skip_raw(raw):
        return
    stored = getattr(instance, "_urbanisation_stored", None)
    if stored and not created:
        same_geom = (stored["geom"] is not None and instance.geom is not None
                     and stored["geom"].equals_exact(instance.geom, tolerance=0.01))
        if same_geom and stored["currentPopulation"] == instance.currentPopulation:
            return
    _schedule_hoods([instance.pk])


@receiver(post_delete, sender="administrative.Neighborhood", dispatch_uid="builtup_neighborhood_urbanisation_deleted")
def neighborhood_urbanisation_deleted(sender, instance, **kwargs):
    """DAG edge: Total_Population -> Degree_Urbanisation. Its allocation rows go with it (CASCADE)."""
    _schedule_hoods([instance.pk])


def _is_property(sender):
    return isinstance(sender, type) and issubclass(sender, Property)


@receiver(pre_save, dispatch_uid="builtup_property_urbanisation_presave")
def property_urbanisation_presave(sender, instance, raw=False, **kwargs):
    if not _is_property(sender) or instance.pk is None:
        return
    instance._urbanisation_stored = (Property.objects.filter(pk=instance.pk)
                                     .values("geom", "usageFunction").first())


def _residential(usage):
    return bool(usage) and "Residential function" in usage


@receiver(post_save, dispatch_uid="builtup_property_urbanisation_saved")
def property_urbanisation_saved(sender, instance, created, raw=False, **kwargs):
    """
    DAG edge: Total_Population -> Degree_Urbanisation. A dwelling added, moved
    or (un)made residential changes how its neighborhood's people are spread.
    Sender is Property or a proxy (housing.ResidentialProperty), which builtup
    cannot import, hence the subclass test.
    """
    if not _is_property(sender) or _skip_raw(raw):
        return
    stored = getattr(instance, "_urbanisation_stored", None)
    was = bool(stored) and _residential(stored["usageFunction"])
    now = _residential(instance.usageFunction)
    if not was and not now:
        return
    if stored and not created and was == now and stored["geom"] is not None and instance.geom is not None \
            and stored["geom"].equals_exact(instance.geom, tolerance=0.01):
        return
    _schedule_hoods(geoms=[instance.geom, stored["geom"] if stored else None])


@receiver(post_delete, dispatch_uid="builtup_property_urbanisation_deleted")
def property_urbanisation_deleted(sender, instance, **kwargs):
    """DAG edge: Total_Population -> Degree_Urbanisation. A dwelling removed."""
    if _is_property(sender) and _residential(instance.usageFunction):
        _schedule_hoods(geoms=[instance.geom])


@receiver(pre_save, sender=Building, dispatch_uid="builtup_building_urbanisation_presave")
def building_urbanisation_presave(sender, instance, raw=False, **kwargs):
    if instance.pk is None:
        return
    instance._urbanisation_geom = Building.objects.filter(pk=instance.pk).values_list("geom", flat=True).first()


@receiver(post_save, sender=Building, dispatch_uid="builtup_building_urbanisation_saved")
def building_urbanisation_saved(sender, instance, created, raw=False, **kwargs):
    """DAG edge: Buildings -> Degree_Urbanisation. A footprint drawn or moved changes the built-up share."""
    if _skip_raw(raw):
        return
    old = getattr(instance, "_urbanisation_geom", None)
    if not created and old is not None and instance.geom is not None \
            and old.equals_exact(instance.geom, tolerance=0.01):
        return
    _schedule_hoods(geoms=[instance.geom, old])


@receiver(post_delete, sender=Building, dispatch_uid="builtup_building_urbanisation_deleted")
def building_urbanisation_deleted(sender, instance, **kwargs):
    """DAG edge: Buildings -> Degree_Urbanisation."""
    _schedule_hoods(geoms=[instance.geom])


@receiver(post_save, sender="physicalEnv.LandCoverVector", dispatch_uid="builtup_landcover_urbanisation_saved")
def landcover_urbanisation_saved(sender, instance, raw=False, **kwargs):
    """DAG edge: LandCover -> Degree_Urbanisation. Settlement mask and water shares are re-read."""
    if _skip_raw(raw):
        return
    _schedule_hoods(landcover=[instance.geom])


@receiver(post_delete, sender="physicalEnv.LandCoverVector", dispatch_uid="builtup_landcover_urbanisation_deleted")
def landcover_urbanisation_deleted(sender, instance, **kwargs):
    """DAG edge: LandCover -> Degree_Urbanisation."""
    _schedule_hoods(landcover=[instance.geom])


def _landcover_rows_created(sender, pks=(), **kwargs):
    """DAG edge: LandCover -> Degree_Urbanisation. Rows the editor's rings insert with raw SQL / create()."""
    from physicalEnv.models import LandCoverVector

    if sender is not LandCoverVector:
        return
    _schedule_hoods(landcover=list(LandCoverVector.objects.filter(pk__in=list(pks)).values_list("geom", flat=True)))


def _connect_landcover_created():
    from physicalEnv.landcover import landcover_created

    landcover_created.connect(_landcover_rows_created, dispatch_uid="builtup_landcover_urbanisation_created")


_connect_landcover_created()
