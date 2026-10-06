from django.shortcuts import render
from django.http import JsonResponse

from administrative.admin_units import resolve_admin_unit, ADMIN_LEVELS
from administrative.population import DEFAULT_SCENARIO, get_population, population_params
from mainMap.views import BUILDING_TYPE_COLORS, BUILDING_TYPE_LABELS, LAYER_STYLES
from .calculations import (
    calculate_building_stock,
    calculate_building_mix,
    calculate_building_age,
    calculate_street_network,
    calculate_green_space,
    calculate_facilities,
)


# WHO Europe guideline: at least 9 m² of green space per inhabitant
# (ideally 50 m²), used for the green-space gauge colour bands.
GREEN_PER_CAPITA_MIN_M2 = 9
GREEN_PER_CAPITA_GOOD_M2 = 50


# Card colours = the matching map layer's colour (mainMap/views.py LAYER_STYLES),
# so a card and the layer it summarises read as the same thing.
LAYER_COLORS = {
    name: LAYER_STYLES[f'builtup.{model}']['color']
    for name, model in (('building', 'Building'), ('street', 'Street'),
                        ('park', 'Park'), ('facility', 'Facility'))
}


# -- shared helper ------------------------------------------------------------

def _get_adminUnit_data(level, location, year, pop_scenario=DEFAULT_SCENARIO, pop_growth=0.0):
    """
    Fetch all built-up DB values for an administrative unit.

    The building stock is the current one (no year on Building/Street/Park);
    `year` and the population what-if only drive the per-capita indicators,
    through the projected population.
    """
    adminUnit = resolve_admin_unit(level, location)
    if adminUnit is None:
        return None

    population = get_population(adminUnit, year, pop_scenario, pop_growth)
    return {
        'adminUnit': adminUnit,
        'population': population,
        'stock': calculate_building_stock(adminUnit),
        'mix': calculate_building_mix(adminUnit),
        'age': calculate_building_age(adminUnit),
        'streets': calculate_street_network(adminUnit),
        'green': calculate_green_space(adminUnit, population),
        'facilities': calculate_facilities(adminUnit, population),
    }


MOCK_DATA = {
    'adminUnit': type('adminUnit', (), {
        'adminUnitName': 'Demo', 'currentPopulation': 160_000,
    })(),
    'population': 160_000,
    'stock': {
        'total_buildings': 52_000, 'total_footprint_m2': 9_400_000,
        'total_floor_area_m2': 21_000_000, 'total_units': 76_000,
        'built_coverage_pct': 6.1, 'floor_area_ratio': 0.14,
        'avg_height_m': 8.7, 'avg_floors': 2.4,
        'vacant_buildings': 780, 'vacant_pct': 1.5, 'unit_area_km2': 154.0,
    },
    'mix': {
        'total': 52_000,
        'by_type': {
            'residential':   {'count': 41_000, 'count_pct': 78.8, 'footprint_m2': 5_100_000},
            'commercial':    {'count': 4_300,  'count_pct': 8.3,  'footprint_m2': 1_600_000},
            'industrial':    {'count': 1_900,  'count_pct': 3.7,  'footprint_m2': 1_700_000},
            'institutional': {'count': 1_200,  'count_pct': 2.3,  'footprint_m2': 600_000},
            'mixed':         {'count': 2_100,  'count_pct': 4.0,  'footprint_m2': 400_000},
        },
        'unclassified': 1_500,
    },
    'age': {
        'dated_buildings': 51_000, 'avg_construction_year': 1972,
        'periods': [
            {'key': 'pre_1945',  'label': 'before 1945', 'count': 7_100,  'pct': 13.9},
            {'key': '1945_1974', 'label': '1945–1974',   'count': 16_800, 'pct': 32.9},
            {'key': '1975_1991', 'label': '1975–1991',   'count': 12_400, 'pct': 24.3},
            {'key': '1992_2005', 'label': '1992–2005',   'count': 9_200,  'pct': 18.0},
            {'key': 'post_2005', 'label': 'after 2005',  'count': 5_500,  'pct': 10.8},
        ],
    },
    'streets': {
        'total_length_km': 1_150.0, 'street_density_km_km2': 7.5,
        'by_class': {
            'primary':     {'length_km': 120.0, 'pct': 10.4},
            'secondary':   {'length_km': 260.0, 'pct': 22.6},
            'residential': {'length_km': 770.0, 'pct': 67.0},
        },
    },
    'green': {
        'park_area_m2': 2_900_000, 'park_count': 64,
        'park_area_per_capita_m2': 18.1, 'park_share_pct': 1.9,
    },
    'facilities': {
        'total_facilities': 210, 'facilities_per_10k': 13.1,
        'by_type': {'school': 72, 'hospital': 3, 'fire_station': 6,
                    'police_station': 4, 'market': 95, 'transportNode': 30},
    },
}


# -- shared calculation -------------------------------------------------------

def _build_indicators(data, green_added_ha=None):
    """Pure function: takes DB data dict, returns flat indicators dict.

    `green_added_ha` is the what-if: extra park area (hectares) added on top
    of the stored parks, re-deriving green space per inhabitant and the park
    share of the unit's area.
    """
    stock = data['stock']
    mix = data['mix']
    age = data['age']
    streets = data['streets']
    green = data['green']
    fac = data['facilities']
    population = data.get('population')

    added_m2 = (green_added_ha or 0) * 10_000
    park_area = green['park_area_m2'] + added_m2
    per_capita = green.get('park_area_per_capita_m2')
    park_share = green.get('park_share_pct', 0)
    if added_m2:
        if population:
            per_capita = round(park_area / population, 1)
        if stock.get('unit_area_km2'):
            park_share = round(park_area / (stock['unit_area_km2'] * 1e6) * 100, 1)

    if per_capita is None:
        green_status = None
    elif per_capita < GREEN_PER_CAPITA_MIN_M2:
        green_status = 'bad'
    elif per_capita < GREEN_PER_CAPITA_GOOD_M2:
        green_status = 'warn'
    else:
        green_status = 'ok'

    # Same order, labels and colours as the Building layer's map legend
    # (mainMap/views.py); 'unknown' holds the buildings without usage data.
    types = mix['by_type']
    mix_total = mix['total']
    mix_segments = [
        {
            'key': key,
            'label': label,
            'color': BUILDING_TYPE_COLORS[key],
            'pct': (round(mix['unclassified'] / mix_total * 100, 1) if mix_total else 0)
                   if key == 'unknown' else types[key]['count_pct'],
        }
        for key, label in BUILDING_TYPE_LABELS
    ]
    return {
        'population': population,

        # -- Building stock --
        'total_buildings': stock['total_buildings'],
        'total_footprint_m2': stock['total_footprint_m2'],
        'total_floor_area_m2': stock['total_floor_area_m2'],
        'total_units': stock['total_units'],
        'built_coverage_pct': stock['built_coverage_pct'],
        'floor_area_ratio': stock['floor_area_ratio'],
        'avg_height_m': stock['avg_height_m'],
        'avg_floors': stock['avg_floors'],
        'vacant_buildings': stock['vacant_buildings'],
        'vacant_pct': stock['vacant_pct'],
        'unit_area_km2': stock['unit_area_km2'],
        'units_per_1000': round(stock['total_units'] / population * 1000, 1) if population else None,

        # -- Building mix --
        'mix_total': mix['total'],
        'mix_unclassified': mix['unclassified'],
        'mix_segments': mix_segments,
        'layer_colors': LAYER_COLORS,

        # -- Building age --
        'dated_buildings': age['dated_buildings'],
        'avg_construction_year': age['avg_construction_year'],
        'age_periods': age['periods'],

        # -- Streets --
        'street_length_km': streets['total_length_km'],
        'street_density': streets['street_density_km_km2'],
        'street_primary_pct': streets['by_class']['primary']['pct'],
        'street_secondary_pct': streets['by_class']['secondary']['pct'],
        'street_residential_pct': streets['by_class']['residential']['pct'],

        # -- Green space (what-if) --
        'green_added_ha': green_added_ha or 0,
        'park_area_ha': round(park_area / 10_000, 1),
        'park_count': green['park_count'],
        'park_share_pct': park_share,
        'green_per_capita_m2': per_capita,
        'green_status': green_status,
        'green_min_m2': GREEN_PER_CAPITA_MIN_M2,
        'green_good_m2': GREEN_PER_CAPITA_GOOD_M2,

        # -- Facilities --
        'total_facilities': fac['total_facilities'],
        'facilities_per_10k': fac['facilities_per_10k'],
        'facility_counts': fac['by_type'],
    }


# -- views --------------------------------------------------------------------

def _parse_green_added(request):
    try:
        return max(float(request.GET.get('green_added_ha', 0)), 0.0)
    except ValueError:
        return 0.0


def builtup_indicators(request, level, location, year):
    pop_scenario, pop_growth = population_params(request.GET)
    data = _get_adminUnit_data(level, location, year, pop_scenario, pop_growth)
    if data is None:
        data = MOCK_DATA

    context = {
        'adminUnit': data['adminUnit'],
        'level': level,
        'location': location,
        'year': year,
        'indicators': _build_indicators(data),
        'pop_scenario': pop_scenario,
        'pop_growth': pop_growth,
    }

    if request.headers.get('HX-Request'):
        return render(request, 'builtup/partials/indicators_panel.html', context)
    return render(request, 'builtup/builtup_indicators.html', context)


def recalculate_indicators(request, level, location, year):
    pop_scenario, pop_growth = population_params(request.GET)
    data = _get_adminUnit_data(level, location, year, pop_scenario, pop_growth)
    if data is None:
        data = MOCK_DATA

    indicators = _build_indicators(data, green_added_ha=_parse_green_added(request))
    return render(request, 'builtup/partials/indicators_grid.html', {'indicators': indicators})


def builtup_indicators_json(request, level, location, year):
    """JSON endpoint for programmatic access to built-up indicators."""
    data = _get_adminUnit_data(level, location, year)
    if data is None:
        return JsonResponse({'error': 'Administrative unit not found', 'using_mock': True,
                             'indicators': _build_indicators(MOCK_DATA)})

    name_field = ADMIN_LEVELS.get(level, (None, None))[1]
    name = getattr(data['adminUnit'], name_field, None) if name_field else str(data['adminUnit'])
    return JsonResponse({
        'adminUnit': name,
        'year': year,
        'indicators': _build_indicators(data),
    })
