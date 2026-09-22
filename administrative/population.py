"""
Population projection for any administrative unit.

CBS table 85173NED is published per gemeente, so projections are stored per City
(PopulationProjection). Every other level is derived from those city values:

  City          the stored projection for the year, extrapolated (see
                `extrapolate`) for a year outside the imported horizon, and
                falling back to the current population when there isn't
                enough data to extrapolate from
  District /    the unit's own current population, scaled by how much CBS
  Neighborhood  expects the *city* to grow between its earliest imported
                year and the target year (see `_city_growth_factor`) --
                never by the unit's share of `city.currentPopulation`. That
                field is the sum of whichever districts/neighborhoods of the
                city happen to be imported locally, which is very often far
                smaller than CBS's own (real, whole-city) numbers, so a
                share computed against it would overstate every unit's
                projection. Applying the city's percentage growth directly
                to the unit's own (accurate) current population sidesteps
                that entirely -- it only ever needs CBS's numbers to agree
                with themselves, not with local administrative coverage.
  Province      the sum of its cities, i.e. the result of the changes below it

`growth_adjust_pct` is the what-if control: extra growth in percent per year,
compounded from REFERENCE_YEAR onward and applied on top of the chosen variant.

DAG edges: Population_Growth -> Total_Population
           Total_Population  -> Total_Water_Demand / NumberUsers
"""
from collections import defaultdict

from .admin_units import city_of
from .models import City, District, Neighborhood, PopulationProjection, Province

# First year of the year selector (the "baseline"); the growth adjustment only
# applies to years after it.
REFERENCE_YEAR = 2025
DEFAULT_SCENARIO = PopulationProjection.Scenario.PROGNOSE.value
SCENARIOS = [value for value, _label in PopulationProjection.Scenario.choices]


def normalize_scenario(scenario):
    """Unknown/empty variant names fall back to the median forecast."""
    return scenario if scenario in SCENARIOS else DEFAULT_SCENARIO


def _series(city_ids, scenario):
    """{city_id: {year: projected population}} for one forecast variant."""
    series = defaultdict(dict)
    rows = PopulationProjection.objects.filter(
        city_id__in=city_ids, scenario=scenario
    ).values_list('city_id', 'year', 'population')
    for city_id, year, population in rows:
        series[city_id][year] = population
    return series


def _adjust(value, year, growth_adjust_pct):
    """Compound the extra annual growth from REFERENCE_YEAR to `year`."""
    years = max(year - REFERENCE_YEAR, 0)
    if not growth_adjust_pct or not years:
        return value
    return value * (1 + growth_adjust_pct / 100) ** years


def extrapolate(city_series, year):
    """
    Population for `year` outside the years CBS actually published for one
    city, projected from the compound annual growth rate implied by the
    first and last imported years (e.g. a year past 2050 once the current
    85173NED horizon is exhausted, or one before its earliest year).

    None when there's nothing to extrapolate from (fewer than two imported
    years, or a non-positive starting value) -- the caller then falls back
    to the current population instead.
    """
    years = sorted(city_series)
    if len(years) < 2:
        return None
    y0, y1 = years[0], years[-1]
    v0, v1 = city_series[y0], city_series[y1]
    if v0 <= 0 or y1 == y0:
        return None
    annual_growth = (v1 / v0) ** (1 / (y1 - y0)) - 1
    anchor_year, anchor_value = (y1, v1) if year > y1 else (y0, v0)
    return anchor_value * (1 + annual_growth) ** (year - anchor_year)


def annual_growth_rate(city, scenario=DEFAULT_SCENARIO):
    """
    CBS's compound annual population growth rate for `city`, in percent per
    year -- the same rate `extrapolate` derives internally from the earliest
    and latest imported PopulationProjection years for `scenario`.

    None when fewer than two years are imported for the city (nothing to
    derive a rate from yet); City.save() then leaves popGrowthRate untouched.

    DAG edge: Population_Growth -> Total_Population (City.popGrowthRate)
    """
    scenario = normalize_scenario(scenario)
    city_series = _series([city.pk], scenario).get(city.pk, {})
    years = sorted(city_series)
    if len(years) < 2:
        return None
    y0, y1 = years[0], years[-1]
    v0, v1 = city_series[y0], city_series[y1]
    if v0 <= 0 or y1 == y0:
        return None
    return ((v1 / v0) ** (1 / (y1 - y0)) - 1) * 100


def _city_value(city, series, year, growth_adjust_pct):
    """Projected population of one city for `year` (or its current one if year is None)."""
    if year is None:
        return city.currentPopulation or 0
    city_series = series.get(city.pk, {})
    base = city_series.get(year)
    if base is None:
        base = extrapolate(city_series, year)
    if base is None:
        base = city.currentPopulation or 0
    return _adjust(base, year, growth_adjust_pct)


def _city_growth_factor(city, series, year, growth_adjust_pct):
    """
    How much CBS expects the city itself to grow between its earliest
    imported projection year (REFERENCE_YEAR when that's one of them) and
    `year`, using only CBS's own numbers on both sides of the ratio --
    never `city.currentPopulation`.

    None when there are fewer than two imported years for the city, since a
    single data point carries no growth information to extrapolate from;
    the caller then falls back to the older share-of-city approach.
    """
    city_series = series.get(city.pk, {})
    if len(city_series) < 2:
        return None
    baseline_year = REFERENCE_YEAR if REFERENCE_YEAR in city_series else min(city_series)
    baseline = _city_value(city, series, baseline_year, growth_adjust_pct)
    if not baseline:
        return None
    return _city_value(city, series, year, growth_adjust_pct) / baseline


def population_by_year(unit, years, scenario=DEFAULT_SCENARIO, growth_adjust_pct=0.0):
    """
    {year: projected population} of `unit` (Province, City, District or
    Neighborhood) for each year in `years`, using one query for all of them.
    """
    scenario = normalize_scenario(scenario)
    growth = float(growth_adjust_pct or 0)

    if isinstance(unit, Province):
        cities = list(City.objects.filter(province=unit))
        series = _series([c.pk for c in cities], scenario)
        return {
            y: round(sum(_city_value(c, series, y, growth) for c in cities))
            for y in years
        }

    if isinstance(unit, City):
        series = _series([unit.pk], scenario)
        return {y: round(_city_value(unit, series, y, growth)) for y in years}

    if isinstance(unit, (District, Neighborhood)):
        city = city_of(unit)
        current = unit.currentPopulation or 0
        if city is None:
            return {y: current for y in years}   # nothing to scale by
        series = _series([city.pk], scenario)
        result = {}
        for y in years:
            factor = _city_growth_factor(city, series, y, growth)
            if factor is not None:
                result[y] = round(current * factor)
            elif city.currentPopulation:
                # Only one imported year for the city: no growth rate to
                # derive, so fall back to scaling by the unit's share of
                # `city.currentPopulation` (accurate only when every
                # district/neighborhood of the city has been imported).
                share = current / city.currentPopulation
                result[y] = round(share * _city_value(city, series, y, growth))
            else:
                result[y] = current
        return result

    raise TypeError(f"population_by_year: unsupported unit type {type(unit)!r}")


def get_population(unit, year=None, scenario=DEFAULT_SCENARIO, growth_adjust_pct=0.0):
    """
    Projected population of `unit` in `year` (its current population if `year`
    is None). Without any projection data this equals the current population,
    so dashboards keep working before the CBS table has been imported.
    """
    if year is None:
        return unit.currentPopulation or 0
    return population_by_year(unit, [year], scenario, growth_adjust_pct)[year]


def projection_years(unit):
    """Sorted years for which projections exist for the cities behind `unit`."""
    if isinstance(unit, Province):
        cities = City.objects.filter(province=unit)
    else:
        city = city_of(unit)
        cities = City.objects.filter(pk=city.pk) if city else City.objects.none()
    return sorted(set(
        PopulationProjection.objects.filter(city__in=cities).values_list('year', flat=True)
    ))


def population_curve(unit, scenario=DEFAULT_SCENARIO, growth_adjust_pct=0.0):
    """[{'year', 'population'}, ...] over every projected year; [] if none imported."""
    years = projection_years(unit)
    if not years:
        return []
    values = population_by_year(unit, years, scenario, growth_adjust_pct)
    return [{'year': y, 'population': values[y]} for y in years]


# Bounds for the what-if slider, so a stray query string can't produce absurd numbers.
MAX_GROWTH_ADJUST_PCT = 5.0


def population_params(query):
    """
    (scenario, growth_adjust_pct) from a request's query parameters
    `pop_scenario` and `pop_growth`; invalid or missing values give the defaults
    (median forecast, no adjustment) and growth is clamped to +-MAX_GROWTH_ADJUST_PCT.
    """
    scenario = normalize_scenario(query.get('pop_scenario'))
    try:
        growth = float(query.get('pop_growth') or 0)
    except (TypeError, ValueError):
        growth = 0.0
    if growth != growth:  # NaN
        growth = 0.0
    growth = max(-MAX_GROWTH_ADJUST_PCT, min(MAX_GROWTH_ADJUST_PCT, growth))
    return scenario, growth
