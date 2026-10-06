from django.contrib.gis.db.models.functions import Intersection, Length
from django.db.models import Sum, Avg, Count, Q, F, FloatField, Value
from django.db.models.functions import Cast, Coalesce, Greatest, Round

from .models import Building, Street, Park, Facility
from administrative.admin_units import neighborhoods_within


# Construction-period bands of the Dutch housing-stock typology (RVO
# "Voorbeeldwoningen"): each band shares building regulations and so roughly
# shares insulation level, materials and morphology.
CONSTRUCTION_PERIODS = [
    ('pre_1945',  'before 1945', None, 1944),
    ('1945_1974', '1945–1974',   1945, 1974),
    ('1975_1991', '1975–1991',   1975, 1991),
    ('1992_2005', '1992–2005',   1992, 2005),
    ('post_2005', 'after 2005',  2006, None),
]

BUILDING_TYPES = ['residential', 'commercial', 'industrial', 'institutional', 'mixed']
STREET_CLASSES = ['primary', 'secondary', 'residential']
FACILITY_TYPES = [code for code, _label in Facility._meta.get_field('type').choices]


def _pct(part, total):
    return round(part / total * 100, 1) if total else 0


# -- Building stock -------------------------------------------------------------

def calculate_building_stock(adminBund):
    """Size, density and form of the building stock in an admin unit.

    Built-up coverage = total footprint ÷ unit area; floor-area ratio (FAR)
    = Σ footprint × floors ÷ unit area, falling back to height ÷ 3 m per
    storey for buildings without a floor count.

    DAG edges:  Urbanization -> Buildings
                Buildings    -> DSM            (height, the input SOLWEIG needs)
                Buildings    -> Canyon_Aspect  (height feeds the H/W ratio)
    """
    buildings = Building.objects.filter(neighborhood__in=neighborhoods_within(adminBund))

    # Storeys per building: its floor count, else height ÷ 3 m (at least one),
    # else one. PostgreSQL's GREATEST ignores NULL, so a missing height gives 1.
    storeys = Coalesce(
        Cast('numberFloors', FloatField()),
        Greatest(Round(F('height_m') / 3.0), Value(1.0)),
        output_field=FloatField(),
    )
    agg = buildings.aggregate(
        count=Count('id'),
        footprint=Sum('area_sqm'),
        floor_area=Sum(F('area_sqm') * storeys, output_field=FloatField()),
        units=Sum('numberUnits'),
        avg_height=Avg('height_m'),
        avg_floors=Avg('numberFloors'),
        vacant=Count('id', filter=Q(vacant=True)),
    )
    floor_area = agg['floor_area'] or 0

    unit_area_m2 = (adminBund.area_km2 or 0) * 1e6
    footprint = agg['footprint'] or 0
    count = agg['count'] or 0

    return {
        'total_buildings': count,
        'total_footprint_m2': round(footprint),
        'total_floor_area_m2': round(floor_area),
        'total_units': agg['units'] or 0,
        'built_coverage_pct': _pct(footprint, unit_area_m2),
        'floor_area_ratio': round(floor_area / unit_area_m2, 2) if unit_area_m2 else None,
        'avg_height_m': round(agg['avg_height'], 1) if agg['avg_height'] else None,
        'avg_floors': round(agg['avg_floors'], 1) if agg['avg_floors'] else None,
        'vacant_buildings': agg['vacant'] or 0,
        'vacant_pct': _pct(agg['vacant'] or 0, count),
        'unit_area_km2': round(adminBund.area_km2, 2) if adminBund.area_km2 else None,
    }


def calculate_building_mix(adminBund):
    """Share of buildings and footprint per coarse building type (from BAG usage).

    DAG edges:  Urbanization -> Buildings
    """
    buildings = Building.objects.filter(neighborhood__in=neighborhoods_within(adminBund))
    rows = {
        r['buildingType']: r
        for r in buildings.values('buildingType').annotate(count=Count('id'), footprint=Sum('area_sqm'))
    }
    total = sum(r['count'] for r in rows.values())
    return {
        'total': total,
        'by_type': {
            t: {
                'count': rows.get(t, {}).get('count', 0),
                'count_pct': _pct(rows.get(t, {}).get('count', 0), total),
                'footprint_m2': round(rows.get(t, {}).get('footprint') or 0),
            }
            for t in BUILDING_TYPES
        },
        'unclassified': total - sum(rows.get(t, {}).get('count', 0) for t in BUILDING_TYPES),
    }


def calculate_building_age(adminBund):
    """Distribution of construction years over the Dutch typology periods.

    DAG edges:  (none — descriptive; building age is a proxy for insulation
                level and renovation need, not yet a DAG node)
    """
    buildings = Building.objects.filter(
        neighborhood__in=neighborhoods_within(adminBund), constructionYear__isnull=False)

    filters = {}
    for key, _label, start, end in CONSTRUCTION_PERIODS:
        q = Q()
        if start is not None:
            q &= Q(constructionYear__gte=start)
        if end is not None:
            q &= Q(constructionYear__lte=end)
        filters[key] = Count('id', filter=q)

    agg = buildings.aggregate(dated=Count('id'), avg_year=Avg('constructionYear'), **filters)
    dated = agg['dated'] or 0

    return {
        'dated_buildings': dated,
        'avg_construction_year': round(agg['avg_year']) if agg['avg_year'] else None,
        'periods': [
            {'key': key, 'label': label, 'count': agg[key] or 0, 'pct': _pct(agg[key] or 0, dated)}
            for key, label, _start, _end in CONSTRUCTION_PERIODS
        ],
    }


# -- Street network -------------------------------------------------------------

def calculate_street_network(adminBund):
    """Street length (clipped to the unit) and density per classification.

    Streets carry no admin FK, so each one counts with the length of its
    intersection with the unit — a street crossing a boundary is split,
    never duplicated.

    DAG edges:  Urbanization -> Streets
                Streets      -> Accessibility   (density, as its first input)
    """
    streets = Street.objects.filter(geom__intersects=adminBund.geom)
    rows = streets.values('classification').annotate(
        length=Sum(Length(Intersection('geom', adminBund.geom)), output_field=FloatField()),
        count=Count('id'),
    )
    by_class = {r['classification']: (r['length'] or 0) / 1000 for r in rows}
    total_km = sum(by_class.values())
    area_km2 = adminBund.area_km2 or 0

    return {
        'total_length_km': round(total_km, 1),
        'street_density_km_km2': round(total_km / area_km2, 1) if area_km2 else None,
        'by_class': {
            c: {'length_km': round(by_class.get(c, 0), 1), 'pct': _pct(by_class.get(c, 0), total_km)}
            for c in STREET_CLASSES
        },
    }


# -- Green space & facilities -------------------------------------------------

def calculate_green_space(adminBund, population):
    """Park area per inhabitant, against the WHO guideline of ≥ 9 m² per person.

    DAG edges:  LandCover  -> Green_Area
                Green_Area -> Accessibility
    """
    parks = Park.objects.filter(neighborhood__in=neighborhoods_within(adminBund))
    agg = parks.aggregate(area=Sum('area'), count=Count('id'))
    area = agg['area'] or 0
    return {
        'park_area_m2': round(area),
        'park_count': agg['count'] or 0,
        'park_area_per_capita_m2': round(area / population, 1) if population else None,
        'park_share_pct': _pct(area, (adminBund.area_km2 or 0) * 1e6),
    }


def calculate_facilities(adminBund, population):
    """Urban facilities by type, and per 10 000 inhabitants.

    DAG edges:  Facilities -> Accessibility
    """
    facilities = Facility.objects.filter(neighborhood__in=neighborhoods_within(adminBund))
    counts = dict(facilities.values_list('type').annotate(n=Count('id')))
    total = sum(counts.values())
    return {
        'total_facilities': total,
        'facilities_per_10k': round(total / population * 10_000, 1) if population else None,
        'by_type': {t: counts.get(t, 0) for t in FACILITY_TYPES},
    }
