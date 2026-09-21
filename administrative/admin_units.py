"""Shared helpers for resolving and aggregating by administrative unit.

Lets any domain app's indicator calculations accept a Province, City,
District, or Neighborhood instance interchangeably, since all four carry
a `geom` field and sit in a single FK chain
(Province > City > District > Neighborhood).
"""

from django.conf import settings
from django.contrib.gis.geos import Point

from .models import Province, City, District, Neighborhood

ADMIN_LEVELS = {
    'province':     (Province,     'ProvinceName'),
    'city':         (City,         'cityName'),
    'district':     (District,     'districtName'),
    'neighborhood': (Neighborhood, 'neighborhoodName'),
}


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
    point.transform(settings.COORDINATE_SYSTEM)

    for level, (model, _name_field) in reversed(list(ADMIN_LEVELS.items())):
        unit = model.objects.filter(geom__contains=point).first()
        if unit:
            return level, unit
    return None, None


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
    raise TypeError(f"province_of: unsupported unit type {type(unit)!r}")
