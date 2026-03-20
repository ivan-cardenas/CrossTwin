from django.shortcuts import get_object_or_404, render
from django.http import JsonResponse, Http404
from django.core.serializers import serialize
from django.contrib.gis.db import models as gis_models
from django.db import connection
from django.apps import apps

from .models import *
from common.models import Province as PM
from .calculations import _get_consumption_capita, calculate_supply_security
# Create your views here.
from django.contrib.gis.db.models.functions import Intersection, Length
from django.contrib.gis.measure import D

# ── constants ─────────────────────────────────────────────────────────
SERVICE_HOURS_MAX = 24
MAX_OPEX_EUR      = 10_000_000
MAX_CONSUMPTION   = 300

# ── shared helper ─────────────────────────────────────────────────────
def _get_province_data(location, year):
    """Fetch all fixed DB values for a province/year. Returns a dict."""
    province = get_object_or_404(PM, ProvinceName=location)
    
    imported_water_m3_yr = (
        ImportedWater.objects.filter(is_active=True)
        .aggregate(total=models.Sum('quantity_m3_d'))['total'] or 0
    ) * 365

    available_water_Mm3 = (
        AvailableFreshWater.objects
        .filter(geom__intersects=province.geom)
        .aggregate(total=Sum('totalQuantity_Mm3'))['total'] or 0
    )

    opex_total = (
        OPEX.objects.filter(year=year)
        .aggregate(total=models.Sum('totalOPEX_EUR'))['total'] or 0
    )

    network_length = (
        PipeNetwork.objects
        .filter(geom__intersects=province.geom)
        .annotate(clipped=Intersection('geom', province.geom))
        .annotate(clipped_length=Length('clipped'))
        .aggregate(total=Sum('clipped_length'))['total']
    )

    demand_m3_d, supply_m3_d, supply_security = calculate_supply_security(province)

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
    }

MOCK_DATA = {
    'province':             type('Province', (), {'ProvinceName': 'Demo', 'currentPopulation': 500_000})(),
    'population':           500_000,
    'consumption_capita':   100,
    'supply_m3_d':          20_000,
    'imported_water_m3_yr': 50,
    'available_water_Mm3':  100,
    'opex_total':           10_000,
    'network_length':       5_000,
}

# ── shared calculation ────────────────────────────────────────────────
def _build_indicators(data, consumption_override=None):
    """Pure function: takes DB data dict, returns indicators dict."""
    consumption  = (consumption_override or data['consumption_capita'])/1000
    demand_m3_d  = consumption * data['population']
    supply_m3_d  = data['supply_m3_d']
    available    = data['available_water_Mm3']
    opex_total   = data['opex_total']

    demand_Mm3_yr  = demand_m3_d  * 365 / 1_000_000
    supply_Mm3_yr  = supply_m3_d  * 365 / 1_000_000

    service_time = (
        SERVICE_HOURS_MAX if supply_m3_d >= demand_m3_d
        else round(SERVICE_HOURS_MAX * supply_m3_d / demand_m3_d, 1)
    )

    return {
        'consumption_capita':    consumption,
        'consumption_percent':   min(consumption / MAX_CONSUMPTION * 100, 100),
        'total_supply_Mm3':      round(supply_Mm3_yr, 2),
        'total_demand_Mm3':      round(demand_Mm3_yr, 2),
        'total_supply_percent':  round(min(supply_Mm3_yr / available * 100, 100), 1) if available else 0,
        'total_demand_percent':  round(min(demand_Mm3_yr / available * 100, 100), 1) if available else 0,  # ← missing
        'supply_security':       supply_Mm3_yr/demand_Mm3_yr * 100,
        'service_time':          service_time,
        'service_time_percent':  round(service_time / SERVICE_HOURS_MAX * 100, 1),
        'network_length':        data['network_length'],
        'opex':                  opex_total,
        'opex_percent':          min(opex_total / MAX_OPEX_EUR * 100, 100),
    }


# ── views ─────────────────────────────────────────────────────────────
def water_indicators(request, location, year):
    try:
        data = _get_province_data(location, year)
    except Exception as e:
        print(f"[water_indicators] mock fallback: {e}")
        data = MOCK_DATA

    context = {
        'Province':   data['province'],
        'year':       year,
        'indicators': _build_indicators(data),
    }
    return render(request, 'watersupply/water_indicators.html', context)


def recalculate_indicators(request, location, year):
    consumption = float(request.GET.get('consumption', 120))

    try:
        data = _get_province_data(location, year)
    except Exception as e:
        print(f"[recalculate] mock fallback: {e}")
        data = MOCK_DATA

    indicators = _build_indicators(data, consumption_override=consumption)
    print(f"[recalculate] indicators: {indicators}")
    return render(request, 'watersupply/partials/indicators_grid.html', {'indicators': indicators})