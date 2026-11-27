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


# ── House prices: CBS WOZ level ─────────────────────────────────────
#
#   woz_per_sqm   = mean WOZ value of the area's dwellings / their mean floor area
#
# The WOZ value is the CBS mean (rounded to 1 000 EUR for the neighborhood tables, only for regions
# with at least 20 dwellings and a WOZ value for 85 % of them). The newest table year available is
# used as it is: no valuation-date shift is applied. The floor area is the BAG usable area
# (oppervlakte, builtup.Property.livingArea else grossArea) of the dwellings of the area: a ratio of
# two means, not a mean of per-dwelling ratios.

# Smallest and largest plausible mean dwelling area (m2) for the ratio above: the
# lower bound is the Bbl minimum (MIN_DWELLING_AREA_SQM); 500 m2 only guards
# against a broken area column.
WOZ_AREA_MAX_SQM = 500.0

WOZ_METHOD = "mean WOZ / mean BAG dwelling area (v1)"


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


# ── House price index: base year and extrapolation ──────────────────
#
#   index_t   = 100 x level_t / level_base                     (observed years, base year = 100)
#   ln(index) = a + b x year    (least squares over the last HPI_TREND_YEARS observed years)
#   g_recent  = exp(b) - 1                                     (the recent growth rate)
#   g_long    = (index_last / index_first)^(1 / years) - 1     (the average growth over the whole observed series)
#   g_k       = g_long + (g_recent - g_long) x 0.5^(k / HPI_FADE_HALF_LIFE_YEARS)     k = years after the last observed year
#   index_k   = index_(k-1) x (1 + g_k)                        up to HPI_END_YEAR
#
# The recent trend (a boom, or a slump) is not repeated for 75 years: the growth rate fades from the recent trend
# towards the long-run average of the observed series, halfway after HPI_FADE_HALF_LIFE_YEARS. The long-run rate is
# the dashboard's slider (default: the average of the observed series, 1995-2025 for the CBS national index).
# It is a trend continuation, not a forecast: no demand, income, interest-rate or affordability feedback.

HPI_BASE_YEAR = 2019
HPI_END_YEAR = 2100
HPI_TREND_YEARS = 10          # observed years the recent growth rate is fitted on
HPI_WINDOW_YEARS = 5          # years the dashboard chart shows at a time (centred on the scenario year)
HPI_MIN_TREND_POINTS = 3      # fewer observed years give no trend, hence no projection
# Years until the recent growth has faded halfway to the long-run rate. A modelling assumption (no published
# value): the recent 10-year boom is mostly gone after two half-lives (10 years), the near term stays close to it.
# A calibration parameter to test in a sensitivity run, not a measured value.
HPI_FADE_HALF_LIFE_YEARS = 5
HPI_LONG_RUN_MIN, HPI_LONG_RUN_MAX = 0.0, 10.0   # % per year, range of the dashboard's long-run growth slider
HPI_METHOD = ("area WOZ value per m2 rebased to the base year, carried on with the national CBS index, whose growth fades "
              "from the last-10-years trend to the long-run average with a 5-year half-life, to 2100 (v3)")


def rebase_index(series, base_year=HPI_BASE_YEAR):
    """
    [(year, level)] -> [(year, index)] with the level of `base_year` = 100, sorted by year.
    Empty when the series has no positive level in the base year.
    """
    levels = {year: value for year, value in series if value is not None}
    base = levels.get(base_year)
    if not base or base <= 0:
        return []
    return [(year, round(100.0 * value / base, 2)) for year, value in sorted(levels.items()) if value > 0]


def trend_growth(index_points, trend_years=HPI_TREND_YEARS):
    """
    Annual log growth rate b of the last `trend_years` observed years (OLS of ln(index) on the year);
    None with fewer than HPI_MIN_TREND_POINTS points.
    """
    import math

    points = sorted(index_points)[-trend_years:]
    if len(points) < HPI_MIN_TREND_POINTS:
        return None
    xs, ys = [p[0] for p in points], [math.log(p[1]) for p in points]
    mean_x, mean_y = sum(xs) / len(xs), sum(ys) / len(ys)
    spread = sum((x - mean_x) ** 2 for x in xs)
    return sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys)) / spread


def long_run_growth(index_points):
    """Average annual growth (%) over the whole observed series, first to last year; None under two years."""
    points = sorted(index_points)
    if len(points) < 2 or points[-1][0] == points[0][0] or points[0][1] <= 0:
        return None
    years = points[-1][0] - points[0][0]
    return ((points[-1][1] / points[0][1]) ** (1.0 / years) - 1.0) * 100.0


def faded_growth(recent_pct, long_run_pct, k, half_life=HPI_FADE_HALF_LIFE_YEARS):
    """Annual growth (%) `k` years after the last observed year: the recent rate fading to the long-run one."""
    return long_run_pct + (recent_pct - long_run_pct) * 0.5 ** (k / half_life)


def hpi_curve(series, base_year=HPI_BASE_YEAR, end_year=HPI_END_YEAR, long_run_pct=None):
    """
    The house price index curve of a [(year, level)] series: the observed years rebased to `base_year` = 100 and
    the growth extrapolated year by year to `end_year` (recent trend fading to `long_run_pct`, default the average
    growth of the whole observed series).

    Returns None without a base-year level; {"observed", "projected", "recent_pct", "long_run_pct",
    "long_run_default_pct", "growth_pct" (= recent_pct), "half_life", "base_year", "method"} otherwise, with an empty
    `projected` (and no rates) when there are too few years for a trend.
    Reads stored values only (the stored index or the CBS WOZ value per m2); no DAG edge.
    """
    import math

    observed = rebase_index(series, base_year)
    if not observed:
        return None
    b = trend_growth(observed)
    default = long_run_growth(observed)
    last_year, last_value = observed[-1]
    out = {"observed": observed, "projected": [], "base_year": base_year, "method": HPI_METHOD, "source": "series",
           "half_life": HPI_FADE_HALF_LIFE_YEARS, "recent_pct": None, "growth_pct": None, "long_run_pct": None,
           "long_run_default_pct": None if default is None else round(default, 2)}
    if b is None or default is None:
        return out
    recent = (math.exp(b) - 1.0) * 100.0
    long_run = default if long_run_pct is None else long_run_pct
    value, projected = last_value, []
    for k, year in enumerate(range(last_year + 1, end_year + 1), start=1):
        value *= 1.0 + faded_growth(recent, long_run, k) / 100.0
        projected.append((year, round(value, 2)))
    out.update(projected=projected, recent_pct=round(recent, 2), growth_pct=round(recent, 2),
               long_run_pct=round(long_run, 2))
    return out


def hpi_local_curve(series, national, base_year=HPI_BASE_YEAR):
    """
    The curve of an area: its own observed [(year, level)] series (the CBS WOZ value per m2 of its neighborhoods)
    rebased to `base_year` = 100, carried beyond its last observed year with the year-on-year change of the national
    curve `national` (hpi_curve of the national index: observed national years, then the faded extrapolation).

        index_y = index_last x national_y / national_last          for y after the area's last observed year

    None without a base-year level of the area or without a national curve covering its last year.
    """
    observed = rebase_index(series, base_year)
    if not observed or not national:
        return None
    nat = {**dict(national["observed"]), **dict(national["projected"])}
    last_year, last_value = observed[-1]
    reference = nat.get(last_year)
    if not reference:
        return None
    projected = [(year, round(last_value * nat[year] / reference, 2)) for year in sorted(nat) if year > last_year]
    return {**national, "observed": observed, "projected": projected, "source": "area"}


def hpi_at(curve, year):
    """
    (index, previous index, projected?) of a curve at `year`; (None, None, False) outside the curve.
    The previous index is that of year - 1, None when the curve does not cover it.
    """
    if not curve:
        return None, None, False
    values = {y: v for y, v in curve["observed"]}
    projected = {y: v for y, v in curve["projected"]}
    value = values.get(year, projected.get(year))
    previous = values.get(year - 1, projected.get(year - 1))
    return value, previous, year in projected and year not in values


def hpi_price_factor(curve, year, base_year):
    """
    Factor on a modelled price per m2 for the scenario `year`: the house price index of `year` over that of
    `base_year`, the WOZ year the price fit was calibrated on. 1.0 without a curve or a value for either year.

        price_year = price_stored x I_year / I_base_year

    DAG edge: House_Price_Index -> Property (dashboard path; the stored price stays at the fit's WOZ year)
    """
    value, _, _ = hpi_at(curve, year)
    base, _, _ = hpi_at(curve, base_year)
    if not value or not base:
        return 1.0
    return value / base


# ── Mortgage: historical rate and monthly payment ───────────────────
#
#   rate_y    = the year's mean of the monthly rates of MORTGAGE_HEADLINE (DNB MFI statistics)
#   payment   = L x r / (1 - (1 + r)^-n),  r = rate / 12 / 100,  n = 12 x term (years)

MORTGAGE_RATE_MIN, MORTGAGE_RATE_MAX = 0.0, 10.0   # % per year; the slider range and the card's bar cap
# the series the slider starts from (housing.MortgageRate): all loans for house purchase, new business, all fixation periods
MORTGAGE_HEADLINE = {"instrument": "Loans for house purchasing - Total", "flowType": "New business",
                     "maturity": "Total", "rateFixation": "Total"}
MORTGAGE_DEFAULT_TERM_YEARS = 30                   # the Dutch standard annuity term, when no recorded mortgage gives one


def mortgage_rate_at(rates, year):
    """
    (rate %, year it belongs to) of {year: rate}: that of `year`, else the latest earlier year; (None, None)
    when there is none.
    """
    usable = [y for y, r in rates.items() if r is not None and y <= year]
    if not usable:
        return None, None
    best = max(usable)
    return rates[best], best


def annuity_payment(loan, rate_pct, term_years=MORTGAGE_DEFAULT_TERM_YEARS):
    """Monthly payment of an annuity mortgage, EUR; None without a loan or a term. A zero rate repays linearly."""
    if not loan or not term_years or rate_pct is None:
        return None
    n = 12 * term_years
    r = rate_pct / 100.0 / 12.0
    return loan / n if r == 0 else loan * r / (1.0 - (1.0 + r) ** -n)


# ── Accessibility -> modelled price (association-based, Phase 4 of docs/ACCESSIBILITY_PLAN.md) ──
#
#   modelled = S x (1 + g) x exp( a + SUM_t beta_t T(A_t) + SUM_k gamma_k z_k + mu_c )
#
# One equation for the whole city (housing.PriceModel.prediction), calibrated on the CBS WOZ value per m2 of the
# PC6 postcode areas; a dwelling's price is that equation applied to the dwelling's own variables. The WOZ value
# of its area is not an input of the price.
#
#   a, mu_c     intercept and municipality effect of the fit (mu_c = 0 for a fit on one municipality)
#   t           a term "mode:category": how reachable one kind of amenity is (supermarket, shop, school,
#               bus stop, train station, park, ...) on foot or by bicycle; A_t is the building's value of
#               that category, 0-100 (builtup chain.category_value x 100), beta_t its coefficient: only the terms
#               that survived the redundancy and influence screening of the fit have one
#   T           the functional form of the fit: identity ("linear") or ln(1 + A)
#   z_k         the controls: construction year, apartment share, rental share, energy label, socio-economic
#               status, distance to the municipal centre; a control a dwelling lacks is the fit's mean of it
#   S           Duan's smearing factor, so that the median-like exp() reproduces the level of the calibration data
#   g           what-if market change (0 for the stored value)
#
# The betas come from a cross-section of postcode areas, so the result reads as an association, not as
# the causal effect of one amenity: it credits accessibility with everything that goes with it
# (prestige, jobs, older housing), and the WOZ value lags the market. Every modelled price carries
# PRICE_LABEL. Adding an amenity changes the A_t of the buildings near it and with them the price, through the
# same betas everywhere.

PRICE_METHOD = "hedonic city-wide equation on amenity categories, calibrated on WOZ per PC6 (v3)"
PRICE_LABEL = "association-based scenario (upper bound), not a forecast"
PRICE_FORMS = ("linear", "log1p")
TERM_SEP = ":"

# What-if range of the dashboard's market slider (never written).
MARKET_GROWTH_MIN, MARKET_GROWTH_MAX = -30.0, 30.0       # % change of the market on top of the model
SCORE_MIN, SCORE_MAX = 0.0, 100.0


def term_key(mode, category):
    """The name of one accessibility term of the price model: 'walk:supermarket'."""
    return f"{mode}{TERM_SEP}{category}"


def split_term(term):
    """(mode, category) of a term name."""
    mode, _, category = term.partition(TERM_SEP)
    return mode, category


def candidate_terms():
    """Every term the price model can use: each mode x each amenity category of the accessibility score."""
    from builtup.calculations import chain as access

    return [term_key(mode, category) for mode in access.MODES for category in access.CATEGORIES]


def term_values(distances, mode):
    """
    {term: value 0-100} of one building and mode from its stored Accessibility.distances
    ({category: [network metres to the k nearest]}). A category with no reachable amenity is 0, as in the score.
    """
    from builtup.calculations import chain as access

    return {term_key(mode, category): 100.0 * access.category_value((distances or {}).get(category), mode, omegas)
            for category, (_weight, omegas) in access.CATEGORIES.items()}


def access_transform(score, form):
    """T(A): the score as the fit entered it. None stays None."""
    import math

    if score is None:
        return None
    if form == "log1p":
        return math.log1p(max(score, SCORE_MIN))
    if form == "linear":
        return float(score)
    raise ValueError(f"unknown functional form {form!r}")


def market_growth_factor(growth_pct):
    """1 + g: the what-if market change as a factor on the price."""
    return 1.0 + growth_pct / 100.0


def log_price(prediction, access, controls, city, form=None):
    """
    ln of the modelled price before smearing: a + SUM beta T(A) + SUM gamma z + mu_c, from `prediction`
    (PriceModel.prediction). `access` is {term: value}, `controls` {name: value or None}, `city` the municipality id.
    None when the equation cannot be applied: no intercept, a term without a value (the building has no stored
    accessibility), a control that neither the dwelling nor the fit has, or a municipality the fit has no effect for.
    """
    form = form or prediction.get("form", "linear")
    intercept, terms = prediction.get("intercept"), prediction.get("terms") or {}
    if intercept is None or not terms:
        return None
    total = intercept
    for term, beta in terms.items():
        value = access.get(term)
        if beta is None or value is None:
            return None
        total += beta * access_transform(value, form)
    for name, gamma in (prediction.get("controls") or {}).items():
        value = controls.get(name)
        if value is None:
            value = (prediction.get("control_means") or {}).get(name)
        if value is None or gamma is None:
            return None
        total += gamma * value
    cities = prediction.get("cities") or {}
    if cities:
        if city is None or str(city) not in cities:
            return None
        total += cities[str(city)]
    return total


def modelled_price_per_sqm(prediction, access, controls, city, form=None, growth_pct=0.0):
    """
    Modelled price per m2 of a dwelling, EUR/m2: association-based scenario (upper bound),
    not a forecast. The stored value uses growth 0; the dashboard's market slider changes only that.

    None when the equation cannot be applied (the stored price is kept).

    DAG edge: Accessibility -> Property
    """
    import math

    value = log_price(prediction, access, controls, city, form)
    if value is None:
        return None
    return math.exp(value) * prediction.get("smearing", 1.0) * market_growth_factor(growth_pct)
