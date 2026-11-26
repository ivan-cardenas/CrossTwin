"""
Database side of the house price index: which NVM region a neighborhood belongs
to and the region's annual price per m2. The equations are in chain.py.

DAG edges: Market_Reports -> House_Price_Index
"""
from . import chain


def region_of_neighborhood(neighborhood_id):
    """NVM region name of the neighborhood's municipality; None without a mapping."""
    from housing.models import NVMRegionMapping

    return (NVMRegionMapping.objects
            .filter(city__district__neighborhood__pk=neighborhood_id)
            .values_list("region", flat=True).first())


def annual_prices(region):
    """
    {year: mean of the quarterly median price per m2 ("Totaal")} of an NVM
    region, only for years with all four quarters (chain.annual_price_per_sqm).
    """
    from housing.models import NVMMarketReport

    rows = (NVMMarketReport.objects
            .filter(region=region, dwellingType=NVMMarketReport.TOTAL, pricePerSqm_EUR__isnull=False)
            .values_list("year", "quarter", "pricePerSqm_EUR"))
    by_year = {}
    for year, _quarter, price in rows:
        by_year.setdefault(year, []).append(price)
    annual = {year: chain.annual_price_per_sqm(prices) for year, prices in by_year.items()}
    return {year: price for year, price in annual.items() if price is not None}


def index_from_prices(annual, year):
    """
    {"index", "base_year", "price"} of `year` against the earliest complete year of
    `annual` (the base year itself is 100); None when `year` has no annual price.
    """
    if year not in annual:
        return None
    base_year = min(annual)
    index = chain.price_index(annual[year], annual[base_year])
    if index is None:
        return None
    return {"index": index, "base_year": base_year, "price": annual[year]}


def index_for(neighborhood_id, year):
    """
    The derived index record of a neighborhood and year (see index_from_prices
    plus the region name); None without a region mapping or NVM prices, so the
    stored index is kept.
    """
    region = region_of_neighborhood(neighborhood_id)
    if region is None:
        return None
    derived = index_from_prices(annual_prices(region), year)
    if derived is None:
        return None
    return {**derived, "region": region}
