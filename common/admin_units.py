"""Shared helpers for resolving and aggregating by administrative unit.

Lets any domain app's indicator calculations accept a Province, City,
District, or Neighborhood instance interchangeably, since all four carry
a `geom` field and sit in a single FK chain
(Province > City > District > Neighborhood).
"""

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
