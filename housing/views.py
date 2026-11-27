import logging
import math

from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from administrative.admin_units import resolve_admin_unit, ADMIN_LEVELS
from administrative.models import District, Neighborhood
from administrative.calculations.population import DEFAULT_SCENARIO, get_population, is_extrapolated, population_params
from .calculations import chain, property_price
from .calculations.indicators import (
    calculate_household_size,
    calculate_dwellings,
    calculate_living_alone,
    calculate_supply_demand_for_unit,
    supply_demand_from_dwellings,
    calculate_new_units_for_unit,
    calculate_pipeline_land_take,
    calculate_mortgage_indicators,
    calculate_rent_indicators,
    calculate_house_price_index,
    calculate_price_history,
    price_chart,
    calculate_property_indicators,
    calculate_zoning,
    calculate_affordability,
    calculate_modelled_price,
)


# -- shared helper ------------------------------------------------------------

def _get_adminUnit_data(level, location, year, pop_scenario=DEFAULT_SCENARIO, pop_growth=0.0):
    """
    Fetch all housing-related DB values for an administrative unit/year.

    `population` is the projected population for `year` (CBS variant `pop_scenario`
    plus `pop_growth` % extra growth per year); it equals the current population
    when no projections are imported. `population_baseline` is the same without
    the what-if. Supply and demand units come from the stored HousingSupplyDemand
    records (demand = baseline population / persons per home); `_build_indicators`
    applies the what-ifs on top of them.
    """
    adminUnit = resolve_admin_unit(level, location)
    if adminUnit is None:
        return None

    household = calculate_household_size(adminUnit, year)
    dwellings = calculate_dwellings(adminUnit)
    population_baseline = get_population(adminUnit, year)
    if isinstance(adminUnit, (District, Neighborhood)):
        # the CBS stock is per municipality: below the city, count the mapped dwellings
        supply_demand = supply_demand_from_dwellings(
            dwellings['dwellings'], population_baseline, household['average_size'])
    else:
        supply_demand = calculate_supply_demand_for_unit(adminUnit, year)
    new_units = calculate_new_units_for_unit(adminUnit, year)
    land_take = calculate_pipeline_land_take(adminUnit, year)
    mortgage = calculate_mortgage_indicators(adminUnit, year)
    rent = calculate_rent_indicators(adminUnit)
    hpi = calculate_house_price_index(adminUnit, year)
    price_history = calculate_price_history(adminUnit)
    property_ind = calculate_property_indicators(adminUnit)
    zoning = calculate_zoning(adminUnit)
    affordability = calculate_affordability(adminUnit, year)
    modelled_price = calculate_modelled_price(adminUnit)

    return {
        'adminUnit': adminUnit,
        'population': get_population(adminUnit, year, pop_scenario, pop_growth),
        'population_extrapolated': is_extrapolated(adminUnit, year),
        'population_baseline': population_baseline,
        'household': household,
        'dwellings': dwellings,
        'living_alone': calculate_living_alone(adminUnit),
        'supply_demand': supply_demand,
        'new_units': new_units,
        'land_take': land_take,
        'mortgage': mortgage,
        'rent': rent,
        'hpi': hpi,
        'price_history': price_history,
        'property': property_ind,
        'zoning': zoning,
        'affordability': affordability,
        'modelled_price': modelled_price,
    }


MOCK_DATA = {
    'adminUnit': type('adminUnit', (), {
        'adminUnitName': 'Demo', 'currentPopulation': 500_000,
    })(),
    'population': 500_000,
    'population_baseline': 500_000,
    'household': {'average_size': 2.3, 'year': 2025, 'households': 217_000, 'population': 500_000},
    'dwellings': {'dwellings': 180_000, 'estimated_residents': 414_000},
    'supply_demand': {
        'supply_units': 180_000, 'demand_units': 210_000,
        'deficit': 30_000, 'deficit_pct': 14.3, 'supply_source': 'cbs',
    },
    'new_units': {
        'completed_units': 2_500, 'completed_projects': 12,
        'pipeline_units': 4_800, 'pipeline_projects': 18,
    },
    'land_take': {
        'by_class': [
            {'class_name': 'pastures', 'area_ha': 21.4, 'urban': False},
            {'class_name': 'urban fabric', 'area_ha': 9.8, 'urban': True},
            {'class_name': 'arable land', 'area_ha': 6.1, 'urban': False},
        ],
        'footprint_ha': 38.0, 'greenfield_ha': 27.5, 'infill_ha': 9.8, 'uncovered_ha': 0.7,
    },
    'mortgage': {
        'interest_rate': 3.5, 'ltv_limit': 100.0, 'lti_limit': 4.5,
        'mortgage_rate': 4.2, 'approval_rate': 82.0,
        'avg_down_payment_pct': 10.0,
        'avg_monthly_payment': 1_250.0, 'avg_interest_rate': 4.1,
        'avg_loan_amount': 280_000.0, 'total_mortgages': 1_500,
    },
    'rent': {
        'avg_monthly_rent': 1_100.0, 'avg_annual_rent': 13_200.0,
        'avg_price_to_rent_ratio': 22.5, 'total_rentals': 3_200,
    },
    'hpi': {
        'avg_index': 142.5, 'yoy_change_pct': 5.3,
        'neighborhoods_reported': 45,
    },
    'property': {
        'avg_sale_price': 320_000.0, 'avg_listing_price': 335_000.0,
        'avg_price_sqm': 3_800.0, 'avg_living_area': 85.0,
        'total_properties': 4_500, 'total_units': 180_000,
        'vacant_buildings': 120, 'total_buildings': 8_500,
        'avg_vacancy_rate': 3.2,
    },
    'zoning': {
        'total_area_sqm': 45_000_000,
        'by_type': {
            'residential': {'area_sqm': 28_000_000, 'count': 120, 'area_pct': 62.2, 'avg_benchmark_EUR_sqm': 3_500.0},
            'commercial': {'area_sqm': 8_000_000, 'count': 45, 'area_pct': 17.8, 'avg_benchmark_EUR_sqm': 4_200.0},
            'industrial': {'area_sqm': 5_000_000, 'count': 20, 'area_pct': 11.1, 'avg_benchmark_EUR_sqm': 1_800.0},
            'mixed': {'area_sqm': 4_000_000, 'count': 15, 'area_pct': 8.9, 'avg_benchmark_EUR_sqm': 3_900.0},
        },
    },
    'affordability': {
        'avg_affordability_index': 7.8, 'avg_median_income': 42_000.0,
        'avg_median_expenditure': 28_000.0, 'avg_median_disposable': 14_000.0,
        'avg_median_house_price': 320_000.0, 'avg_median_rent': 1_100.0,
        'avg_median_mortgage': 1_250.0,
        'stress_distribution': {'low': 18, 'moderate': 20, 'high': 7},
        'neighborhoods_reported': 45,
    },
}


# -- shared calculation -------------------------------------------------------

def _screening_rows(model):
    """The amenity terms of a fit for the card: kept ones with their beta first, then the screened-out ones with the reason."""
    terms = ((model.screening or {}).get('terms')) or {}
    kept, dropped = [], []
    for term, info in terms.items():
        mode, category = chain.split_term(term)
        row = {'term': term, 'mode': mode, 'category': category.replace('_', ' '), 'reason': info.get('reason', '')}
        if info.get('status') == 'kept':
            row.update(beta=info.get('beta'), p=info.get('p'), effect_pct=(info.get('effect_per_sd') or 0) * 100,
                       vif=info.get('vif'))
            kept.append(row)
        else:
            dropped.append(row)
    kept.sort(key=lambda r: -(abs(r['beta'] or 0)))
    return kept, sorted(dropped, key=lambda r: (r['reason'], r['term']))


# What the card shows per control: label, the step the effect is quoted for and its unit (the fit's scale of the control).
CONTROL_STEPS = {
    'constructionYear': ('Construction year', 10.0, '+10 years'),
    'energyLabel': ('Energy label', 1.0, 'one label step better'),
    'apartmentShare': ('Share of apartments in the area', 0.1, '+10 percentage points'),
    'rentalShare': ('Share of rentals in the area', 0.1, '+10 percentage points'),
    'ses': ('Socio-economic status', 1.0, '+1 on the CBS scale'),
    'distCentre_km': ('Distance to the municipal centre', 1.0, '+1 km'),
}


def _control_rows(model):
    """The controls of a fit for the card: kept ones with the price change per step, then the dropped ones."""
    spec, coefficients = model.spec or {}, model.coefficients or {}
    kept, dropped = [], []
    for name in spec.get('controls') or []:
        label, step, unit = CONTROL_STEPS.get(name, (name, 1.0, '+1'))
        info = coefficients.get(name) or {}
        beta = info.get('coef')
        kept.append({'control': name, 'label': label, 'step': unit, 'beta': beta, 'p': info.get('p'),
                     'effect_pct': None if beta is None else (math.exp(beta * step) - 1.0) * 100.0})
    if spec.get('controls_requested', True):
        for name in spec.get('dropped_controls') or []:
            dropped.append({'control': name, 'label': CONTROL_STEPS.get(name, (name,))[0],
                            'reason': 'not in the rows, constant, or present for under 80 % of the areas'})
    return kept, dropped


def _modelled_price_indicators(mp, market_growth):
    """The modelled-price card: stored mean, the what-if mean, the fit with its screened terms and the label."""
    model, summary = mp.get('model'), mp.get('summary') or {}
    out = {
        'mp_available': False,
        'mp_label': chain.PRICE_LABEL,
        'mp_growth': market_growth, 'mp_growth_min': chain.MARKET_GROWTH_MIN, 'mp_growth_max': chain.MARKET_GROWTH_MAX,
        'mp_has_model': model is not None,
        'mp_stored_mean': summary.get('stored_mean'),
    }
    if model is not None:
        kept, dropped = _screening_rows(model)
        controls_kept, controls_dropped = _control_rows(model)
        screening = model.screening or {}
        out['mp_model'] = {
            'id': model.pk, 'n': model.n, 'r2': model.r2, 'form': model.form, 'woz_year': model.wozYear,
            'spatial_model': model.spatialModel, 'morans_p': model.moransP, 'diagnostic_passed': model.diagnosticPassed,
            'spline_departs': (model.formComparison or {}).get('spline_departs'),
            'excluded': len((model.spec or {}).get('excluded_low_coverage') or []),
            'candidates': screening.get('candidates'), 'kept': kept, 'dropped': dropped,
            'controls': controls_kept, 'controls_dropped': controls_dropped,
        }
    if model is None or not summary.get('priced'):
        return out
    default = property_price.mean_price(summary)
    whatif = market_growth != 0.0
    shown = property_price.mean_price(summary, market_growth) if whatif else default
    if not shown['priced']:
        return out
    out.update({
        'mp_available': True,
        'mp_price': round(shown['price']),
        'mp_level': round(shown['level']),
        'mp_change_pct': round((shown['price'] / shown['level'] - 1) * 100, 1),
        'mp_default_price': round(default['price']) if default['price'] else None,
        'mp_priced': shown['priced'],
        'mp_whatif': whatif,
    })
    return out


def _build_indicators(data, household_size_override=None, alone_override=None,
                      market_growth=0.0):
    """
    Pure function: takes DB data dict, returns flat indicators dict.

    `alone_override` (% of the residents living alone, the slider; default from CBS
    one-person households) adapts the demand to the neighborhood's household mix:
    those residents take one home each, the others fill homes at the municipality's
    persons per multi-person home (chain.alone_demand_factor); the one-person homes
    are housed first (chain.household_split). `household_size_override` (persons
    per home, the slider) and the population what-ifs already in data['population']
    only deviate from the stored baseline through chain.what_if_demand; nothing is
    written.

    The modelled price (DAG edge Accessibility -> Property) is the mean of the stored values; `market_growth` (%)
    is its what-if, applied with chain.market_growth_factor, the factor of the function that wrote the stored
    values, and never written.
    """
    sd = data['supply_demand']
    household = data.get('household') or {}
    dwellings = data.get('dwellings') or {}
    nu = data['new_units']
    land_take = data.get('land_take') or {}
    mtg = data['mortgage']
    rent = data['rent']
    hpi = data['hpi']
    price_chart_geometry, price_chart_unit = price_chart(data.get('price_history') or {'woz': [], 'index': []})
    prop = data['property']
    zoning = data['zoning']
    aff = data['affordability']

    effective_rate = mtg.get('mortgage_rate')
    avg_monthly = mtg.get('avg_monthly_payment')

    # Housing demand = population / persons per home. The stored baseline is
    # scaled by the what-ifs (population dock, persons-per-home slider).
    stored_size = household.get('average_size')
    size = household_size_override or stored_size
    base_demand = chain.what_if_demand(
        sd['demand_units'], data.get('population'), data.get('population_baseline'),
        stored_size, size) or 0

    # Household mix: the residents living alone (CBS), the slider's default.
    living_alone = data.get('living_alone') or {}
    stored_alone = living_alone.get('pct')
    alone = alone_override if alone_override is not None else stored_alone
    alone_share = alone / 100.0 if alone is not None else None
    multi_size = household.get('multi_person_size')
    factor = chain.alone_demand_factor(size, alone_share, multi_size)
    demand_units = round(base_demand * factor)
    # the residents the baseline demand implies, on the same (CBS) scale as the stock
    residents = base_demand * size if size else None
    single_dwellings, other_homes, other_size = chain.household_split(residents, demand_units, alone_share)

    # Usable supply: the stock minus what does not count as a home (vacant
    # buildings, units below the minimum dwelling area), at the mapped share.
    usable_units = round(sd['supply_units'] * dwellings.get('usable_share', 1.0))
    deficit = demand_units - usable_units
    deficit_pct = round(deficit / demand_units * 100, 1) if demand_units else 0

    # Supply coverage: what share of demand is currently met (gauge display)
    supply_coverage_pct = None
    if demand_units:
        supply_coverage_pct = round(usable_units / demand_units * 100, 1)

    # Affordability: housing cost burden (mortgage or rent / income)
    income = aff.get('avg_median_income')
    cost_burden_pct = None
    if income and income > 0 and avg_monthly:
        cost_burden_pct = round(avg_monthly * 12 / income * 100, 1)

    # Stress distribution totals
    stress = aff.get('stress_distribution', {})
    stress_total = sum(stress.values()) if stress else 0

    modelled = _modelled_price_indicators(data.get('modelled_price') or {}, market_growth)

    return {
        **modelled,
        'population': data.get('population'),
        'population_extrapolated': data.get('population_extrapolated', False),
        # -- Household size (CBS persons per home; the slider) --
        'household_size': round(size, 2) if size else None,
        'household_size_stored': round(stored_size, 2) if stored_size else None,
        'household_size_year': household.get('year'),
        'size_min': chain.SIZE_MIN,
        'size_max': chain.SIZE_MAX,
        'dwellings': dwellings.get('dwellings', 0),
        'estimated_residents': dwellings.get('estimated_residents', 0),
        # residents the supplied homes hold at this size, against the population
        'housed_residents': chain.housed_residents(usable_units, residents, demand_units, alone_share),
        'alone_pct': alone,
        'alone_pct_stored': stored_alone,
        'alone_source': living_alone.get('source'),
        'alone_min': chain.ALONE_MIN,
        'alone_max': chain.ALONE_MAX,
        'single_dwellings': single_dwellings,
        'other_household_size': round(other_size, 2) if other_size else None,
        'multi_person_size': round(multi_size, 2) if multi_size else None,
        'usable_units': usable_units,
        'min_dwelling_area': chain.MIN_DWELLING_AREA_SQM,
        'usable_dwellings': dwellings.get('usable_dwellings', 0),
        # -- Supply & Demand --
        'supply_units': sd['supply_units'],
        'supply_source': sd.get('supply_source', 'cbs'),
        'demand_units': demand_units,
        'deficit': deficit,
        'deficit_pct': deficit_pct,
        'supply_coverage_pct': supply_coverage_pct,

        # -- Pipeline (New Units) --
        'completed_units': nu['completed_units'],
        'completed_projects': nu['completed_projects'],
        'pipeline_units': nu['pipeline_units'],
        'pipeline_projects': nu['pipeline_projects'],
        'pipeline_footprint_ha': land_take.get('footprint_ha', 0.0),
        'pipeline_greenfield_ha': land_take.get('greenfield_ha', 0.0),
        'pipeline_infill_ha': land_take.get('infill_ha', 0.0),
        'pipeline_land_take_classes': [c for c in land_take.get('by_class', []) if not c['urban']][:3],

        # -- Mortgage --
        'interest_rate': mtg.get('interest_rate'),
        'mortgage_rate': effective_rate,
        'ltv_limit': mtg.get('ltv_limit'),
        'lti_limit': mtg.get('lti_limit'),
        'approval_rate': mtg.get('approval_rate'),
        'avg_monthly_payment': avg_monthly,
        'avg_loan_amount': mtg.get('avg_loan_amount'),
        'total_mortgages': mtg.get('total_mortgages', 0),

        # -- Rent --
        'avg_monthly_rent': rent.get('avg_monthly_rent'),
        'avg_annual_rent': rent.get('avg_annual_rent'),
        'avg_price_to_rent_ratio': rent.get('avg_price_to_rent_ratio'),
        'total_rentals': rent.get('total_rentals', 0),

        # -- House Price Index --
        'hpi_value': hpi.get('avg_index'),
        'hpi_yoy_change': hpi.get('yoy_change_pct'),
        'hpi_neighborhoods': hpi.get('neighborhoods_reported', 0),
        'price_chart': price_chart_geometry,
        'price_chart_unit': price_chart_unit,

        # -- Property Market --
        'avg_sale_price': prop.get('avg_sale_price'),
        'avg_listing_price': prop.get('avg_listing_price'),
        'avg_price_sqm': prop.get('avg_price_sqm'),
        'avg_living_area': prop.get('avg_living_area'),
        'total_properties': prop.get('total_properties', 0),
        'total_units': prop.get('total_units', 0),
        'vacant_buildings': prop.get('vacant_buildings', 0),
        'total_buildings': prop.get('total_buildings', 0),
        'vacancy_rate': prop.get('avg_vacancy_rate'),

        # -- Zoning --
        'zoning_total_area_sqm': zoning.get('total_area_sqm', 0),
        'zoning_residential_pct': zoning.get('by_type', {}).get('residential', {}).get('area_pct', 0),
        'zoning_commercial_pct': zoning.get('by_type', {}).get('commercial', {}).get('area_pct', 0),
        'zoning_industrial_pct': zoning.get('by_type', {}).get('industrial', {}).get('area_pct', 0),
        'zoning_mixed_pct': zoning.get('by_type', {}).get('mixed', {}).get('area_pct', 0),
        'zoning_residential_benchmark_EUR_sqm': zoning.get('by_type', {}).get('residential', {}).get('avg_benchmark_EUR_sqm'),

        # -- Affordability --
        'affordability_index': aff.get('avg_affordability_index'),
        'median_income': income,
        'median_expenditure': aff.get('avg_median_expenditure'),
        'median_disposable_income': aff.get('avg_median_disposable'),
        'median_house_price': aff.get('avg_median_house_price'),
        'cost_burden_pct': cost_burden_pct,
        'stress_low': stress.get('low', 0),
        'stress_moderate': stress.get('moderate', 0),
        'stress_high': stress.get('high', 0),
        'stress_total': stress_total,
        'neighborhoods_reported': aff.get('neighborhoods_reported', 0),
    }


# -- views --------------------------------------------------------------------

def _float_param(params, name, low, high, default):
    """A float query parameter clamped to [low, high]; `default` when missing or not a number."""
    try:
        value = float(params.get(name))
    except (TypeError, ValueError):
        return default
    return min(max(value, low), high)


def housing_indicators(request, level, location, year):
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
        'can_fit_price_model': request.user.is_staff,
    }

    if request.headers.get('HX-Request'):
        return render(request, 'housing/partials/indicators_panel.html', context)
    return render(request, 'housing/housing_indicators.html', context)


def recalculate_indicators(request, level, location, year):
    household_size = request.GET.get('household_size')
    try:
        household_size = float(household_size) if household_size else None
    except ValueError:
        household_size = None
    if household_size is not None:
        household_size = min(max(household_size, chain.SIZE_MIN), chain.SIZE_MAX)

    alone = request.GET.get('alone_pct')
    try:
        alone = float(alone) if alone else None
    except ValueError:
        alone = None
    if alone is not None:
        alone = min(max(alone, chain.ALONE_MIN), chain.ALONE_MAX)

    pop_scenario, pop_growth = population_params(request.GET)
    data = _get_adminUnit_data(level, location, year, pop_scenario, pop_growth)
    if data is None:
        data = MOCK_DATA

    indicators = _build_indicators(
        data, household_size_override=household_size, alone_override=alone,
        market_growth=_float_param(request.GET, 'market_growth', chain.MARKET_GROWTH_MIN, chain.MARKET_GROWTH_MAX, 0.0))

    return render(request, 'housing/partials/indicators_grid.html', {
        'indicators': indicators, 'level': level, 'location': location, 'year': year,
        'can_fit_price_model': request.user.is_staff})


def housing_indicators_json(request, level, location, year):
    """JSON endpoint for programmatic access to housing indicators."""
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


# -- accessibility price model (staff) ------------------------------------------

def _model_summary(model, repriced):
    screening = model.screening or {}
    return {
        'id': model.pk, 'n': model.n, 'woz_year': model.wozYear, 'form': model.form, 'r2': model.r2,
        'spatial_model': model.spatialModel, 'morans_p': model.moransP, 'diagnostic_passed': model.diagnosticPassed,
        'terms_kept': screening.get('kept'), 'terms_candidates': screening.get('candidates'),
        'repriced': repriced, 'label': chain.PRICE_LABEL,
        'exploratory': bool((model.spec or {}).get('exploratory')),
    }


@require_POST
def price_model_fit(request):
    """Fit the hedonic model on the newest WOZ year available, make it the active fit and reprice the dwellings (staff)."""
    from .calculations import price_model

    if not request.user.is_staff:
        return JsonResponse({'error': 'Log in as a staff user to fit the price model.'}, status=403)
    exploratory = request.POST.get('mode') == 'exploratory'   # no controls, small minimum, stored but not applied
    try:
        model = price_model.fit_and_store(use_controls=not exploratory, exploratory=exploratory)
    except price_model.PriceModelError as exc:
        return JsonResponse({'error': str(exc)}, status=409)
    except Exception:
        logging.getLogger(__name__).exception('Price model fit failed')
        return JsonResponse({'error': 'The fit failed; see the server log.'}, status=500)
    return JsonResponse(_model_summary(model, model.repriced))


@require_POST
def price_model_refreeze(request):
    """
    Freeze the accessibility baselines of every PC6 postcode area again from the stored accessibility (staff).
    Use it after the accessibility was recomputed with other settings (e.g. a new cut-off): a baseline made
    with the old ones would price that change as an amenity effect. Fit the price model afterwards.
    """
    from .calculations import postcode_woz

    if not request.user.is_staff:
        return JsonResponse({'error': 'Log in as a staff user to freeze the baselines.'}, status=403)
    try:
        rows = postcode_woz.prepare(refreeze=True)
    except ValueError as exc:
        return JsonResponse({'error': str(exc)}, status=409)
    except Exception:
        logging.getLogger(__name__).exception('Re-freezing the baselines failed')
        return JsonResponse({'error': 'Freezing the baselines failed; see the server log.'}, status=500)
    return JsonResponse({'message': f'Baselines frozen again for {len(rows)} postcode areas. Fit the price model next.'})


@require_POST
def price_model_reprice(request):
    """Reprice every dwelling with the active fit, e.g. after a new WOZ year was imported (staff)."""
    from .models import PriceModel

    if not request.user.is_staff:
        return JsonResponse({'error': 'Log in as a staff user to reprice the dwellings.'}, status=403)
    model = PriceModel.active()
    if model is None:
        return JsonResponse({'error': 'No price model is fitted yet.'}, status=409)
    try:
        repriced = property_price.reprice(model=model)
    except Exception:
        logging.getLogger(__name__).exception('Repricing failed')
        return JsonResponse({'error': 'The repricing failed; see the server log.'}, status=500)
    return JsonResponse(_model_summary(model, repriced))
