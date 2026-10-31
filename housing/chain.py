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


def baseline_population(city, year):
    """
    (population, partial) the stored housing chain uses for `city` in `year`.

    City.currentPopulation is the sum of the neighborhoods imported locally,
    often far below the real city, while the household stock is whole-gemeente
    CBS, so the local sum must not be divided by a CBS household size. In order:
      1. the population stored with that year's HouseholdSize (the forecast
         median of that year, or a manually entered value);
      2. the CBS median forecast (watersupply.chain.baseline_population), when
         the city has projections;
      3. the current population, with partial=True: it only covers what is
         imported, so a demand built on it understates the city.
    The population is None when the city has none of them.

    DAG edge: Population_Growth -> Total_Population
    """
    from administrative.models import PopulationProjection
    from administrative.population import DEFAULT_SCENARIO
    from watersupply.chain import baseline_population as projected_population

    from .models import HouseholdSize

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
