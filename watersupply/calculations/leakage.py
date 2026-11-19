"""
Inputs of the Unavoidable Annual Real Losses (UARL) per city, read from the
database. The equation itself is watersupply/calculations/chain.py::uarl_m3_d;
this module only gathers its inputs, for both callers:

* the stored path, LeakageIndex.save() (network-wide, one row per year);
* the dashboard, calculations/indicators.py::calculate_nrw (one admin unit).

Each city contributes (18 Lm + 0.8 Nc + 25 Lp) x P with its own pressure P
(CoverageWaterSupply.avg_pressure_m of the city's latest record up to the year),
its mains length Lm (pipes clipped to the area) and its connections Nc (dwellings
within the service buffer: in the Netherlands every dwelling has its own meter
and connection, so shared connections of apartment blocks are overcounted).
Pipes outside every city count with DEFAULT_PRESSURE_M and no connections.

DAG edge: Network -> ILI
"""
from . import chain


def coverage_record(city_id, year):
    """The city's CoverageWaterSupply used for `year`: latest up to it, else the earliest later one."""
    from watersupply.models import CoverageWaterSupply

    records = CoverageWaterSupply.objects.filter(city_id=city_id)
    return (records.filter(year__lte=year).order_by('-year', '-id').first()
            or records.order_by('year', 'id').first())


def mains_km_within(geom):
    """Length of the pipe network inside `geom`, in km (pipes clipped to it)."""
    from django.contrib.gis.db.models.functions import Intersection, Length
    from django.db.models import Sum

    from watersupply.models import PipeNetwork

    total = (PipeNetwork.objects.filter(geom__intersects=geom)
             .annotate(inside=Length(Intersection('geom', geom)))
             .aggregate(m=Sum('inside'))['m'])
    return total.m / 1000 if total else 0.0


def total_mains_km():
    from django.db.models import Sum

    from watersupply.models import PipeNetwork

    return PipeNetwork.objects.aggregate(km=Sum('length_km'))['km'] or 0.0


def city_part(city_id, year, geom, private_pipe_m, connections=None, buffer_neighborhoods=None):
    """
    One city's share of the UARL inside `geom` (the city, or a unit within it).
    `connections` defaults to the coverage record's households_covered; with
    `buffer_neighborhoods` they are counted for those neighborhoods only.
    """
    from .users import neighborhood_users

    record = coverage_record(city_id, year)
    pressure = record.avg_pressure_m if record and record.avg_pressure_m else chain.DEFAULT_PRESSURE_M
    if connections is None:
        if buffer_neighborhoods is not None:
            buffer_m = record.buffer_m if record else None
            from .users import DEFAULT_SERVICE_BUFFER_M
            counts = neighborhood_users(list(buffer_neighborhoods), buffer_m or DEFAULT_SERVICE_BUFFER_M)
            connections = sum(c.dwellings_served for c in counts.values())
        else:
            connections = record.households_covered if record else 0
    mains = mains_km_within(geom)
    return {
        'city_id': city_id,
        'coverage_year': record.year if record else None,
        'mains_km': round(mains, 3),
        'connections': connections,
        'pressure_m': pressure,
        'uarl_m3_d': chain.uarl_m3_d(mains, connections, connections * private_pipe_m / 1000, pressure),
    }


def combine(parts):
    """Totals of city parts: mains, connections, UARL, mean pressure (weighted by mains + connections), reliability."""
    mains = sum(p['mains_km'] for p in parts)
    connections = sum(p['connections'] for p in parts)
    uarl = sum(p['uarl_m3_d'] for p in parts)
    weights = [(p['mains_km'] + p['connections'], p['pressure_m']) for p in parts]
    weight = sum(w for w, _ in weights)
    pressure = sum(w * pm for w, pm in weights) / weight if weight else None
    min_pressure = min((p['pressure_m'] for p in parts), default=0)
    return {
        'mains_km': round(mains, 3),
        'connections': connections,
        'uarl_m3_d': uarl,
        'pressure_m': round(pressure, 2) if pressure is not None else None,
        'reliable': chain.uarl_reliable(mains, connections, min_pressure),
    }


def network_parts(year, private_pipe_m):
    """Per-city parts of the whole network for `year` (LeakageIndex.save())."""
    from administrative.models import City
    from watersupply.models import CoverageWaterSupply

    city_ids = (CoverageWaterSupply.objects.filter(city__isnull=False)
                .values_list('city_id', flat=True).distinct())
    parts = [city_part(city.pk, year, city.geom, private_pipe_m)
             for city in City.objects.filter(pk__in=city_ids).only('pk', 'geom').order_by('pk')]
    rest = total_mains_km() - sum(p['mains_km'] for p in parts)
    if rest > 1e-6:   # pipes outside every covered city: default pressure, no connections
        parts.append({'city_id': None, 'coverage_year': None, 'mains_km': round(rest, 3),
                      'connections': 0, 'pressure_m': chain.DEFAULT_PRESSURE_M,
                      'uarl_m3_d': chain.uarl_m3_d(rest, 0, 0, chain.DEFAULT_PRESSURE_M)})
    return parts
