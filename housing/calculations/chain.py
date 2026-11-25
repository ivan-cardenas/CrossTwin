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

# Slider range of the dashboard's "persons per home" control; also the plausible
# range stored values are checked against (NL average is ~2.1, 1-person-heavy
# student cities fall below 1.8).
SIZE_MIN = 1.0
SIZE_MAX = 4.0

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


def housed_residents(dwellings, average_size):
    """Residents living in `dwellings` occupied at `average_size` persons each."""
    if not dwellings or not average_size:
        return 0
    return round(dwellings * average_size)


def dwelling_gap(needed, stock):
    """
    Homes still to build for a population: needed - stock (negative = surplus).
    None without both.

    DAG edge: Housing_Demand -> Housing_Gap (scenario runs)
    """
    if needed is None or stock is None:
        return None
    return needed - stock
