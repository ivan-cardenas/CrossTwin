"""
The population -> consumption -> demand -> supply security -> service time
chain of the water supply, written once and used by both paths:

* the stored path: ConsumptionCapita / TotalWaterDemand / SupplySecurity
  save() (re-run by watersupply/signals.py) with the *baseline* population of
  the record's year, i.e. the CBS median forecast without extra growth;
* the dashboard path: views._build_indicators with the population what-if of
  the request (forecast variant + extra growth from the population dock),
  which is never written to the database.

So the population slider is a deviation from the stored baseline computed by
the same equations, not a second implementation of them. Everything here is
pure except baseline_population(), the one function that reads the database.

DAG edges: Total_Population, ConsumptionCapita -> Total_Water_Demand
           Total_Water_Demand, Total_Water_Prod -> Supply_Security -> Service_Time
"""

SERVICE_HOURS_MAX = 24


def baseline_population(city, year):
    """
    Population the stored chain uses for `city` in `year`: the CBS median
    forecast without extra growth (the population dock's default), falling
    back to the current population when no projection is imported. None when
    the city has neither, so callers can keep a stored value instead of
    writing zero.

    DAG edge: Population_Growth -> Total_Population
    """
    from administrative.population import get_population  # avoid import cycle at startup

    population = get_population(city, year)
    if not population and city.currentPopulation is None:
        return None
    return population


def demand_m3_d(consumption_L_d, population):
    """Daily water demand in m3/day: L/person/day / 1000 * persons."""
    return consumption_L_d / 1000 * population


def consumption_m3_yr(consumption_L_d, population):
    """Yearly water consumption in m3/year."""
    return demand_m3_d(consumption_L_d, population) * 365


def supply_security_pct(production_m3_d, demand):
    """Production as a percentage of demand (0 when there is no demand)."""
    return production_m3_d / demand * 100 if demand else 0


def service_time_hours(production_m3_d, demand):
    """
    Hours of supply per day: full service when production covers demand,
    otherwise the covered share of 24 h. Without demand, full service only if
    something is produced.
    """
    if not demand:
        return SERVICE_HOURS_MAX if production_m3_d > 0 else 0
    if production_m3_d >= demand:
        return SERVICE_HOURS_MAX
    return round(SERVICE_HOURS_MAX * production_m3_d / demand, 1)
