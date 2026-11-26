"""
The population -> household size -> housing demand / residents chain of the
housing module, written once and used by both paths:

* the stored path: HouseholdSize / HousingSupplyDemand save() and
  housing/signals.py (Property.residents) with the *baseline* population of the
  record's year (CBS median forecast, no extra growth);
* the dashboard path: views._build_indicators with the request's what-ifs
  (population dock + the "persons per home" slider), never written.

Everything here is pure; the dashboard with default controls equals the stored
values because both call these functions.

    average_size  = population / households          (CBS, per city and year)
    demand_units  = population / average_size         (homes needed)
    residents     = average_size                      (per occupied dwelling)

DAG edges: Total_Population, Household_Size -> Housing_Demand
           Household_Size -> Property
"""

from builtup.calculations.regulations import MIN_VERBLIJFSGEBIED_M2

# Slider range of the dashboard's "persons per home" control; also the plausible
# range stored values are checked against (NL average is ~2.1, 1-person-heavy
# student cities fall below 1.8).
SIZE_MIN = 1.0
SIZE_MAX = 4.0

# Range of the "residents living alone" slider, % of the residents. Neighborhood
# values (CBS one-person households x households / inhabitants) reach about 60 %
# in student and city-centre areas.
ALONE_MIN = 0.0
ALONE_MAX = 70.0

# A dwelling counts as a usable home from this floor area (m2). The Bbl needs at
# least 18 m2 verblijfsgebied per dwelling (IPLO infoblad, core/data_sources.py
# "Bbl"); the BAG usable area (oppervlakte) is at least the verblijfsgebied, so a
# unit below 18 m2 certainly is not a home. Rooms, studios in care or student
# complexes and similar fall out; a unit above it is kept even if it is not
# (a lower bound on what is excluded).
MIN_DWELLING_AREA_SQM = MIN_VERBLIJFSGEBIED_M2

# ── Affordability stress ─────────────────────────────────────────────
#
#   cost    = tenure-weighted monthly housing cost (rent / mortgage)
#   burden  = 12 x cost / annual median income
#   adjusted = burden x (1 + SES_WEIGHT x clamp(-SES, -SES_CLAMP, SES_CLAMP))
#   level   = low (< 30 %), moderate (30-40 %), high (>= 40 %) of `adjusted`
#
# A neighborhood with a below-average socio-economic status (negative CBS score)
# has less reserve to absorb the same housing cost, so its burden counts for more.

# Housing-cost burden bands, share of income. 40 % is the Eurostat "housing cost
# overburden" threshold (EU-SILC, share of disposable income); 30 % is the common
# affordability rule of thumb (Nibud / OECD). Both are applied to gross median
# income, which understates the burden against Eurostat's disposable income.
BURDEN_MODERATE = 0.30
BURDEN_HIGH = 0.40

# SES modifier: +/- 10 % of the burden per standard deviation of the CBS status
# score, clamped at +/- 2 SD. A modelling assumption (no published coefficient):
# a calibration parameter to test in a sensitivity run, not a measured value.
SES_WEIGHT = 0.10
SES_CLAMP = 2.0

STRESS_METHOD = "cost-burden 30/40 % x SES 10 %/SD (v1)"   # stored with every derived row


def monthly_housing_cost(rent, mortgage, rental_share_pct=None):
    """
    Monthly housing cost of a neighborhood in EUR; None without a usable input.

    Both rent and mortgage given: weighted by the share of rental dwellings
    (`rental_share_pct`, 0-100), the plain mean when that share is unknown. Only
    one given: that one. Values <= 0 count as missing.
    """
    rent = rent if rent and rent > 0 else None
    mortgage = mortgage if mortgage and mortgage > 0 else None
    if rent is None or mortgage is None:
        return rent if mortgage is None else mortgage
    share = 0.5 if rental_share_pct is None else min(max(rental_share_pct, 0.0), 100.0) / 100.0
    return share * rent + (1.0 - share) * mortgage


def housing_cost_burden(monthly_cost, annual_income):
    """Share of the annual income spent on housing (None without both inputs)."""
    if not monthly_cost or not annual_income or annual_income <= 0:
        return None
    return 12.0 * monthly_cost / annual_income


def ses_modifier(socio_economic_status):
    """
    Factor on the cost burden for the neighborhood's CBS socio-economic status
    score (standardised, negative = below average). 1.0 without a score.

    DAG edge: Social_Profile -> Affordability_Stress
    """
    if socio_economic_status is None:
        return 1.0
    return 1.0 + SES_WEIGHT * max(-SES_CLAMP, min(SES_CLAMP, -socio_economic_status))


def affordability_stress_level(burden, socio_economic_status=None):
    """
    'low' | 'moderate' | 'high' for a housing-cost burden, after the SES modifier;
    None without a burden (the caller keeps the stored level).

    DAG edges: Income_Expenses -> Affordability_Stress
               Social_Profile  -> Affordability_Stress
    """
    if burden is None:
        return None
    adjusted = burden * ses_modifier(socio_economic_status)
    if adjusted >= BURDEN_HIGH:
        return "high"
    if adjusted >= BURDEN_MODERATE:
        return "moderate"
    return "low"


def baseline_population(city, year):
    """
    (population, partial) the stored housing chain uses for `city` in `year`.

    City.currentPopulation is the sum of the neighborhoods imported locally,
    often far below the real city, while the household stock is whole-gemeente
    CBS, so the local sum must not be divided by a CBS household size. In order:
      1. the population stored with that year's HouseholdSize (the forecast
         median of that year, or a manually entered value);
      2. the CBS median forecast (watersupply.calculations.chain.baseline_population), when
         the city has projections;
      3. the current population, with partial=True: it only covers what is
         imported, so a demand built on it understates the city.
    The population is None when the city has none of them.

    DAG edge: Population_Growth -> Total_Population
    """
    from administrative.models import PopulationProjection
    from administrative.calculations.population import DEFAULT_SCENARIO
    from watersupply.calculations.chain import baseline_population as projected_population

    from ..models import HouseholdSize

    record = HouseholdSize.objects.filter(city=city, year=year, population__isnull=False).first()
    if record:
        return record.population, False
    if PopulationProjection.objects.filter(city=city, scenario=DEFAULT_SCENARIO).exists():
        return projected_population(city, year), False
    return (city.currentPopulation or None), True


def average_household_size(population, households):
    """Persons per private household, or None without both inputs."""
    if not population or not households:
        return None
    return population / households


def demand_units(population, average_size):
    """Homes needed to house `population` at `average_size` persons each (None without inputs)."""
    if population is None or not average_size:
        return None
    return round(population / average_size)


def what_if_demand(stored_demand, population, baseline_population, stored_size, size):
    """
    Dashboard demand for a population / persons-per-home what-if, never written.

        demand = stored_demand x (population / baseline_population) x (stored_size / size)

    It is a deviation from the stored baseline, so with default controls the
    dashboard equals the stored demand even when `population` only covers the
    imported neighborhoods of a city (the ratio cancels the coverage). Without a
    stored demand it falls back to population / size.
    """
    if not size:
        return stored_demand
    if stored_demand and baseline_population and stored_size and population is not None:
        return round(stored_demand * (population / baseline_population) * (stored_size / size))
    return demand_units(population, size) or stored_demand


def multi_person_size(population, households, one_person_households):
    """
    Persons per multi-person household of a municipality (CBS 86291NED):

        m = (population - one_person) / (households - one_person)

    One-person households hold one person each, so they are taken out of both
    terms. None without the three inputs or without a multi-person household.
    """
    if not population or not households or one_person_households is None:
        return None
    multi = households - one_person_households
    if multi <= 0 or population <= one_person_households:
        return None
    return (population - one_person_households) / multi


def living_alone_share(one_person_households, residents):
    """Share (0-1) of the residents who live alone: each one-person household holds one person."""
    if not one_person_households or not residents:
        return None
    return min(one_person_households / residents, 1.0)


def alone_demand_factor(average_size, alone_share, multi_size):
    """
    Factor on the demand (residents / average size) for a neighborhood whose share
    of residents living alone is `alone_share`, against the municipality:

        homes = share x R + (1 - share) x R / m          (R residents)
        factor = homes / (R / average_size) = average_size x (share + (1 - share) / m)

    It is 1 when the neighborhood has the municipality's share (the average is then
    already right) and above 1 when more residents live alone (each takes a whole
    home). 1.0 without the inputs, so the dashboard falls back to the average alone.
    """
    if not average_size or alone_share is None or not multi_size:
        return 1.0
    share = min(max(alone_share, ALONE_MIN / 100.0), ALONE_MAX / 100.0)
    return average_size * (share + (1.0 - share) / multi_size)


def household_split(residents, homes, alone_share):
    """
    (single, other_homes, other_size): `homes` split into one-person homes (the
    residents living alone, housed first) and the others.

        single     = min(residents x share, homes)
        other_size = (residents - single) / (homes - single)

    The other homes hold more than the plain average because the average already
    counts the one-person homes. `other_size` is None when no home is left;
    all None without residents or homes.
    """
    if not residents or not homes:
        return None, None, None
    share = min(max(alone_share or 0.0, ALONE_MIN / 100.0), ALONE_MAX / 100.0)
    single = min(round(residents * share), homes)
    other = homes - single
    return single, other, ((residents - single) / other if other else None)


def housed_residents(dwellings, residents, homes, alone_share=None):
    """
    Residents the `dwellings` house, never more than the `residents` there are.

    One-person homes are filled first, every other dwelling holds `other_size`
    (household_split). Dwellings beyond the occupied `homes` stand empty, so the
    stock cannot house more than the residents (BAG alone would give dwellings x
    average size, more than the population).
    """
    if not dwellings or not residents or not homes:
        return 0
    single, _, other_size = household_split(residents, homes, alone_share)
    used_single = min(single, dwellings)
    capacity = used_single + (dwellings - used_single) * (other_size or 0.0)
    return round(min(capacity, residents))


def dwelling_gap(needed, stock):
    """
    Homes still to build for a population: needed - stock (negative = surplus).
    None without both.

    DAG edge: Housing_Demand -> Housing_Gap (scenario runs)
    """
    if needed is None or stock is None:
        return None
    return needed - stock


# ── House prices: CBS WOZ level and NVM market trend ─────────────────
#
#   woz_per_sqm   = mean WOZ value of the neighbourhood's dwellings / their mean floor area
#   annual price  = mean of the year's quarterly NVM median price per m2 (dwelling type "Totaal")
#   index         = 100 x annual price / annual price of the region's base year
#
# The WOZ value is the CBS "Kerncijfers wijken en buurten" mean (rounded to
# 1 000 EUR by CBS, only for regions with at least 20 dwellings and a WOZ value
# for 85 % of them). The table of year Y holds the WOZ value at the valuation
# date 1 January of Y-1. The floor area is the BAG usable area (oppervlakte,
# builtup.Property.livingArea else grossArea) of the dwellings inside the
# neighbourhood: a ratio of two means, not a mean of per-dwelling ratios.

# Smallest and largest plausible mean dwelling area (m2) for the ratio above: the
# lower bound is the Bbl minimum (MIN_DWELLING_AREA_SQM); 500 m2 only guards
# against a broken area column.
WOZ_AREA_MAX_SQM = 500.0

WOZ_METHOD = "mean WOZ / mean BAG dwelling area (v1)"
# Years used by the index need all four quarters of NVM before they count as a full year.
NVM_QUARTERS_PER_YEAR = 4
INDEX_BASE = 100.0
INDEX_METHOD = "NVM median price per m2, annual mean of quarters, base year = 100 (v1)"


def woz_valuation_year(table_year):
    """Year of the WOZ valuation date (1 January) of a CBS Kerncijfers table."""
    return table_year - 1


def woz_per_sqm(avg_woz_eur, mean_area_sqm):
    """
    WOZ value per m2 of floor area, EUR/m2. None without both inputs or when the
    mean area is outside [MIN_DWELLING_AREA_SQM, WOZ_AREA_MAX_SQM].
    """
    if not avg_woz_eur or not mean_area_sqm or avg_woz_eur <= 0:
        return None
    if not MIN_DWELLING_AREA_SQM <= mean_area_sqm <= WOZ_AREA_MAX_SQM:
        return None
    return avg_woz_eur / mean_area_sqm


def annual_price_per_sqm(quarterly_prices):
    """
    Mean of a year's quarterly median prices per m2, EUR/m2. `quarterly_prices`
    is the list of the quarters that have a value; fewer than four quarters
    give None (a part-year mean would mix seasons).
    """
    prices = [p for p in quarterly_prices if p]
    if len(prices) < NVM_QUARTERS_PER_YEAR:
        return None
    return sum(prices) / len(prices)


def price_index(price, base_price):
    """
    House price index (base year = 100) from an annual price per m2 and the base
    year's price. None without both (a stored index is then kept).

    DAG edge: Market_Reports -> House_Price_Index
    """
    if not price or not base_price or price <= 0 or base_price <= 0:
        return None
    return INDEX_BASE * price / base_price
