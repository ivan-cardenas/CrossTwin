from django.shortcuts import render
from django.http import JsonResponse

from common.models import Province as PM
from .calculations import (
    calculate_supply_demand_province,
    calculate_new_units_province,
    calculate_mortgage_indicators,
    calculate_rent_indicators,
    calculate_house_price_index,
    calculate_property_indicators,
    calculate_zoning,
    calculate_affordability,
)


# -- shared helper ------------------------------------------------------------

def _get_province_data(location, year):
    """Fetch all housing-related DB values for a province/year."""
    try:
        province = PM.objects.get(ProvinceName=location)
    except PM.DoesNotExist:
        return None

    supply_demand = calculate_supply_demand_province(province, year)
    new_units = calculate_new_units_province(province, year)
    mortgage = calculate_mortgage_indicators(province, year)
    rent = calculate_rent_indicators(province)
    hpi = calculate_house_price_index(province, year)
    property_ind = calculate_property_indicators(province)
    zoning = calculate_zoning(province)
    affordability = calculate_affordability(province, year)

    return {
        'province': province,
        'population': province.currentPopulation,
        'supply_demand': supply_demand,
        'new_units': new_units,
        'mortgage': mortgage,
        'rent': rent,
        'hpi': hpi,
        'property': property_ind,
        'zoning': zoning,
        'affordability': affordability,
    }


MOCK_DATA = {
    'province': type('Province', (), {
        'ProvinceName': 'Demo', 'currentPopulation': 500_000,
    })(),
    'population': 500_000,
    'supply_demand': {
        'supply_units': 180_000, 'demand_units': 210_000,
        'deficit': 30_000, 'deficit_pct': 14.3,
    },
    'new_units': {
        'completed_units': 2_500, 'completed_projects': 12,
        'pipeline_units': 4_800, 'pipeline_projects': 18,
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

def _build_indicators(data, interest_rate_override=None):
    """Pure function: takes DB data dict, returns flat indicators dict."""
    sd = data['supply_demand']
    nu = data['new_units']
    mtg = data['mortgage']
    rent = data['rent']
    hpi = data['hpi']
    prop = data['property']
    zoning = data['zoning']
    aff = data['affordability']

    # Allow overriding interest rate for what-if scenarios
    effective_rate = interest_rate_override or mtg.get('mortgage_rate')

    # Recalculate monthly payment if interest rate changed
    avg_monthly = mtg.get('avg_monthly_payment')
    if interest_rate_override and mtg.get('avg_loan_amount') and mtg.get('avg_loan_amount') > 0:
        # Standard annuity formula: M = P * r(1+r)^n / ((1+r)^n - 1)
        loan = mtg['avg_loan_amount']
        r = interest_rate_override / 100 / 12  # monthly rate
        n = 30 * 12  # 30-year term default
        if r > 0:
            avg_monthly = round(loan * r * (1 + r) ** n / ((1 + r) ** n - 1), 2)
        else:
            avg_monthly = round(loan / n, 2)

    # Housing deficit as % of demand
    deficit_pct = sd.get('deficit_pct') or 0

    # Affordability: housing cost burden (mortgage or rent / income)
    income = aff.get('avg_median_income')
    cost_burden_pct = None
    if income and income > 0 and avg_monthly:
        cost_burden_pct = round(avg_monthly * 12 / income * 100, 1)

    # Stress distribution totals
    stress = aff.get('stress_distribution', {})
    stress_total = sum(stress.values()) if stress else 0

    return {
        # -- Supply & Demand --
        'supply_units': sd['supply_units'],
        'demand_units': sd['demand_units'],
        'deficit': sd['deficit'],
        'deficit_pct': deficit_pct,

        # -- Pipeline (New Units) --
        'completed_units': nu['completed_units'],
        'completed_projects': nu['completed_projects'],
        'pipeline_units': nu['pipeline_units'],
        'pipeline_projects': nu['pipeline_projects'],

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

def housing_indicators(request, location, year):
    data = _get_province_data(location, year)
    if data is None:
        data = MOCK_DATA

    context = {
        'Province': data['province'],
        'year': year,
        'indicators': _build_indicators(data),
    }

    if request.headers.get('HX-Request'):
        return render(request, 'housing/partials/indicators_panel.html', context)
    return render(request, 'housing/housing_indicators.html', context)


def recalculate_indicators(request, location, year):
    interest_rate = request.GET.get('interest_rate')
    interest_rate = float(interest_rate) if interest_rate else None

    data = _get_province_data(location, year)
    if data is None:
        data = MOCK_DATA

    indicators = _build_indicators(data, interest_rate_override=interest_rate)

    return render(request, 'housing/partials/indicators_panel.html', {'indicators': indicators})


def housing_indicators_json(request, location, year):
    """JSON endpoint for programmatic access to housing indicators."""
    data = _get_province_data(location, year)
    if data is None:
        return JsonResponse({'error': 'Province not found', 'using_mock': True,
                             'indicators': _build_indicators(MOCK_DATA)})

    return JsonResponse({
        'province': data['province'].ProvinceName,
        'year': year,
        'indicators': _build_indicators(data),
    })
