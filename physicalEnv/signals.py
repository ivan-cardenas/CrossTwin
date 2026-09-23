from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.db.models import Sum, Max, Q
from django.contrib.gis.db.models.functions import Area, Intersection
from django.utils import timezone

from .models import LandCoverVector
from administrative.models import Neighborhood, District, City, Province
# Reused from administrative's own population cascade rather than
# duplicated -- see administrative/signals.py for the shared aggregation
# logic this re-enters after writing Neighborhood.urban_area below.
from administrative.signals import _recompute_population

URBAN_AREA_KEYWORDS = ["urban fabric", "road", "rail", "transport"]


def _urban_area_filter():
    """Q object: land_cover_type.class_name case-insensitively contains
    any of URBAN_AREA_KEYWORDS. class_name is a free-form lookup value
    populated at import time (see importer/external_catalog.py's
    pdok_landcover_brt entry), not a fixed enum, so substring matching is
    used rather than exact equality -- matching the same convention as
    core/landCoverStyles.py's KEYWORD_COLORS."""
    q = Q()
    for kw in URBAN_AREA_KEYWORDS:
        q |= Q(land_cover_type__class_name__icontains=kw)
    return q


def _recompute_neighborhood_urban_area(city_id):
    """
    Recompute urban_area for every Neighborhood under city_id, from the
    most recent LandCoverVector year available for that city, then
    manually re-enter administrative/signals.py's population/urban_area
    cascade. Neighborhood.objects.update() below does not fire post_save,
    so nothing else will push this change up to District/City/Province.
    """
    latest_year = LandCoverVector.objects.filter(city_id=city_id).aggregate(
        latest=Max('year')
    )['latest']
    # No LandCoverVector rows left for this city (e.g. the last one was just
    # deleted) -- don't bail out early, still recompute so existing
    # Neighborhoods reset to 0.0 instead of keeping a stale value.
    qualifying = (
        LandCoverVector.objects.filter(city_id=city_id, year=latest_year).filter(_urban_area_filter())
        if latest_year is not None
        else LandCoverVector.objects.none()
    )

    district_ids = set()
    for neighborhood in Neighborhood.objects.filter(district__city_id=city_id):
        total = (
            qualifying.filter(geom__intersects=neighborhood.geom)
            .annotate(clipped=Intersection('geom', neighborhood.geom))
            .annotate(clipped_area=Area('clipped'))
            .aggregate(total=Sum('clipped_area'))['total']
        )
        urban_area_km2 = total.sq_km if total else 0.0
        Neighborhood.objects.filter(pk=neighborhood.pk).update(
            urban_area=urban_area_km2, last_updated=timezone.now(),
        )
        if neighborhood.district_id:
            district_ids.add(neighborhood.district_id)

    for district_id in district_ids:
        city_pk = _recompute_population(
            District, district_id,
            child_model=Neighborhood, child_fk='district_id', parent_fk='city_id',
        )
        if not city_pk:
            continue
        province_pk = _recompute_population(
            City, city_pk,
            child_model=District, child_fk='city_id', parent_fk='province_id',
        )
        if not province_pk:
            continue
        _recompute_population(
            Province, province_pk,
            child_model=City, child_fk='province_id',
        )


@receiver(post_save, sender=LandCoverVector, dispatch_uid="landcover_save_to_neighborhood_urban_area")
@receiver(post_delete, sender=LandCoverVector, dispatch_uid="landcover_delete_to_neighborhood_urban_area")
def landcover_changed(sender, instance, **kwargs):
    # O(qualifying rows x neighborhoods) per city on every single save/delete
    # -- fine for interactive edits, but a bulk WFS import (one
    # LandCoverVector.objects.create() per feature, no bulk_create -- see
    # importer/external_data.py) will re-run this redundantly once per row
    # of the same city. Not solved here; batching import-side would need the
    # importer to disconnect this receiver for the duration of a batch and
    # call _recompute_neighborhood_urban_area() once per city afterward.
    city_id = instance.city_id
    if not city_id:
        return
    _recompute_neighborhood_urban_area(city_id)
