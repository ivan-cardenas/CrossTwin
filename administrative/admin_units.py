"""Shared helpers for resolving and aggregating by administrative unit.

Lets any domain app's indicator calculations accept a Province, City,
District, or Neighborhood instance interchangeably, since all four carry
a `geom` field and sit in a single FK chain
(Province > City > District > Neighborhood).
"""

import functools

from django.conf import settings
from django.contrib.gis.gdal import CoordTransform, SpatialReference
from django.contrib.gis.geos import Point

from .models import Province, City, District, Neighborhood, Postcode4, Postcode6


@functools.lru_cache(maxsize=1)
def _wgs84_to_storage():
    """
    Built once per process: creating a GDAL/PROJ transformation is the slow
    part of Point.transform() (~25 ms, most of an admin-unit request), while
    applying an existing one takes microseconds.
    """
    return CoordTransform(SpatialReference(4326), SpatialReference(settings.COORDINATE_SYSTEM))

ADMIN_LEVELS = {
    'province':     (Province,     'ProvinceName'),
    'city':         (City,         'cityName'),
    'district':     (District,     'districtName'),
    'neighborhood': (Neighborhood, 'neighborhoodName'),
    # Postcode areas cut across the chain above (a PC4 spans several neighborhoods and often several
    # municipalities): they are units you can select and aggregate by, but not part of the hierarchy that
    # a point resolves through (HIERARCHY_LEVELS) or that cascades population.
    'postcode4':    (Postcode4,    'code'),
    'postcode6':    (Postcode6,    'code'),
}

# The nested chain, largest to smallest: what a map point resolves through (smallest first).
HIERARCHY_LEVELS = ('province', 'city', 'district', 'neighborhood')
POSTCODE_MODELS = (Postcode4, Postcode6)


def resolve_admin_unit(level, name):
    """Look up a Province/City/District/Neighborhood instance by level + name."""
    entry = ADMIN_LEVELS.get(level)
    if entry is None:
        return None
    model, name_field = entry
    try:
        return model.objects.get(**{name_field: name})
    except model.DoesNotExist:
        return None


def resolve_admin_unit_at_point(lng, lat):
    """
    Point-in-polygon lookup: find the smallest administrative unit
    (Neighborhood > District > City > Province) containing a WGS84
    (lng, lat) point, e.g. the current map center.

    Returns (level, unit) — the level key from ADMIN_LEVELS and the
    matching model instance — or (None, None) if the point falls outside
    every known unit.
    """
    point = Point(lng, lat, srid=4326)
    point.transform(_wgs84_to_storage())

    for level in reversed(HIERARCHY_LEVELS):
        model = ADMIN_LEVELS[level][0]
        unit = model.objects.filter(geom__contains=point).first()
        if unit:
            return level, unit
    return None, None


def postcodes_at_point(lng, lat):
    """{'postcode4': Postcode4 or None, 'postcode6': Postcode6 or None} containing a WGS84 (lng, lat) point."""
    point = Point(lng, lat, srid=4326)
    point.transform(_wgs84_to_storage())
    return {level: ADMIN_LEVELS[level][0].objects.filter(geom__contains=point).first()
            for level in ('postcode4', 'postcode6')}


def _anchor(unit):
    """A point that lies on the unit (point on surface, so it is inside even for a concave area)."""
    return unit.geom.point_on_surface


def city_of(unit):
    """
    The City an administrative unit belongs to (itself for a City), or None
    for a Province (it spans many cities) or an unattached District/Neighborhood.
    """
    if isinstance(unit, City):
        return unit
    if isinstance(unit, District):
        return unit.city
    if isinstance(unit, Neighborhood):
        return unit.district.city if unit.district else None
    if isinstance(unit, POSTCODE_MODELS):
        # a postcode area can span cities: the one under its point on surface
        return City.objects.filter(geom__contains=_anchor(unit)).first()
    return None


def cities_within(unit):
    """City queryset covering the given administrative unit, at any level."""
    if isinstance(unit, Province):
        return City.objects.filter(province=unit)
    if isinstance(unit, City):
        return City.objects.filter(pk=unit.pk)
    if isinstance(unit, District):
        return City.objects.filter(pk=unit.city_id)
    if isinstance(unit, Neighborhood):
        return City.objects.filter(pk=unit.district.city_id)
    if isinstance(unit, POSTCODE_MODELS):
        return City.objects.filter(geom__intersects=unit.geom)
    raise TypeError(f"cities_within: unsupported unit type {type(unit)!r}")


def neighborhoods_within(unit):
    """Neighborhood queryset covering the given administrative unit, at any level."""
    if isinstance(unit, Province):
        return Neighborhood.objects.filter(district__city__province=unit)
    if isinstance(unit, City):
        return Neighborhood.objects.filter(district__city=unit)
    if isinstance(unit, District):
        return Neighborhood.objects.filter(district=unit)
    if isinstance(unit, Neighborhood):
        return Neighborhood.objects.filter(pk=unit.pk)
    if isinstance(unit, Postcode6):
        # a street section is smaller than a neighborhood: the one it lies in
        return Neighborhood.objects.filter(geom__contains=_anchor(unit))
    if isinstance(unit, Postcode4):
        # the neighborhoods whose point on surface lies in the area (a neighborhood cut by the border
        # belongs to the area that holds its middle, so none is counted twice)
        from django.contrib.gis.db.models.functions import PointOnSurface

        return Neighborhood.objects.annotate(anchor_pt=PointOnSurface("geom")).filter(anchor_pt__within=unit.geom)
    raise TypeError(f"neighborhoods_within: unsupported unit type {type(unit)!r}")


def province_of(unit):
    """Resolve the enclosing Province for an admin unit at any level.

    Needed for province-scoped reference data (e.g. central bank policy,
    credit conditions) that has no per-city/district/neighborhood variant.
    """
    if isinstance(unit, Province):
        return unit
    if isinstance(unit, City):
        return unit.province
    if isinstance(unit, District):
        return unit.city.province
    if isinstance(unit, Neighborhood):
        return unit.district.city.province
    if isinstance(unit, POSTCODE_MODELS):
        city = city_of(unit)
        return city.province if city else None
    raise TypeError(f"province_of: unsupported unit type {type(unit)!r}")
