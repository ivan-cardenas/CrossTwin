from django.db.models import Sum, Avg, F, FloatField, ExpressionWrapper, Count, Q

from .models import (
    HousingSupplyDemand, HousingProject, CentralBankPolicy,
    CreditSupplyConditions, Mortgage, Rentals, HousePriceIndex,
    HousingAffordability,
)
from common.models import City, Neighborhood
from builtup.models import Property, ZoningArea, Building


# -- Supply & Demand ---------------------------------------------------------

def calculate_supply_demand(city, year):
    """Housing supply vs demand for a city and year.

    DAG edges:  Urbanization     -> Housing_Demand
                New_Units        -> Housing_Supply
                Housing_Demand   -> House_Price_Index
    """
    record = HousingSupplyDemand.objects.filter(city=city, year=year).first()
    if not record:
        return {
            'supply_units': 0,
            'demand_units': 0,
            'deficit': 0,
            'deficit_pct': None,
        }

    deficit = record.demand_units - record.supply_units
    deficit_pct = (
        round(deficit / record.demand_units * 100, 1)
        if record.demand_units else None
    )
    return {
        'supply_units': record.supply_units,
        'demand_units': record.demand_units,
        'deficit': deficit,
        'deficit_pct': deficit_pct,
    }


def calculate_supply_demand_province(province, year):
    """Aggregate supply/demand across all cities in a province."""
    cities = City.objects.filter(province=province)
    records = HousingSupplyDemand.objects.filter(city__in=cities, year=year)

    agg = records.aggregate(
        supply=Sum('supply_units'),
        demand=Sum('demand_units'),
    )
    supply = agg['supply'] or 0
    demand = agg['demand'] or 0
    deficit = demand - supply

    return {
        'supply_units': supply,
        'demand_units': demand,
        'deficit': deficit,
        'deficit_pct': round(deficit / demand * 100, 1) if demand else None,
    }


# -- New Units (pipeline) ----------------------------------------------------

def calculate_new_units(city, year):
    """New housing units in the pipeline.

    DAG edges:  Zoning_Status -> New_Units
                Network       -> New_Units
                New_Units     -> Housing_Supply
                New_Units     -> LandCover
    """
    projects = HousingProject.objects.filter(
        neighborhood__district__city=city,
    )

    completed = projects.filter(year_expected_completion__lte=year)
    pipeline = projects.filter(year_expected_completion__gt=year)

    completed_agg = completed.aggregate(
        units=Sum('project_units'),
        count=Count('id'),
    )
    pipeline_agg = pipeline.aggregate(
        units=Sum('project_units'),
        count=Count('id'),
    )

    return {
        'completed_units': completed_agg['units'] or 0,
        'completed_projects': completed_agg['count'] or 0,
        'pipeline_units': pipeline_agg['units'] or 0,
        'pipeline_projects': pipeline_agg['count'] or 0,
    }


def calculate_new_units_province(province, year):
    """Aggregate new units across all cities in a province."""
    cities = City.objects.filter(province=province)
    neighborhoods = Neighborhood.objects.filter(district__city__in=cities)
    projects = HousingProject.objects.filter(neighborhood__in=neighborhoods)

    completed = projects.filter(year_expected_completion__lte=year)
    pipeline = projects.filter(year_expected_completion__gt=year)

    completed_agg = completed.aggregate(
        units=Sum('project_units'), count=Count('id'),
    )
    pipeline_agg = pipeline.aggregate(
        units=Sum('project_units'), count=Count('id'),
    )

    return {
        'completed_units': completed_agg['units'] or 0,
        'completed_projects': completed_agg['count'] or 0,
        'pipeline_units': pipeline_agg['units'] or 0,
        'pipeline_projects': pipeline_agg['count'] or 0,
    }


# -- Mortgage -----------------------------------------------------------------

def calculate_mortgage_indicators(province, year):
    """Mortgage indicators from central bank policy and credit conditions.

    DAG edges:  Central_Bank  -> Mortgage
                Credit_Supply -> Mortgage
                Mortgage      -> Affordability_Stress
                Mortgage      -> Income_Expenses
    """
    policy = CentralBankPolicy.objects.filter(
        province=province, year=year,
    ).first()

    credit = CreditSupplyConditions.objects.filter(
        province=province, year=year,
    ).first()

    # Aggregate actual mortgage data
    cities = City.objects.filter(province=province)
    neighborhoods = Neighborhood.objects.filter(district__city__in=cities)
    buildings = Building.objects.filter(neighborhood__in=neighborhoods)
    properties = Property.objects.filter(building__in=buildings)
    mortgages = Mortgage.objects.filter(property__in=properties)

    agg = mortgages.aggregate(
        avg_monthly=Avg('monthlyPayment'),
        avg_interest=Avg('interestRate'),
        avg_loan=Avg('totalLoanAmount'),
        total_count=Count('id'),
    )

    return {
        'interest_rate': policy.interest_rate if policy else None,
        'ltv_limit': policy.LTV_limit if policy else None,
        'lti_limit': policy.LTI_limit if policy else None,
        'mortgage_rate': credit.mortgageRate if credit else None,
        'approval_rate': credit.mortgage_approval_rate if credit else None,
        'avg_down_payment_pct': credit.average_down_payment if credit else None,
        'avg_monthly_payment': round(agg['avg_monthly'], 2) if agg['avg_monthly'] else None,
        'avg_interest_rate': round(agg['avg_interest'], 2) if agg['avg_interest'] else None,
        'avg_loan_amount': round(agg['avg_loan'], 2) if agg['avg_loan'] else None,
        'total_mortgages': agg['total_count'] or 0,
    }


# -- Rent ---------------------------------------------------------------------

def calculate_rent_indicators(province):
    """Rental market indicators.

    DAG edges:  Property -> Rent
                Rent     -> Income_Expenses
    """
    cities = City.objects.filter(province=province)
    neighborhoods = Neighborhood.objects.filter(district__city__in=cities)
    buildings = Building.objects.filter(neighborhood__in=neighborhoods)
    properties = Property.objects.filter(building__in=buildings)
    rentals = Rentals.objects.filter(property__in=properties)

    agg = rentals.aggregate(
        avg_monthly=Avg('monthlyRent'),
        avg_annual=Avg('annualRent'),
        avg_price_to_rent=Avg('priceToRentRatio'),
        total_count=Count('id'),
    )

    return {
        'avg_monthly_rent': round(agg['avg_monthly'], 2) if agg['avg_monthly'] else None,
        'avg_annual_rent': round(agg['avg_annual'], 2) if agg['avg_annual'] else None,
        'avg_price_to_rent_ratio': round(agg['avg_price_to_rent'], 1) if agg['avg_price_to_rent'] else None,
        'total_rentals': agg['total_count'] or 0,
    }


# -- House Price Index --------------------------------------------------------

def calculate_house_price_index(province, year):
    """House price index aggregated across neighborhoods.

    DAG edges:  Housing_Demand -> House_Price_Index
                Property       -> House_Price_Index
    """
    cities = City.objects.filter(province=province)
    neighborhoods = Neighborhood.objects.filter(district__city__in=cities)
    records = HousePriceIndex.objects.filter(
        neighborhood__in=neighborhoods, year=year,
    )

    agg = records.aggregate(
        avg_index=Avg('index_value'),
        count=Count('id'),
    )

    # Year-over-year change
    prev_records = HousePriceIndex.objects.filter(
        neighborhood__in=neighborhoods, year=year - 1,
    )
    prev_avg = prev_records.aggregate(avg=Avg('index_value'))['avg']
    current_avg = agg['avg_index']

    yoy_change = None
    if current_avg and prev_avg and prev_avg > 0:
        yoy_change = round((current_avg - prev_avg) / prev_avg * 100, 1)

    return {
        'avg_index': round(current_avg, 1) if current_avg else None,
        'yoy_change_pct': yoy_change,
        'neighborhoods_reported': agg['count'] or 0,
    }


# -- Property Market ----------------------------------------------------------

def calculate_property_indicators(province):
    """Property market indicators.

    DAG edges:  Housing_Supply -> Property
                Zoning_Status  -> Property
                Accessibility  -> Property
                Property       -> Affordability_Stress
                Property       -> Rent
                Property       -> House_Price_Index
                Property       -> Mortgage
    """
    cities = City.objects.filter(province=province)
    neighborhoods = Neighborhood.objects.filter(district__city__in=cities)
    buildings = Building.objects.filter(neighborhood__in=neighborhoods)
    properties = Property.objects.filter(building__in=buildings)

    agg = properties.aggregate(
        avg_price=Avg('salePrice_EUR'),
        avg_listing=Avg('listingPrice_EUR'),
        avg_price_sqm=Avg('unitaryPrice_EUR_per_sqm'),
        avg_area=Avg('livingArea'),
        total_count=Count('id'),
    )

    # Vacancy from buildings
    vacancy = buildings.aggregate(
        total_units=Sum('numberUnits'),
        vacant_buildings=Count('id', filter=Q(vacant=True)),
        total_buildings=Count('id'),
    )

    avg_vacancy_rate = buildings.filter(
        vacancyRate__isnull=False,
    ).aggregate(avg=Avg('vacancyRate'))['avg']

    return {
        'avg_sale_price': round(agg['avg_price'], 2) if agg['avg_price'] else None,
        'avg_listing_price': round(agg['avg_listing'], 2) if agg['avg_listing'] else None,
        'avg_price_sqm': round(agg['avg_price_sqm'], 2) if agg['avg_price_sqm'] else None,
        'avg_living_area': round(agg['avg_area'], 1) if agg['avg_area'] else None,
        'total_properties': agg['total_count'] or 0,
        'total_units': vacancy['total_units'] or 0,
        'vacant_buildings': vacancy['vacant_buildings'] or 0,
        'total_buildings': vacancy['total_buildings'] or 0,
        'avg_vacancy_rate': round(avg_vacancy_rate, 1) if avg_vacancy_rate else None,
    }


# -- Zoning -------------------------------------------------------------------

def calculate_zoning(province):
    """Zoning area breakdown.

    DAG edges:  Housing_Demand -> Zoning_Status
                Zoning_Status  -> Property
                Zoning_Status  -> New_Units
    """
    cities = City.objects.filter(province=province)
    neighborhoods = Neighborhood.objects.filter(district__city__in=cities)
    zones = ZoningArea.objects.filter(neighborhood__in=neighborhoods)

    total_area = zones.aggregate(total=Sum('area'))['total'] or 0

    by_type = {}
    for zone_type in ['residential', 'commercial', 'industrial', 'mixed']:
        type_agg = zones.filter(zone_type=zone_type).aggregate(
            area=Sum('area'),
            count=Count('id'),
            avg_benchmark=Avg('benchmarkPrice_per_sqm'),
        )
        by_type[zone_type] = {
            'area_sqm': type_agg['area'] or 0,
            'count': type_agg['count'] or 0,
            'area_pct': round((type_agg['area'] or 0) / total_area * 100, 1) if total_area else 0,
            'avg_benchmark_EUR_sqm': round(type_agg['avg_benchmark'], 2) if type_agg['avg_benchmark'] else None,
        }

    return {
        'total_area_sqm': total_area,
        'by_type': by_type,
    }


# -- Affordability ------------------------------------------------------------

def calculate_affordability(province, year):
    """Housing affordability indicators.

    DAG edges:  Property            -> Affordability_Stress
                Income_Expenses     -> Affordability_Stress
                Mortgage            -> Affordability_Stress
                Water_Tariff_Afford -> Income_Expenses
                Rent                -> Income_Expenses
                Mortgage            -> Income_Expenses
    """
    cities = City.objects.filter(province=province)
    neighborhoods = Neighborhood.objects.filter(district__city__in=cities)
    records = HousingAffordability.objects.filter(
        neighborhood__in=neighborhoods, year=year,
    )

    if not records.exists():
        return {
            'avg_affordability_index': None,
            'avg_median_income': None,
            'avg_median_expenditure': None,
            'avg_median_disposable': None,
            'avg_median_house_price': None,
            'avg_median_rent': None,
            'avg_median_mortgage': None,
            'stress_distribution': {},
            'neighborhoods_reported': 0,
        }

    agg = records.aggregate(
        avg_index=Avg('affordabilityIndex'),
        avg_income=Avg('medianIncome'),
        avg_expenditure=Avg('medianExpenditure'),
        avg_disposable=Avg('medianDisposableIncome'),
        avg_house_price=Avg('medianHousePrice'),
        avg_rent=Avg('medianRent'),
        avg_mortgage=Avg('medianMortgage'),
        count=Count('id'),
    )

    # Stress level distribution
    stress_dist = {}
    for level_key, level_label in [('low', 'Low'), ('moderate', 'Moderate'), ('high', 'High')]:
        stress_dist[level_key] = records.filter(
            affordabilityStressLevel=level_key,
        ).count()

    return {
        'avg_affordability_index': round(agg['avg_index'], 2) if agg['avg_index'] else None,
        'avg_median_income': round(agg['avg_income'], 2) if agg['avg_income'] else None,
        'avg_median_expenditure': round(agg['avg_expenditure'], 2) if agg['avg_expenditure'] else None,
        'avg_median_disposable': round(agg['avg_disposable'], 2) if agg['avg_disposable'] else None,
        'avg_median_house_price': round(agg['avg_house_price'], 2) if agg['avg_house_price'] else None,
        'avg_median_rent': round(agg['avg_rent'], 2) if agg['avg_rent'] else None,
        'avg_median_mortgage': round(agg['avg_mortgage'], 2) if agg['avg_mortgage'] else None,
        'stress_distribution': stress_dist,
        'neighborhoods_reported': agg['count'] or 0,
    }
