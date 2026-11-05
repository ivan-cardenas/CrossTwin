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


def recharge_Mm3_yr(infiltration_depth_cm_yr, area_m2):
    """
    Yearly recharge of a fresh-water source in Mm3/year: the depth of water
    that infiltrates in a year over the source's area.
        V = depth [cm/yr] / 100 * area [m2] / 1e6
    The infiltration *rate* (cm/h) is a capacity during rain, not a yearly
    amount, so it does not enter here.

    DAG edge: Infiltration -> Available_FW
    """
    return infiltration_depth_cm_yr / 100 * area_m2 / 1e6


def recharge_depth_cm_yr(daily_rain_mm, et_ref_mm_yr, composition):
    """
    Yearly recharge depth (cm/yr) of an area from a year of daily rain, a
    year's reference evapotranspiration and its soil-group x land-cover
    composition, as a simple yearly water balance:

        runoff_d = sum over pieces of SCS Q(P_d, CN_piece) x area_piece / area
        recharge = max(0, sum(P_d) - sum(runoff_d) - ET_ref) / 10

    Q is computed per piece and day (physicalEnv.soil.scs_runoff_mm), because
    it is non-linear in both P and CN. Simplifications: Makkink reference ET
    with crop factor 1 for every surface, no soil-moisture store between days
    (a dry year gives 0, not a deficit carried over), and pieces without a
    curve number are left out of the area.

    composition: [(soil_group, land_cover_class, area_m2), ...]
    Returns None when no piece has a curve number.

    DAG edges:  Meteorology  -> Available_FW
                LandCover    -> Infiltration -> Available_FW
                Soil_Type    -> Infiltration -> Available_FW
    """
    balance = yearly_water_balance_mm(daily_rain_mm, et_ref_mm_yr, composition)
    return None if balance is None else balance['recharge_mm'] / 10


def yearly_water_balance_mm(daily_rain_mm, et_ref_mm_yr, composition):
    """
    The yearly water balance behind recharge_depth_cm_yr, in mm over the
    area: {'rain_mm', 'runoff_mm', 'et_mm', 'recharge_mm'}, where

        recharge = max(0, rain - runoff - ET_ref)
        et       = the part of ET_ref the rain left after runoff
                   (min(ET_ref, rain - runoff)), so rain = runoff + et + recharge

    None when no piece has a curve number. See recharge_depth_cm_yr for the
    method and its simplifications.

    DAG edges:  Meteorology  -> Available_FW
                LandCover    -> Infiltration -> Available_FW
                Soil_Type    -> Infiltration -> Available_FW
    """
    from physicalEnv.soil import curve_number, scs_runoff_mm

    # Pieces with the same curve number behave alike: weight per CN.
    area_by_cn = {}
    for soil_group, land_cover_class, area_m2 in composition:
        cn = curve_number(land_cover_class, soil_group)
        if cn is None or area_m2 <= 0:
            continue
        area_by_cn[cn] = area_by_cn.get(cn, 0.0) + area_m2
    total = sum(area_by_cn.values())
    if not total:
        return None
    shares = [(cn, a / total) for cn, a in area_by_cn.items()]
    rain = runoff = 0.0
    for p in daily_rain_mm:
        if not p or p <= 0:
            continue
        rain += p
        runoff += sum(scs_runoff_mm(p, cn) * share for cn, share in shares)
    et_ref = et_ref_mm_yr or 0.0
    return {
        'rain_mm':     rain,
        'runoff_mm':   runoff,
        'et_mm':       min(et_ref, rain - runoff),
        'recharge_mm': max(0.0, rain - runoff - et_ref),
    }
