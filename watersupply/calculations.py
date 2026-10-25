from django.db.models import (
    Sum, Avg, F, FloatField, IntegerField, ExpressionWrapper, OuterRef, Subquery,
)
from django.db.models.functions import Coalesce
from django.contrib.gis.db import models as gis_models
from django.contrib.gis.db.models.functions import Intersection, Length, PointOnSurface

from .models import (
    ConsumptionCapita, TotalWaterDemand, ExtractionWater, ImportedWater,
    AvailableFreshWater, PipeNetwork, CoverageWaterSupply, NonRevenueWater,
    WaterTreatment, MeteredResidential, UsersLocation, OPEX,
    TotalWaterProduction, Watershed,
)
from administrative.models import City, Province, Neighborhood
from administrative.admin_units import cities_within, neighborhoods_within


# ── Consumption & Demand ─────────────────────────────────────────────

def _get_consumption_record_years(adminBund, year):
    """Per city of the unit, the ConsumptionCapita record used for `year` (ConsumptionCapita.for_year)."""
    records = (ConsumptionCapita.for_year(city, year) for city in cities_within(adminBund))
    return [r for r in records if r is not None]


def _get_consumption_capita(adminBund, year):
    """Per-capita consumption (L/person/day) for an admin unit and year.

    Mean over the unit's cities of each city's record for `year`, or of its
    latest earlier year when there is none (ConsumptionCapita.for_year), so an
    old survey is the default until newer data exists.
    """
    records = _get_consumption_record_years(adminBund, year)
    if not records:
        return 0
    return sum(r.consumption_capita_L_d for r in records) / len(records)


def consumption_data_years(adminBund, year):
    """The years the consumption of `year` actually comes from (sorted, may be empty)."""
    return sorted({r.year for r in _get_consumption_record_years(adminBund, year)})


def calculate_total_demand(adminBund, year):
    """Total water demand in m³/day across all cities in an admin unit."""
    cities = cities_within(adminBund)
    consumption = _get_consumption_capita(adminBund, year)
    population = adminBund.currentPopulation or 0
    # L/person/day → m³/day
    return consumption / 1000 * population


# ── Extraction & Production ──────────────────────────────────────────

def active_wells_with_watershed():
    """Active wells annotated with `ws`, the id of the watershed their water belongs to.

    The watershed of the well's AvailableFreshWater source when set, otherwise
    the watershed containing the well; None when neither exists.
    """
    containing = Watershed.objects.filter(geom__contains=OuterRef('geom')).values('pk')[:1]
    return ExtractionWater.objects.filter(is_active=True).annotate(
        ws=Coalesce('source__watershed', Subquery(containing), output_field=IntegerField()),
    )


def _watershed_neighborhoods(watershed):
    """Neighborhoods served by a watershed: those whose point on surface lies in it.

    One point per neighborhood, so a neighborhood crossing a watershed border
    counts in exactly one watershed and the shares of a watershed sum to 1.
    """
    return (
        Neighborhood.objects
        .annotate(pos=PointOnSurface('geom'))
        .filter(pos__within=watershed.geom)
    )


def watershed_share(adminBund, watershed):
    """Share (0-1) of a watershed's water that goes to the population of adminBund.

    share = population of the unit's neighborhoods in the watershed
            / population of all neighborhoods in the watershed
    Falls back to the unit's share of the watershed area when no neighborhood
    population is stored there (e.g. only cities were imported).
    """
    served = _watershed_neighborhoods(watershed)
    total_pop = served.aggregate(p=Sum('currentPopulation'))['p'] or 0
    if total_pop > 0:
        unit_pop = (
            served.filter(pk__in=neighborhoods_within(adminBund).values('pk'))
            .aggregate(p=Sum('currentPopulation'))['p'] or 0
        )
        return unit_pop / total_pop
    if not watershed.geom.area:
        return 0.0
    return adminBund.geom.intersection(watershed.geom).area / watershed.geom.area


def calculate_total_extraction(adminBund):
    """Active extraction in m³/day available to the population of adminBund.

    Wells may lie outside the unit: the water they pump belongs to their
    watershed (the watershed of the well's AvailableFreshWater source, or the
    watershed containing the well) and is distributed over the population of
    that watershed. Per watershed:
        E_u = Σ_w V_w × share(u, watershed)
    with V_w the well's volume in m³/day (ExtractionWater.volume_m3_d: measured
    yearly extraction, else pump flow x operation time, else flow x 24 h).
    Wells with no watershed keep the location rule (counted in full for the
    units they lie in).

    DAG edges:  Available_FW → Total_Extraction
    """
    wells = active_wells_with_watershed()
    volume = ExtractionWater.volume_m3_d()
    flows = wells.values('ws').annotate(m3_d=Sum(volume))
    m3_d_by_ws = {row['ws']: row['m3_d'] or 0 for row in flows}

    total_m3_d = 0.0
    if None in m3_d_by_ws:
        total_m3_d += (
            wells.filter(ws__isnull=True, geom__intersects=adminBund.geom)
            .aggregate(total=Sum(volume))['total'] or 0
        )
    for watershed in Watershed.objects.filter(pk__in=[ws for ws in m3_d_by_ws if ws is not None]):
        total_m3_d += m3_d_by_ws[watershed.pk] * watershed_share(adminBund, watershed)
    return total_m3_d


def calculate_total_production_day(adminBund=None):
    """Total water production in m³/day (extraction + imported).

    DAG edges:  Total_Extraction → Total_Water_Prod
                Imported_Water   → Total_Water_Prod
    """
    if adminBund:
        extraction_m3_d = calculate_total_extraction(adminBund)
    else:
        extraction_m3_d = (
            ExtractionWater.objects.filter(is_active=True)
            .aggregate(total=Sum(ExtractionWater.volume_m3_d()))['total'] or 0
        )

    imported_m3_d = (
        ImportedWater.objects.filter(is_active=True)
        .aggregate(total=Sum('quantity_m3_d'))['total'] or 0
    )
    return extraction_m3_d + imported_m3_d


def calculate_supply_security(adminBund, year=None):
    """Supply security: demand vs production.

    DAG edges:  Total_Water_Demand → Supply_Security
                Total_Water_Prod   → Supply_Security
    TotalWaterDemand.demandDay is stored in Mm³/day; it is converted to m³/day
    here. Pass `year` to use that year's demand only (otherwise every year's
    record would be summed together).
    Returns (demand_m3_d, production_m3_d, security_ratio).
    """
    cities = cities_within(adminBund)
    demand_qs = TotalWaterDemand.objects.filter(city__in=cities)
    if year is not None:
        demand_qs = demand_qs.filter(year=year)
    demand = (demand_qs.aggregate(total=Sum('demandDay'))['total'] or 0) * 1e6
    production = calculate_total_production_day(adminBund)

    if demand and production:
        supply_security = production / demand
    else:
        supply_security = None

    return demand, production, supply_security


# ── Energy & Emissions ───────────────────────────────────────────────

def calculate_energy_consumption(adminBund):
    """Total energy consumption from pumping in kWh/day.

    DAG edges:  Total_Extraction   → Energy_Consumption
                Total_Water_Prod   → Energy_Consumption
                Energy_Cost        → Energy_Consumption
    """
    wells = ExtractionWater.objects.filter(
        is_active=True,
        geom__intersects=adminBund.geom,
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


def calculate_co2_emission(adminBund):
    """Total CO₂ emissions from extraction pumps in kg CO₂/day.

    DAG edge:  Total_Extraction → CO2_Emission
    """
    wells = ExtractionWater.objects.filter(
        is_active=True,
        geom__intersects=adminBund.geom,
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

def calculate_collection_ratio(adminBund):
    """Collection ratio: collected meters / installed meters.

    DAG edges:  Metered_Res_Water      → CollectionRatio
                User_Acceptance_WS     → CollectionRatio
                Water_Tariff_Afford    → CollectionRatio
    """
    neighborhoods = neighborhoods_within(adminBund)
    user_locs = UsersLocation.objects.filter(neighborhood__in=neighborhoods)
    meters = MeteredResidential.objects.filter(userLocation__in=user_locs)

    agg = meters.aggregate(
        installed=Sum('installed_meters'),
        collected=Sum('collected_meters'),
    )
    installed = agg['installed'] or 0
    collected = agg['collected'] or 0

    return round(collected / installed * 100, 1) if installed else None


def calculate_opex_recovery(year, adminBund):
    """OPEX recovery percentage.

    DAG edges:  OPEX             → OPEX_Recovery
                CollectionRatio  → OPEX_Recovery
                NRW              → OPEX_Recovery
    """
    neighborhoods = neighborhoods_within(adminBund)
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

def calculate_coverage(adminBund):
    """Water supply coverage aggregated across cities.

    DAG edges:  Network   → Coverage_WS_Area
                CityArea  → Coverage_WS_Area
                NumberUsers → Coverage_WS
    """
    cities = cities_within(adminBund)
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

def calculate_nrw(year, adminBund=None):
    """Non-Revenue Water breakdown, network-wide or for one admin unit.

    DAG edges:  Network         → Real_Losses (each real loss sits on a PipeNetwork)
                Real_Losses     → NRW, ILI
                Apparent_Losses → NRW, ILI

    With ``adminBund``:
    - a real loss counts in proportion to the share of its pipe's length inside
      the unit (pipes run from a well to a users location, so one pipe can
      cross many units; the shares of a leak over all units add up to the
      whole leak). Real losses without a pipe cannot be placed and only
      appear network-wide;
    - apparent losses (meter error, theft, data errors) have no location, so the
      unit gets its share of them by water users (``UsersLocation.usersTotal``);
      ``apparent_share`` is None when no user counts are stored.
    ILI = CARL / UARL over the real losses counted, so it is the unit's own ILI.

    ``real_losses_by_pipe`` lists, per pipe, the presumed leakage counted
    here (``loss_m3_d``, after the length share), that share, and the
    leakage per km of the whole pipe (m³/km/day), worst first.
    """
    nrw_qs = NonRevenueWater.objects.filter(year=year)

    apparent = (
        nrw_qs.filter(type='A')
        .aggregate(total=Sum('loss_Quantity_m3'))['total'] or 0
    )
    apparent_share = 1.0
    if adminBund is not None:
        all_users = UsersLocation.objects.aggregate(total=Sum('usersTotal'))['total'] or 0
        unit_users = (
            UsersLocation.objects
            .filter(neighborhood__in=neighborhoods_within(adminBund))
            .aggregate(total=Sum('usersTotal'))['total'] or 0
        )
        apparent_share = unit_users / all_users if all_users else None
        apparent *= apparent_share or 0

    # CARL and UARL per pipe (pipe_id None = legacy rows without a pipe)
    per_pipe = (
        nrw_qs.filter(type='R')
        .values('pipe_id', 'pipe__length_km')
        .annotate(
            carl=Sum('loss_Quantity_m3'),
            uarl=Sum(ExpressionWrapper(
                F('loss_Quantity_m3') * F('UnavoidableLossses_PCT') / 100, output_field=FloatField())),
        )
    )
    if adminBund is None:
        shares = None
    else:
        shares = {
            p.pk: p.inside.m / p.full.m if p.full.m else 0
            for p in (
                PipeNetwork.objects
                .filter(pk__in=[r['pipe_id'] for r in per_pipe if r['pipe_id']],
                        geom__intersects=adminBund.geom)
                .annotate(inside=Length(Intersection('geom', adminBund.geom)), full=Length('geom'))
            )
        }

    real = uarl = 0
    by_pipe = []
    for row in per_pipe:
        share = 1.0 if shares is None else shares.get(row['pipe_id'], 0)
        if not share:
            continue
        real += row['carl'] * share
        uarl += row['uarl'] * share
        if row['pipe_id']:
            length_km = row['pipe__length_km']
            by_pipe.append({
                'pipe_id': row['pipe_id'],
                'share': share,
                'loss_m3_d': row['carl'] * share,
                'loss_m3_km_d': row['carl'] / length_km if length_km else None,
            })
    by_pipe.sort(key=lambda r: r['loss_m3_d'], reverse=True)

    return {
        'apparent_losses_m3_d': apparent,
        'apparent_share': apparent_share,
        'real_losses_m3_d': real,
        'total_nrw_m3_d': apparent + real,
        'ili': round(real / uarl, 2) if uarl else None,
        'real_losses_by_pipe': by_pipe,
    }


# ── Available Fresh Water ────────────────────────────────────────────

def calculate_available_freshwater(adminBund):
    """Total available fresh water within the adminBund.

    DAG edges:  Infiltration → Available_FW
                Meteorology  → Available_FW
    """
    return (
        AvailableFreshWater.objects
        .filter(geom__intersects=adminBund.geom)
        .aggregate(total=Sum('totalQuantity_Mm3'))['total'] or 0
    )


# ── Infiltration (SCS Curve Number) ──────────────────────────────────

def calculate_infiltration(adminBund, season='wet'):
    """Soil group x land cover composition of the adminBund, for the SCS method.

    The rain depth is a dashboard what-if, so this returns only the areas;
    physicalEnv.soil.summarize_infiltration turns them into curve number,
    infiltration coefficient and volumes for a given rain depth.

    `season` ('wet' or 'dry') picks the groundwater level (GHG or GLG):
    where it is under 60 cm on undrained land the soil counts as group D;
    drained (built-up, paved) land keeps its texture group.

    DAG edges:  LandCover  → Infiltration
                Soil_Type  → Infiltration
    """
    from physicalEnv.soil import SEASONS, soil_landcover_composition

    composition, by_group, shallow_m2, drained_m2 = soil_landcover_composition(
        adminBund.geom, SEASONS[season]['statistic'])
    return {
        'composition': composition,
        'soil_groups_m2': by_group,
        'shallow_groundwater_m2': shallow_m2,
        'drained_shallow_m2': drained_m2,
    }


# ── Drought ──────────────────────────────────────────────────────────

def calculate_drought_area(adminBund, year):
    """Area affected by drought.

    DAG edge:  Total_Extraction → Area_Drought
    """
    from .models import AreaAffectedDrought

    records = AreaAffectedDrought.objects.filter(
        geom__intersects=adminBund.geom, year=year,
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
