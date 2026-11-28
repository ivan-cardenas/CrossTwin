"""
Database side of the modelled price per m2 of a dwelling (the equation is
housing/calculations/chain.py::modelled_price_per_sqm; the fit is price_model.py).

The price is one equation for the whole city (the active housing.PriceModel.prediction) applied to the
variables of each dwelling:
* the building's stored distances to the nearest amenities of each category (builtup.Accessibility), turned
  into the value of each term of the fit (chain.term_values);
* the controls: the building's construction year and energy label (builtup.Building), the multi-family and
  rental share of its PC6 postcode area (CBS), the socio-economic status of the neighborhood under that area,
  and the distance from the dwelling to the municipal centre;
* its municipality (housing.PostcodePrice.city, found by the BAG postcode of the dwelling).
The CBS WOZ value per m2 of the PC6 area (newest statistics year available) is what the equation was
calibrated on, not an input of the price; it is read here for the dashboard's comparison only.

reprice() writes the result onto builtup.Property with bulk_update (no signals, so no
loop with the receivers); rows without the inputs keep their stored value.

DAG edges: Accessibility -> Property
"""
import logging
import math
from collections import Counter

from core.cache import bump_layer_version

from . import chain

logger = logging.getLogger(__name__)

DWELLING = "Residential function"   # BAG woonfunctie label in Property.usageFunction
BUILDING_CHUNK = 2000               # buildings per round of reprice()


def normalise(postal_code):
    """A BAG postcode as a PC6 code: no spaces, upper case ('' when missing)."""
    return (postal_code or "").replace(" ", "").upper()


def postcode_inputs(codes):
    """
    {code: {"woz", "year", "city", "neighborhood", "apartmentShare", "rentalShare"}} from the newest
    housing.PostcodePrice row of each PC6 code that has a WOZ value per m2.
    """
    from housing.models import PostcodePrice

    codes = list(codes)
    if not codes:
        return {}
    rows = (PostcodePrice.objects.filter(postcode6__in=codes, woz_per_sqm__isnull=False)
            .order_by("postcode6", "-year").distinct("postcode6")
            .values("postcode6", "year", "woz_per_sqm", "city_id", "neighborhood_id", "multiFamilyShare_pct", "rentalShare_pct"))
    return {r["postcode6"]: {
        "woz": r["woz_per_sqm"], "year": r["year"], "city": r["city_id"], "neighborhood": r["neighborhood_id"],
        "apartmentShare": None if r["multiFamilyShare_pct"] is None else r["multiFamilyShare_pct"] / 100.0,
        "rentalShare": None if r["rentalShare_pct"] is None else r["rentalShare_pct"] / 100.0} for r in rows}


def dwelling_inputs(dwellings):
    """
    [(property pk, building id, inputs, (x, y))] for the dwellings whose PC6 area is stored: `dwellings` is a
    list of (pk, building_id, postalCode, x, y). The inputs are the row of the dwelling's PC6 area.
    """
    by_code = postcode_inputs({normalise(pc) for _, _, pc, _, _ in dwellings if pc})
    return [(pk, building, by_code[normalise(pc)], (x, y)) for pk, building, pc, x, y in dwellings if normalise(pc) in by_code]


def dwelling_controls(inputs, point, building, centres, ses):
    """
    {control: value or None} of one dwelling. `inputs` is its PC6 row, `point` its (x, y), `building` the
    (constructionYear, energyLabel) of its building, `centres` {city: (x, y)} and `ses` {neighborhood: status}.
    A value the data lacks is None; chain.log_price then uses the fit's mean of the control.
    """
    from .price_model import CONSTRUCTION_YEAR_RANGE, ENERGY_ORDINAL

    year, label = building
    lo, hi = CONSTRUCTION_YEAR_RANGE
    centre = centres.get(inputs["city"])
    return {
        "constructionYear": year if year is not None and lo <= year <= hi else None,
        "energyLabel": ENERGY_ORDINAL.get(label),
        "apartmentShare": inputs["apartmentShare"], "rentalShare": inputs["rentalShare"],
        "ses": ses.get(inputs["neighborhood"]),
        "distCentre_km": None if centre is None else math.hypot(point[0] - centre[0], point[1] - centre[1]) / 1000.0,
    }


def method_label(model):
    """The string stored in Property.priceMethod: the method, the fit and the reading."""
    return (f"{chain.PRICE_METHOD}; model {model.pk} ({model.form}, {model.spatialModel}, {len(model.betas)} terms, "
            f"WOZ {model.wozYear}); {chain.PRICE_LABEL}")[:255]


def building_terms(building_ids, terms):
    """{building_id: {term: value 0-100}} of the wanted terms, from the stored distances to the amenities."""
    from builtup.models import Accessibility

    wanted = set(terms)
    modes = {chain.split_term(t)[0] for t in wanted}
    values = {}
    for building_id, mode, distances in (Accessibility.objects.filter(building_id__in=building_ids, mode__in=modes)
                                         .values_list("building_id", "mode", "distances")):
        values.setdefault(building_id, {}).update(
            {t: v for t, v in chain.term_values(distances, mode).items() if t in wanted})
    return values


def city_centres(city_ids):
    """{city_id: (x, y)} of the municipal centroids (the distance control of the fit is measured to them)."""
    from administrative.models import City

    return {pk: (geom.centroid.x, geom.centroid.y)
            for pk, geom in City.objects.filter(pk__in=list(city_ids)).values_list("pk", "geom") if geom}


def reprice(building_ids=None, model=None):
    """
    Recompute Property.modelledPrice_EUR_per_sqm (and priceModel, priceMethod) of the
    dwellings in `building_ids` (all dwellings when None) with the active fit. Returns
    the number of properties written. A dwelling the equation cannot be applied to (no postcode area, no
    stored accessibility, a municipality the fit has no effect for) keeps its stored value.

    DAG edge: Accessibility -> Property
    """
    from builtup.models import Building, Property

    from housing.models import NeighborhoodSocialProfile, PriceModel, ResidentialProperty

    model = model or PriceModel.active()
    prediction = model.predictor if model is not None else {}
    if not prediction.get("terms"):
        return 0
    if building_ids is None:
        building_ids = list(Property.objects.filter(usageFunction__contains=[DWELLING])
                            .values_list("building_id", flat=True).distinct())
    building_ids = sorted(set(building_ids))
    written = 0
    label = method_label(model)
    for start in range(0, len(building_ids), BUILDING_CHUNK):
        chunk = building_ids[start:start + BUILDING_CHUNK]
        dwellings = [(pk, building, pc, geom.x, geom.y) for pk, building, pc, geom in
                     Property.objects.filter(usageFunction__contains=[DWELLING], building_id__in=chunk, geom__isnull=False)
                     .values_list("pk", "building_id", "postalCode", "geom")]
        if not dwellings:
            continue
        priced = dwelling_inputs(dwellings)
        centres = city_centres({data["city"] for _, _, data, _ in priced if data["city"]})
        hoods = {data["neighborhood"] for _, _, data, _ in priced if data["neighborhood"]}
        ses = dict(NeighborhoodSocialProfile.objects.filter(neighborhood_id__in=hoods)
                   .values_list("neighborhood_id", "socioEconomicStatus"))
        attrs = {b: (year, energy) for b, year, energy in
                 Building.objects.filter(pk__in=chunk).values_list("pk", "constructionYear", "energyLabel")}
        values = building_terms(chunk, prediction["terms"])
        updates = []
        for pk, building_id, data, point in priced:
            controls = dwelling_controls(data, point, attrs.get(building_id, (None, None)), centres, ses)
            price = chain.modelled_price_per_sqm(prediction, values.get(building_id, {}), controls, data["city"])
            if price is None:
                continue
            updates.append(Property(pk=pk, modelledPrice_EUR_per_sqm=round(price, 2), priceModel=model, priceMethod=label))
        if updates:
            Property.objects.bulk_update(updates, ["modelledPrice_EUR_per_sqm", "priceModel", "priceMethod"], batch_size=1000)
            written += len(updates)
    if written:
        bump_layer_version(Property, ResidentialProperty)
    return written


def unit_summary(neighborhood_ids, postcode_prefix=None):
    """
    The dashboard's inputs for the dwellings of some neighborhoods (or, with `postcode_prefix`, a PC4 or PC6
    code: the dwellings with that BAG postcode): ({"stored_mean", "level_mean", "priced"}, active fit).
    `stored_mean` is the mean of Property.modelledPrice_EUR_per_sqm over the dwellings that have one,
    `level_mean` the mean CBS WOZ value per m2 of the same dwellings (what the model was calibrated on).
    """
    from django.db.models import Avg, Count, Value
    from django.db.models.functions import Replace, Upper

    from builtup.models import Property

    from housing.models import PriceModel

    model = PriceModel.active()
    dwellings = Property.objects.filter(usageFunction__contains=[DWELLING], modelledPrice_EUR_per_sqm__isnull=False)
    if postcode_prefix:
        dwellings = (dwellings.annotate(pc=Upper(Replace("postalCode", Value(" "), Value(""))))
                     .filter(pc__startswith=normalise(postcode_prefix)))
    else:
        dwellings = dwellings.filter(building__neighborhood_id__in=list(neighborhood_ids))
    from django.db.models import F, FloatField, Q
    from django.db.models.functions import Coalesce

    # the modelled value of a dwelling: its modelled price per m2 x its area (living area, else gross area)
    stored = dwellings.aggregate(
        mean=Avg("modelledPrice_EUR_per_sqm"), n=Count("pk"),
        value=Avg(F("modelledPrice_EUR_per_sqm") * Coalesce("livingArea", "grossArea"), output_field=FloatField(),
                  filter=Q(livingArea__gt=0) | Q(grossArea__gt=0)))
    if not stored["n"]:
        return {"stored_mean": None, "value_mean": None, "level_mean": None, "priced": 0}, model
    per_code = Counter()
    for code, count in dwellings.order_by().values("postalCode").annotate(n=Count("pk")).values_list("postalCode", "n"):
        per_code[normalise(code)] += count
    inputs = postcode_inputs(per_code)
    counted = sum(n for c, n in per_code.items() if c in inputs)
    weighted = sum(inputs[c]["woz"] * n for c, n in per_code.items() if c in inputs)
    return {"stored_mean": stored["mean"], "value_mean": stored["value"],
            "level_mean": weighted / counted if counted else None,
            "priced": stored["n"]}, model


def mean_price(summary, factor=1.0):
    """
    {"price", "level", "priced"}: the dwelling-weighted mean modelled price and the mean CBS WOZ value (the same
    dwellings), EUR/m2, with `factor` (the house price index of the scenario year, chain.hpi_price_factor) applied to both.
    With factor 1 the price equals the stored mean.
    """
    if not summary.get("priced") or summary.get("stored_mean") is None or not summary.get("level_mean"):
        return {"price": None, "level": None, "priced": 0}
    return {"price": summary["stored_mean"] * factor, "level": summary["level_mean"] * factor, "priced": summary["priced"]}
