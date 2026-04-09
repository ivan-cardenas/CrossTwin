from django.db.models import Sum, Avg, F, FloatField, ExpressionWrapper
from django.contrib.gis.db import models as gis_models

from .models import (
    ConsumptionCapita, TotalWaterDemand, ExtractionWater, ImportedWater,
    AvailableFreshWater, PipeNetwork, CoverageWaterSupply, NonRevenueWater,
    WaterTreatment, MeteredResidential, UsersLocation, OPEX,
    TotalWaterProduction,
)
from common.models import City, Province, Neighborhood


# ── Consumption & Demand ─────────────────────────────────────────────

def _get_consumption_capita(province, year):
    """Return per-capita consumption (L/person/day) for a province and year."""
    cities = City.objects.filter(province=province)
    record = (
        ConsumptionCapita.objects
        .filter(city__in=cities, year=year)
        .aggregate(avg=Avg('consumption_capita_L_d'))
    )
    return record['avg'] or 0


def calculate_total_demand(province, year):
    """Total water demand in m³/day across all cities in a province."""
    cities = City.objects.filter(province=province)
    consumption = _get_consumption_capita(province, year)
    population = province.currentPopulation or 0
    # L/person/day → m³/day
    return consumption / 1000 * population


# ── Extraction & Production ──────────────────────────────────────────

def calculate_total_extraction(province):
    """Total active extraction in m³/day from wells within the province.

    DAG edges:  Available_FW → Total_Extraction
    """
    wells = ExtractionWater.objects.filter(
        is_active=True,
        geom__intersects=province.geom,
    )
    total_m3_s = wells.aggregate(total=Sum('pumpflow_m3_s'))['total'] or 0
    return total_m3_s * 86400  # m³/day


def calculate_total_production_day(province=None):
    """Total water production in m³/day (extraction + imported).

    DAG edges:  Total_Extraction → Total_Water_Prod
                Imported_Water   → Total_Water_Prod
    """
    if province:
        extraction_m3_d = calculate_total_extraction(province)
    else:
        total_m3_s = (
            ExtractionWater.objects.filter(is_active=True)
            .aggregate(total=Sum('pumpflow_m3_s'))['total'] or 0
        )
        extraction_m3_d = total_m3_s * 86400

    imported_m3_d = (
        ImportedWater.objects.filter(is_active=True)
        .aggregate(total=Sum('quantity_m3_d'))['total'] or 0
    )
    return extraction_m3_d + imported_m3_d


def calculate_supply_security(province):
    """Supply security: demand vs production.

    DAG edges:  Total_Water_Demand → Supply_Security
                Total_Water_Prod   → Supply_Security
    Returns (demand_m3_d, production_m3_d, security_ratio).
    """
    cities = City.objects.filter(province=province)
    demand = (
        TotalWaterDemand.objects.filter(city__in=cities)
        .aggregate(total=Sum('demandDay'))['total'] or 0
    )
    production = calculate_total_production_day(province)

    if demand and production:
        supply_security = production / demand
    else:
        supply_security = None

    return demand, production, supply_security


# ── Energy & Emissions ───────────────────────────────────────────────

def calculate_energy_consumption(province):
    """Total energy consumption from pumping in kWh/day.

    DAG edges:  Total_Extraction   → Energy_Consumption
                Total_Water_Prod   → Energy_Consumption
                Energy_Cost        → Energy_Consumption
    """
    wells = ExtractionWater.objects.filter(
        is_active=True,
        geom__intersects=province.geom,
    )
    total_kwh_day = wells.aggregate(
        total=Sum(
            ExpressionWrapper(
                F('pumpEnergyRate_kWh_h') * F('OperationTime_h_day'),
                output_field=FloatField(),
            )
        )
    )['total'] or 0

    # Add water treatment energy if available
    wt_energy = (
        WaterTreatment.objects
        .aggregate(total=Sum('EnergyConsumption_MW_day'))['total'] or 0
    ) * 1000  # MW → kWh (×1000 since MW⋅day needs ×24×1000, but field is MW/day)

    return total_kwh_day + wt_energy


def calculate_co2_emission(province):
    """Total CO₂ emissions from extraction pumps in kg CO₂/day.

    DAG edge:  Total_Extraction → CO2_Emission
    """
    wells = ExtractionWater.objects.filter(
        is_active=True,
        geom__intersects=province.geom,
        pumpEmission_day_kg_CO2__isnull=False,
    )
    return wells.aggregate(total=Sum('pumpEmission_day_kg_CO2'))['total'] or 0


# ── Water Quality & Treatment ────────────────────────────────────────

def calculate_water_quality(year):
    """Water quality metrics from treatment plant samples.

    DAG edges:  WT_Efficiency  → Samples_WQ
                Samples_Taken  → Samples_WQ
                Samples_WQ     → User_Acceptance_WS
    Returns dict with samples_taken, samples_ok, compliance_pct,
    treatment_efficiency, acceptance_rate.
    """
    wt = WaterTreatment.objects.filter(year=year)
    if not wt.exists():
        return {
            'samples_taken': 0,
            'samples_ok': 0,
            'compliance_pct': None,
            'treatment_efficiency': None,
            'acceptance_rate': None,
        }

    agg = wt.aggregate(
        samples_taken=Sum('samplesWaterQualityTaken'),
        samples_ok=Sum('samplesWaterQuality_OK'),
        avg_efficiency=Avg('treatment_efficiency'),
        avg_acceptance=Avg('acceptanceRate'),
    )

    taken = agg['samples_taken'] or 0
    ok = agg['samples_ok'] or 0

    return {
        'samples_taken': taken,
        'samples_ok': ok,
        'compliance_pct': round(ok / taken * 100, 1) if taken else None,
        'treatment_efficiency': round(agg['avg_efficiency'], 1) if agg['avg_efficiency'] else None,
        'acceptance_rate': round(agg['avg_acceptance'], 1) if agg['avg_acceptance'] else None,
    }


# ── Collection & Revenue Recovery ────────────────────────────────────

def calculate_collection_ratio(province):
    """Collection ratio: collected meters / installed meters.

    DAG edges:  Metered_Res_Water      → CollectionRatio
                User_Acceptance_WS     → CollectionRatio
                Water_Tariff_Afford    → CollectionRatio
    """
    neighborhoods = Neighborhood.objects.filter(
        district__city__province=province,
    )
    user_locs = UsersLocation.objects.filter(neighborhood__in=neighborhoods)
    meters = MeteredResidential.objects.filter(userLocation__in=user_locs)

    agg = meters.aggregate(
        installed=Sum('installed_meters'),
        collected=Sum('collected_meters'),
    )
    installed = agg['installed'] or 0
    collected = agg['collected'] or 0

    return round(collected / installed * 100, 1) if installed else None


def calculate_opex_recovery(year, province):
    """OPEX recovery percentage.

    DAG edges:  OPEX             → OPEX_Recovery
                CollectionRatio  → OPEX_Recovery
                NRW              → OPEX_Recovery
    """
    neighborhoods = Neighborhood.objects.filter(
        district__city__province=province,
    )
    user_locs = UsersLocation.objects.filter(neighborhood__in=neighborhoods)
    revenue = (
        MeteredResidential.objects
        .filter(userLocation__in=user_locs, Recovery_EUR__isnull=False)
        .aggregate(total=Sum('Recovery_EUR'))['total'] or 0
    )

    # Get total OPEX for the year
    opex_record = OPEX.objects.filter(year=year).first()
    total_opex = opex_record.totalOPEX_EUR if opex_record else None

    if total_opex and total_opex > 0:
        return {
            'revenue_EUR': round(revenue, 2),
            'total_opex_EUR': round(total_opex, 2),
            'recovery_pct': round(revenue / total_opex * 100, 1),
        }
    return {
        'revenue_EUR': round(revenue, 2),
        'total_opex_EUR': None,
        'recovery_pct': None,
    }


# ── Coverage ─────────────────────────────────────────────────────────

def calculate_coverage(province):
    """Water supply coverage aggregated across cities.

    DAG edges:  Network   → Coverage_WS_Area
                CityArea  → Coverage_WS_Area
                NumberUsers → Coverage_WS
    """
    cities = City.objects.filter(province=province)
    coverage_records = CoverageWaterSupply.objects.filter(city__in=cities)

    if not coverage_records.exists():
        return {
            'covered_area_km2': 0,
            'households_covered': 0,
            'households_total': 0,
            'coverage_pct': None,
        }

    agg = coverage_records.aggregate(
        area=Sum('coveredArea_km2'),
        covered=Sum('households_covered'),
        total=Sum('households_total'),
    )
    total = agg['total'] or 0
    covered = agg['covered'] or 0

    return {
        'covered_area_km2': round(agg['area'] or 0, 2),
        'households_covered': covered,
        'households_total': total,
        'coverage_pct': round(covered / total * 100, 1) if total else None,
    }


# ── Non-Revenue Water ────────────────────────────────────────────────

def calculate_nrw(year):
    """Non-Revenue Water breakdown.

    DAG edges:  Real_Losses     → NRW, ILI
                Apparent_Losses → NRW, ILI
    """
    nrw_qs = NonRevenueWater.objects.filter(year=year)

    apparent = (
        nrw_qs.filter(type='A')
        .aggregate(total=Sum('loss_Quantity_m3'))['total'] or 0
    )
    real = (
        nrw_qs.filter(type='R')
        .aggregate(total=Sum('loss_Quantity_m3'))['total'] or 0
    )

    latest_ili = (
        nrw_qs.filter(type='R', ILI__isnull=False)
        .order_by('-last_updated')
        .first()
    )

    return {
        'apparent_losses_m3_d': apparent,
        'real_losses_m3_d': real,
        'total_nrw_m3_d': apparent + real,
        'ili': latest_ili.ILI if latest_ili else None,
    }


# ── Available Fresh Water ────────────────────────────────────────────

def calculate_available_freshwater(province):
    """Total available fresh water within the province.

    DAG edges:  Infiltration → Available_FW
                Meteorology  → Available_FW
    """
    return (
        AvailableFreshWater.objects
        .filter(geom__intersects=province.geom)
        .aggregate(total=Sum('totalQuantity_Mm3'))['total'] or 0
    )


# ── Drought ──────────────────────────────────────────────────────────

def calculate_drought_area(province, year):
    """Area affected by drought.

    DAG edge:  Total_Extraction → Area_Drought
    """
    from .models import AreaAffectedDrought

    records = AreaAffectedDrought.objects.filter(
        Province=province, year=year,
    )
    if not records.exists():
        return {'total_area_km2': 0, 'max_sensibility': 0}

    agg = records.aggregate(
        area=Sum('areaAffected_km2'),
        max_level=gis_models.Max('SensibilityLevel'),
    )
    return {
        'total_area_km2': round(agg['area'] or 0, 2),
        'max_sensibility': agg['max_level'] or 0,
    }
