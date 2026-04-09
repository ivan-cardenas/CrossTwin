from django.shortcuts import get_object_or_404, render
from django.http import JsonResponse, Http404
from django.core.serializers import serialize
from django.contrib.gis.db import models as gis_models
from django.db import connection
from django.db.models import Sum, Avg
from django.apps import apps

from .models import *
from common.models import Province as PM
from .calculations import (
    _get_consumption_capita,
    calculate_supply_security,
    calculate_total_extraction,
    calculate_total_production_day,
    calculate_energy_consumption,
    calculate_co2_emission,
    calculate_water_quality,
    calculate_collection_ratio,
    calculate_opex_recovery,
    calculate_coverage,
    calculate_nrw,
    calculate_available_freshwater,
    calculate_drought_area,
)
from django.contrib.gis.db.models.functions import Intersection, Length
from django.contrib.gis.measure import D

# ── constants ─────────────────────────────────────────────────────────
SERVICE_HOURS_MAX = 24
MAX_OPEX_EUR      = 10_000_000
MAX_CONSUMPTION   = 300

# ── shared helper ─────────────────────────────────────────────────────
def _get_province_data(location, year):
    """Fetch all fixed DB values for a province/year. Returns a dict."""
    try:
        province = PM.objects.get(ProvinceName=location)
    except PM.DoesNotExist:
        return None

    imported_water_m3_yr = (
        ImportedWater.objects.filter(is_active=True)
        .aggregate(total=Sum('quantity_m3_d'))['total'] or 0
    ) * 365

    available_water_Mm3 = calculate_available_freshwater(province)

    network_length = (
        PipeNetwork.objects
        .filter(geom__intersects=province.geom)
        .annotate(clipped=Intersection('geom', province.geom))
        .annotate(clipped_length=Length('clipped'))
        .aggregate(total=Sum('clipped_length'))['total']
    )

    demand_m3_d, supply_m3_d, supply_security = calculate_supply_security(province)

    # OPEX: average across active wells
    avg_opex_m3 = (
        ExtractionWater.objects.filter(is_active=True, opex_EUR_m3__isnull=False)
        .aggregate(avg=Avg('opex_EUR_m3'))['avg'] or 0
    )
    supply_m3_yr = (supply_m3_d or 0) * 365
    opex_total = supply_m3_yr * avg_opex_m3

    # NRW breakdown
    nrw = calculate_nrw(year)

    # Energy & emissions (DAG: Total_Extraction → Energy_Consumption, CO2_Emission)
    energy_kwh_day = calculate_energy_consumption(province)
    co2_kg_day = calculate_co2_emission(province)

    # Water quality (DAG: Samples_Taken → Samples_WQ → User_Acceptance_WS)
    water_quality = calculate_water_quality(year)

    # Collection ratio (DAG: Metered_Res_Water → CollectionRatio)
    collection_ratio = calculate_collection_ratio(province)

    # OPEX recovery (DAG: OPEX → OPEX_Recovery)
    opex_recovery = calculate_opex_recovery(year, province)

    # Coverage (DAG: Network → Coverage_WS_Area → NumberUsers → Coverage_WS)
    coverage = calculate_coverage(province)

    # Drought (DAG: Total_Extraction → Area_Drought)
    drought = calculate_drought_area(province, year)

    # Total extraction (DAG: Available_FW → Total_Extraction)
    extraction_m3_d = calculate_total_extraction(province)

    return {
        'province':             province,
        'population':           province.currentPopulation,
        'consumption_capita':   _get_consumption_capita(province, year),
        'demand_m3_d':          demand_m3_d,
        'supply_m3_d':          supply_m3_d,
        'supply_security':      supply_security,
        'imported_water_m3_yr': imported_water_m3_yr,
        'available_water_Mm3':  available_water_Mm3,
        'opex_total':           opex_total,
        'network_length':       network_length.km if network_length else 0,
        'nrw_m3_d':             nrw['total_nrw_m3_d'],
        'apparent_losses_m3_d': nrw['apparent_losses_m3_d'],
        'real_losses_m3_d':     nrw['real_losses_m3_d'],
        'ili':                  nrw['ili'],
        # ── New DAG-derived fields ──
        'extraction_m3_d':      extraction_m3_d,
        'energy_kwh_day':       energy_kwh_day,
        'co2_kg_day':           co2_kg_day,
        'water_quality':        water_quality,
        'collection_ratio':     collection_ratio,
        'opex_recovery':        opex_recovery,
        'coverage':             coverage,
        'drought':              drought,
    }

_MOCK_OPEX_M3 = 0.07  # EUR/m3
_MOCK_SUPPLY_M3_D = 20_000

MOCK_DATA = {
    'province':             type('Province', (), {'ProvinceName': 'Demo', 'currentPopulation': 500_000})(),
    'population':           500_000,
    'consumption_capita':   100,
    'supply_m3_d':          _MOCK_SUPPLY_M3_D,
    'imported_water_m3_yr': 50,
    'available_water_Mm3':  100,
    'opex_total':           _MOCK_SUPPLY_M3_D * 365 * _MOCK_OPEX_M3,
    'network_length':       5_000,
    'nrw_m3_d':             3_200,
    'apparent_losses_m3_d': 1_200,
    'real_losses_m3_d':     2_000,
    'ili':                  3.5,
    'extraction_m3_d':      18_000,
    'energy_kwh_day':       4_500,
    'co2_kg_day':           2_250,
    'water_quality':        {
        'samples_taken': 120, 'samples_ok': 114,
        'compliance_pct': 95.0, 'treatment_efficiency': 98.5,
        'acceptance_rate': 92.0,
    },
    'collection_ratio':     85.0,
    'opex_recovery':        {
        'revenue_EUR': 380_000, 'total_opex_EUR': 511_000,
        'recovery_pct': 74.4,
    },
    'coverage':             {
        'covered_area_km2': 42.5, 'households_covered': 4_200,
        'households_total': 5_000, 'coverage_pct': 84.0,
    },
    'drought':              {'total_area_km2': 12.3, 'max_sensibility': 2},
}

# ── shared calculation ────────────────────────────────────────────────
def _build_indicators(data, consumption_override=None):
    """Pure function: takes DB data dict, returns indicators dict."""
    consumption  = (consumption_override or data['consumption_capita'])
    demand_m3_d  = consumption / 1000 * data['population']
    supply_m3_d  = data['supply_m3_d']
    available    = data['available_water_Mm3']
    opex_total   = data['opex_total']

    demand_Mm3_yr  = demand_m3_d  * 365 / 1_000_000
    supply_Mm3_yr  = supply_m3_d  * 365 / 1_000_000

    service_time = (
        SERVICE_HOURS_MAX if supply_m3_d >= demand_m3_d
        else round(SERVICE_HOURS_MAX * supply_m3_d / demand_m3_d, 1)
    )

    # NRW as percentage of supply
    nrw_m3_d = data.get('nrw_m3_d', 0)
    nrw_percent = round(nrw_m3_d / supply_m3_d * 100, 1) if supply_m3_d else 0

    # Water quality
    wq = data.get('water_quality', {})
    # Coverage
    cov = data.get('coverage', {})
    # OPEX recovery
    opex_rec = data.get('opex_recovery', {})
    # Drought
    drought = data.get('drought', {})

    return {
        # ── Existing indicators ──
        'consumption_capita':    consumption,
        'consumption_percent':   min(consumption / MAX_CONSUMPTION * 100, 100),
        'total_supply_Mm3':      round(supply_Mm3_yr, 2),
        'total_demand_Mm3':      round(demand_Mm3_yr, 2),
        'total_supply_percent':  round(min(supply_Mm3_yr / available * 100, 100), 1) if available else 0,
        'total_demand_percent':  round(min(demand_Mm3_yr / available * 100, 100), 1) if available else 0,
        'supply_security':       supply_Mm3_yr / demand_Mm3_yr * 100 if demand_Mm3_yr else 0,
        'service_time':          service_time,
        'service_time_percent':  round(service_time / SERVICE_HOURS_MAX * 100, 1),
        'network_length':        data['network_length'],
        'opex':                  opex_total,
        'opex_percent':          min(opex_total / MAX_OPEX_EUR * 100, 100),
        'nrw_m3_d':              round(nrw_m3_d, 1),
        'nrw_percent':           nrw_percent,
        'apparent_losses_m3_d':  round(data.get('apparent_losses_m3_d', 0), 1),
        'real_losses_m3_d':      round(data.get('real_losses_m3_d', 0), 1),
        'ili':                   data.get('ili'),
        # ── New DAG indicators ──
        'extraction_m3_d':       round(data.get('extraction_m3_d', 0), 1),
        'energy_kwh_day':        round(data.get('energy_kwh_day', 0), 1),
        'co2_kg_day':            round(data.get('co2_kg_day', 0), 1),
        'co2_ton_yr':            round(data.get('co2_kg_day', 0) * 365 / 1000, 2),
        # Water quality
        'samples_taken':         wq.get('samples_taken', 0),
        'samples_ok':            wq.get('samples_ok', 0),
        'compliance_pct':        wq.get('compliance_pct'),
        'treatment_efficiency':  wq.get('treatment_efficiency'),
        'acceptance_rate':       wq.get('acceptance_rate'),
        # Collection & recovery
        'collection_ratio':      data.get('collection_ratio'),
        'opex_revenue_EUR':      opex_rec.get('revenue_EUR', 0),
        'opex_recovery_pct':     opex_rec.get('recovery_pct'),
        # Coverage
        'covered_area_km2':      cov.get('covered_area_km2', 0),
        'households_covered':    cov.get('households_covered', 0),
        'households_total':      cov.get('households_total', 0),
        'coverage_pct':          cov.get('coverage_pct'),
        # Drought
        'drought_area_km2':      drought.get('total_area_km2', 0),
        'drought_sensibility':   drought.get('max_sensibility', 0),
    }


# ── views ─────────────────────────────────────────────────────────────
def water_indicators(request, location, year):
    data = _get_province_data(location, year)
    if data is None:
        data = MOCK_DATA

    context = {
        'Province':   data['province'],
        'year':       year,
        'indicators': _build_indicators(data),
    }

    if request.headers.get('HX-Request'):
        return render(request, 'watersupply/partials/indicators_panel.html', context)
    return render(request, 'watersupply/water_indicators.html', context)


def recalculate_indicators(request, location, year):
    consumption = float(request.GET.get('consumption', 120))
    data = _get_province_data(location, year)
    if data is None:
        data = MOCK_DATA

    indicators = _build_indicators(data, consumption_override=consumption)

    return render(request, 'watersupply/partials/indicators_grid.html', {'indicators': indicators})
