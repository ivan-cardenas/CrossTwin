"""
A year of daily precipitation and reference evapotranspiration at the
station nearest to a point: the meteorological input of the yearly recharge
of watersupply.AvailableFreshWater (watersupply/calculations/chain.py::recharge_depth_cm_yr).

Only daily water-balance rows count (reference_et_mm set, as written by
weather/knmi.py::store_daily); a year counts as complete with
MIN_DAYS_PER_YEAR days that have both values.

DAG edge: Meteorology -> Available_FW (the input side)
"""
MIN_DAYS_PER_YEAR = 360
# How many of the nearest stations with daily rows are tried before giving up.
MAX_STATIONS = 5


def yearly_water_balance(point, year=None):
    """
    {'station': WeatherStation, 'year', 'daily_rain_mm': [...], 'et_ref_mm': float}
    of the nearest station with a complete year: `year` when given, otherwise
    the station's latest complete year. None when no station has one.
    `point` is a GEOS point in the storage CRS.
    """
    from django.contrib.gis.db.models.functions import Distance
    from django.db.models import Count

    from ..models import Meteorology, WeatherStation

    daily = Meteorology.objects.filter(reference_et_mm__isnull=False, precipitation_mm__isnull=False)
    stations = (
        WeatherStation.objects.filter(pk__in=daily.values("station_id"))
        .annotate(distance=Distance("geom", point)).order_by("distance")[:MAX_STATIONS]
    )
    for station in stations:
        years = (
            daily.filter(station=station).values("date__year")
            .annotate(days=Count("id")).filter(days__gte=MIN_DAYS_PER_YEAR)
            .values_list("date__year", flat=True)
        )
        if year is not None:
            if year not in set(years):
                continue
            chosen = year
        else:
            chosen = max(years, default=None)
            if chosen is None:
                continue
        rows = daily.filter(station=station, date__year=chosen).values_list("precipitation_mm", "reference_et_mm")
        rain, et = zip(*rows)
        return {"station": station, "year": chosen, "daily_rain_mm": list(rain), "et_ref_mm": sum(et)}
    return None
