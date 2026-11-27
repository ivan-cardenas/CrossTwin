"""
Accessibility -> modelled price (Phase 4 of docs/ACCESSIBILITY_PLAN.md): the equation over the amenity
categories, the hedonic fit with its redundancy and influence screening, the edge Accessibility -> Property,
the dashboard parity and the staff endpoints.
"""
import datetime
import math
from unittest import mock

import numpy as np
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.test import Client, SimpleTestCase, TestCase
from django.urls import reverse
from shapely.geometry import box

from administrative.models import Postcode6
from builtup.calculations import chain as access_chain
from builtup.models import Accessibility, Building, Property
from builtup.signals import accessibility_changed
from watersupply.tests.factories import make_city, make_neighborhood, make_polygon

from housing import views
from housing.calculations import chain, postcode_woz, price_model, property_price
from housing.models import NeighborhoodSocialProfile, PostcodePrice, PriceModel, WOZValue

SRID = settings.COORDINATE_SYSTEM
DWELLING = ["Residential function"]
SUPERMARKET, STATION = "walk:supermarket", "bike:train_station"
BETAS = {SUPERMARKET: 0.004, STATION: 0.002}
# the city-wide equation of a fit: ln price = a + sum beta A + gamma z + mu_c, times the smearing factor
PREDICTION = {"form": "linear", "intercept": 11.0, "terms": BETAS, "controls": {"constructionYear": -0.002, "ses": 0.1},
              "control_means": {"constructionYear": 1960.0, "ses": 0.0}, "cities": {"153": 0.0, "503": 0.05}, "smearing": 1.02}


def value_at(category, metres, mode="walk"):
    """The 0-100 value of a term of a building whose nearest amenity of the category is `metres` away."""
    return chain.term_values({category: [metres]}, mode)[chain.term_key(mode, category)]


# ── the equation ─────────────────────────────────────────────────────

class PriceEquationTests(SimpleTestCase):
    """One equation for the whole city: the same intercept, betas and control coefficients for every dwelling."""

    def price(self, **kwargs):
        args = dict(prediction=PREDICTION, access={SUPERMARKET: 70.0, STATION: 50.0},
                    controls={"constructionYear": 1970.0, "ses": 0.5}, city=153, form="linear")
        args.update(kwargs)
        return chain.modelled_price_per_sqm(**args)

    def test_linear_price_pinned(self):
        expected = 1.02 * math.exp(11.0 + 0.004 * 70 + 0.002 * 50 - 0.002 * 1970 + 0.1 * 0.5)
        self.assertAlmostEqual(self.price(), expected)
        self.assertAlmostEqual(self.price(), 1825.85, places=2)

    def test_log1p_price_pinned(self):
        prediction = {**PREDICTION, "terms": {SUPERMARKET: 0.4, STATION: 0.2}, "intercept": 2.0}
        expected = 1.02 * math.exp(2.0 + 0.4 * math.log(71.0) + 0.2 * math.log(51.0) - 0.002 * 1970 + 0.05)
        self.assertAlmostEqual(self.price(prediction=prediction, form="log1p"), expected)

    def test_the_form_comes_from_the_prediction_when_not_given(self):
        log_form = {**PREDICTION, "form": "log1p", "terms": {SUPERMARKET: 0.4, STATION: 0.2}}
        self.assertAlmostEqual(self.price(prediction=log_form, form=None), self.price(prediction=log_form, form="log1p"))

    def test_the_municipality_effect_is_the_only_difference_between_two_municipalities(self):
        self.assertAlmostEqual(self.price(city=503) / self.price(city=153), math.exp(0.05))

    def test_a_better_access_raises_the_price_by_the_beta_everywhere(self):
        for city in (153, 503):
            base = self.price(city=city)
            better = self.price(city=city, access={SUPERMARKET: 80.0, STATION: 50.0})
            self.assertAlmostEqual(better / base, math.exp(0.004 * 10))

    def test_the_woz_level_is_not_an_input(self):
        import inspect

        self.assertNotIn("woz", " ".join(inspect.signature(chain.modelled_price_per_sqm).parameters))

    def test_the_market_what_if_scales_the_price(self):
        self.assertAlmostEqual(self.price(growth_pct=10.0), self.price() * 1.1)
        self.assertAlmostEqual(chain.market_growth_factor(-30.0), 0.7)

    def test_a_control_the_dwelling_lacks_is_the_mean_of_the_fit(self):
        lacking = self.price(controls={"constructionYear": None, "ses": 0.5})
        at_mean = self.price(controls={"constructionYear": 1960.0, "ses": 0.5})
        self.assertAlmostEqual(lacking, at_mean)
        self.assertIsNone(self.price(prediction={**PREDICTION, "control_means": {}}, controls={}))

    def test_a_fit_on_one_municipality_has_no_municipality_effect(self):
        prediction = {**PREDICTION, "cities": {}}
        self.assertAlmostEqual(self.price(prediction=prediction, city=None), self.price(prediction=prediction, city=999))

    def test_a_municipality_the_fit_has_no_effect_for_gives_none(self):
        self.assertIsNone(self.price(city=999))
        self.assertIsNone(self.price(city=None))

    def test_missing_inputs_give_none(self):
        self.assertIsNone(self.price(access={}))                          # no stored accessibility: the stored price is kept
        self.assertIsNone(self.price(access={SUPERMARKET: 70.0}))         # a term of the fit without a value
        self.assertIsNone(self.price(prediction={**PREDICTION, "intercept": None}))
        self.assertIsNone(self.price(prediction={}))

    def test_unknown_form_is_an_error(self):
        with self.assertRaises(ValueError):
            chain.access_transform(50.0, "cubic")

    def test_there_is_no_woz_anchor_valuation_shift_or_nvm_factor(self):
        for name in ("woz_valuation_year", "valuation_quarter", "market_factor", "price_index", "annual_price_per_sqm",
                     "BETA_MULT_MAX", "ACCESS_DELTA_MAX", "MAX_ABS_LOG_EFFECT", "access_log_effect"):
            self.assertFalse(hasattr(chain, name), name)


class TermTests(SimpleTestCase):
    def test_a_term_is_a_mode_and_a_category(self):
        self.assertEqual(chain.term_key("walk", "train_station"), "walk:train_station")
        self.assertEqual(chain.split_term("bike:tram_metro_stop"), ("bike", "tram_metro_stop"))

    def test_candidates_are_every_category_on_both_modes(self):
        terms = chain.candidate_terms()
        self.assertEqual(len(terms), 2 * len(access_chain.CATEGORIES))
        self.assertEqual(len(set(terms)), len(terms))
        for category in ("supermarket", "train_station", "bus_stop", "park"):
            self.assertIn(chain.term_key("walk", category), terms)
            self.assertIn(chain.term_key("bike", category), terms)

    def test_term_values_follow_the_distance_decay_of_the_score(self):
        values = chain.term_values({"supermarket": [400.0], "shop": [400.0], "bus_stop": [1600.0]}, "walk")
        self.assertEqual(len(values), len(access_chain.CATEGORIES))
        self.assertAlmostEqual(values["walk:supermarket"], 100.0)          # inside the full-value distance
        self.assertAlmostEqual(values["walk:shop"], 100 * 1.0 / 1.75)      # only the nearest of three weighted shops
        self.assertAlmostEqual(values["walk:bus_stop"], 100 * 0.05 / 1.5, places=3)   # at the cut-off, 1st of 2 stops
        self.assertEqual(values["walk:train_station"], 0.0)                # nothing reachable
        self.assertEqual(chain.term_values(None, "bike")["bike:park"], 0.0)

    def test_the_score_is_the_weighted_mean_of_the_terms(self):
        distances = {"supermarket": [400.0], "school": [900.0, 1500.0], "park": [200.0]}
        values = chain.term_values(distances, "walk")
        weight_sum = sum(w for w, _ in access_chain.CATEGORIES.values())
        score = sum(access_chain.CATEGORIES[c][0] * values[chain.term_key("walk", c)] for c in access_chain.CATEGORIES) / weight_sum
        self.assertAlmostEqual(score, access_chain.accessibility_score(distances, "walk"))


# ── the fit, on synthetic areas ──────────────────────────────────────

def synthetic(n=10, seed=1, noise=0.02, form="linear", spatial=0.0, cities=True, collinear=False):
    """
    An n x n grid of 100 m square areas; ln price = known betas on two terms + controls + noise (+ a smooth field).
    The other candidate terms are made to be screened out: a near copy of the supermarket term (redundant), a pure
    noise term (no influence), a constant one (no variation); `collinear` adds a term that is a blend of the two real ones.
    """
    rng = np.random.default_rng(seed)
    field = np.zeros((n, n))
    if spatial:
        e = rng.normal(0, 1, (n, n))
        for _ in range(4):
            e = (e + np.roll(e, 1, 0) + np.roll(e, -1, 0) + np.roll(e, 1, 1) + np.roll(e, -1, 1)) / 5
        field = spatial * e / e.std()
    transform = np.log1p if form == "log1p" else (lambda v: v)
    b_super, b_station = (0.4, 0.2) if form == "log1p" else (0.004, 0.002)
    rows = []
    for i in range(n):
        for j in range(n):
            supermarket, station = 20 + 7 * i + rng.normal(0, 3), 30 + 5 * j + rng.normal(0, 3)
            terms = {SUPERMARKET: supermarket, STATION: station,
                     "walk:shop": supermarket + rng.normal(0, 6),
                     "walk:library": rng.uniform(0, 100),
                     "walk:park": 0.0}
            if collinear:
                terms["bike:bus_stop"] = 0.5 * supermarket + 0.5 * station + rng.normal(0, 0.5)
            year, share, label = 1950 + rng.normal(0, 20), rng.uniform(0, 1), rng.uniform(3, 8)
            ses, dist = rng.normal(0, 1), rng.uniform(0, 5)
            rows.append({
                "id": f"{i}-{j}", "city": (i // 4) * 2 + j // 4 if cities else 1,
                "terms": terms, "weight": 100 + int(rng.integers(0, 50)),
                "x": i * 100 + 50, "y": j * 100 + 50, "geom": box(i * 100, j * 100, i * 100 + 100, j * 100 + 100),
                "constructionYear": year, "apartmentShare": share, "energyLabel": label, "ses": ses, "distCentre_km": dist,
                "lnPrice": 8 + b_super * transform(supermarket) + b_station * transform(station) - 0.002 * (year - 1950)
                           + 0.1 * ses + field[i, j] + rng.normal(0, noise)})
    return rows


FAST = dict(permutations=99)


class HedonicFitTests(SimpleTestCase):
    def test_the_fit_recovers_known_betas(self):
        fit = price_model.fit_hedonic(synthetic(), **FAST)
        self.assertEqual(fit["form"], "linear")
        self.assertAlmostEqual(fit["termBetas"][SUPERMARKET], 0.004, delta=0.0008)
        self.assertAlmostEqual(fit["termBetas"][STATION], 0.002, delta=0.0008)
        self.assertGreater(fit["r2"], 0.9)
        self.assertEqual(fit["n"], 100)
        self.assertEqual(fit["design"], "cross_section")
        self.assertIn(chain.PRICE_LABEL, fit["method"])
        self.assertIn("2 of 5 terms", fit["method"])

    def test_only_the_screened_terms_get_a_beta(self):
        fit = price_model.fit_hedonic(synthetic(), **FAST)
        self.assertEqual(sorted(fit["termBetas"]), sorted([SUPERMARKET, STATION]))
        self.assertEqual(sorted(fit["spec"]["terms"]), sorted([SUPERMARKET, STATION]))
        self.assertEqual(fit["screening"]["candidates"], 5)
        self.assertEqual(fit["screening"]["kept"], 2)

    def test_a_near_copy_of_a_term_is_redundant(self):
        report = price_model.fit_hedonic(synthetic(), **FAST)["screening"]["terms"]
        self.assertEqual(report["walk:shop"]["status"], "dropped")
        self.assertIn("redundant with walk:supermarket", report["walk:shop"]["reason"])
        self.assertEqual(report["walk:shop"]["redundant_with"], SUPERMARKET)
        self.assertEqual(report[SUPERMARKET]["status"], "kept")     # the one that tracks the price more is the one kept

    def test_a_constant_term_has_too_little_variation(self):
        report = price_model.fit_hedonic(synthetic(), **FAST)["screening"]["terms"]
        self.assertEqual(report["walk:park"]["status"], "dropped")
        self.assertIn("too little variation", report["walk:park"]["reason"])

    def test_a_term_unrelated_to_the_price_has_too_little_influence(self):
        report = price_model.fit_hedonic(synthetic(), **FAST)["screening"]["terms"]
        self.assertEqual(report["walk:library"]["status"], "dropped")
        self.assertIn("too little influence", report["walk:library"]["reason"])
        self.assertRegex(report["walk:library"]["reason"], "not significant|negligible effect")

    def test_a_negligible_effect_is_dropped_even_when_significant(self):
        with mock.patch.object(price_model, "MIN_EFFECT_PER_SD", 0.04):
            fit = price_model.fit_hedonic(synthetic(), **FAST)
        report = fit["screening"]["terms"]
        self.assertEqual(sorted(fit["termBetas"]), [SUPERMARKET])      # 0.002 x sd 15 = 3 % per sd, under 4 %
        self.assertIn("negligible effect", report[STATION]["reason"])
        self.assertLess(report[STATION]["p"], price_model.INFLUENCE_P)  # significant, and still dropped

    def test_collinear_terms_are_dropped_until_the_vif_is_acceptable(self):
        fit = price_model.fit_hedonic(synthetic(collinear=True), **FAST)
        report = fit["screening"]["terms"]
        # the bus-stop term is a blend of the supermarket and station terms (|r| < 0.9 with each, VIF huge); the shop
        # term is a copy of the supermarket one: two independent pieces of information are left, so two terms are kept
        group = [SUPERMARKET, "walk:shop", STATION, "bike:bus_stop"]
        self.assertEqual(sum(report[t]["status"] == "kept" for t in group), 2)
        self.assertTrue(any("collinear" in report[t]["reason"] for t in group))
        for term in fit["termBetas"]:
            self.assertLessEqual(report[term]["vif"], price_model.VIF_MAX)

    def test_the_kept_terms_report_their_statistics(self):
        report = price_model.fit_hedonic(synthetic(), **FAST)["screening"]["terms"][SUPERMARKET]
        for key in ("beta", "beta_no_controls", "p", "effect_per_sd", "vif", "corr_price", "sd"):
            self.assertIsNotNone(report[key], key)
        self.assertAlmostEqual(report["effect_per_sd"], abs(report["coef"]) * report["sd"], places=4)

    def test_no_detectable_category_is_a_clear_error(self):
        rows = synthetic()
        for row in rows:
            row["lnPrice"] = 8.0                               # the price depends on nothing
        with self.assertRaisesRegex(price_model.PriceModelError, "No amenity category"):
            price_model.fit_hedonic(rows, **FAST)

    def test_variance_inflation_pinned(self):
        import pandas as pd

        rng = np.random.default_rng(3)
        a = rng.normal(0, 1, 400)
        frame = pd.DataFrame({"weight": 1.0, "a__x": a, "b__y": rng.normal(0, 1, 400)})
        frame["c__z"] = frame["a__x"] + 0.1 * rng.normal(0, 1, 400)       # r2 with a ~ 0.99
        vif = price_model.variance_inflation(frame, ["a:x", "b:y", "c:z"])
        self.assertLess(vif["b:y"], 1.1)
        self.assertGreater(vif["a:x"], 50)
        self.assertEqual(price_model.variance_inflation(frame, ["a:x"]), {"a:x": 1.0})

    def test_the_fit_stores_one_equation_for_the_whole_city(self):
        fit = price_model.fit_hedonic(synthetic(), **FAST)
        prediction = fit["prediction"]
        self.assertEqual(prediction["terms"], fit["termBetas"])
        self.assertEqual(sorted(prediction["controls"]), sorted(fit["spec"]["controls"]))
        self.assertEqual(sorted(prediction["control_means"]), sorted(fit["spec"]["controls"]))
        self.assertEqual(prediction["form"], fit["form"])
        self.assertEqual(len(prediction["cities"]), len({row["city"] for row in synthetic()}))
        self.assertTrue(0.9 < prediction["smearing"] < 1.1)

    def test_the_equation_reproduces_the_calibration_data(self):
        rows = synthetic()
        fit = price_model.fit_hedonic(rows, **FAST)
        prediction, total, observed, weights = fit["prediction"], 0.0, 0.0, 0.0
        for row in rows:
            price = chain.modelled_price_per_sqm(prediction, row["terms"], row, row["city"])
            self.assertIsNotNone(price)
            total += row["weight"] * price
            observed += row["weight"] * math.exp(row["lnPrice"])
            weights += row["weight"]
        self.assertAlmostEqual(total / observed, 1.0, delta=0.02)                  # the level of the WOZ values is reproduced
        # and the areas are priced by the same coefficients: the correlation with the observed values is high
        predicted = [chain.modelled_price_per_sqm(prediction, r["terms"], r, r["city"]) for r in rows]
        self.assertGreater(np.corrcoef(predicted, [math.exp(r["lnPrice"]) for r in rows])[0, 1], 0.95)

    def test_a_fit_on_one_municipality_has_no_municipality_effects_in_the_equation(self):
        prediction = price_model.fit_hedonic(synthetic(cities=False), **FAST)["prediction"]
        self.assertEqual(prediction["cities"], {})

    def test_an_exploratory_fit_stores_an_equation_too(self):
        prediction = price_model.fit_hedonic(synthetic(n=3, cities=False), use_controls=False, exploratory=True, **FAST)["prediction"]
        self.assertEqual(prediction["controls"], {})
        self.assertIn("intercept", prediction)

    def test_without_controls_is_reported_beside(self):
        fit = price_model.fit_hedonic(synthetic(), **FAST)
        self.assertIsNotNone(fit["screening"]["terms"][SUPERMARKET]["beta_no_controls"])
        self.assertIn(SUPERMARKET, fit["coefficientsNoControls"])
        self.assertEqual(sorted(fit["spec"]["controls"]), sorted(c for c in price_model.CONTROLS if c != "rentalShare"))   # the rows carry no rental share
        self.assertEqual(fit["spec"]["errors"], "clustered by municipality")

    def test_a_form_that_is_logarithmic_is_picked(self):
        fit = price_model.fit_hedonic(synthetic(form="log1p", noise=0.005), **FAST)
        self.assertEqual(fit["form"], "log1p")
        self.assertAlmostEqual(fit["termBetas"][SUPERMARKET], 0.4, delta=0.08)
        comparison = fit["formComparison"]
        self.assertGreater(comparison["log1p"]["cv_r2"], comparison["linear"]["cv_r2"])
        self.assertLess(comparison["log1p"]["aic"], comparison["linear"]["aic"])

    def test_noise_without_spatial_structure_passes_the_diagnostic(self):
        fit = price_model.fit_hedonic(synthetic(noise=0.05), **FAST)
        self.assertGreater(fit["moransP"], price_model.MORAN_ALPHA)
        self.assertEqual(fit["spatialModel"], "ols")
        self.assertTrue(fit["diagnosticPassed"])
        self.assertIsNone(fit["spatialLambda"])

    def test_an_injected_spatial_error_is_flagged_and_a_spatial_model_fitted(self):
        fit = price_model.fit_hedonic(synthetic(spatial=0.08, noise=0.02), **FAST)
        self.assertLess(fit["moransP"], price_model.MORAN_ALPHA)
        self.assertGreater(fit["moransI"], 0.1)
        self.assertIsNotNone(fit["spatialLambda"])
        self.assertIsNotNone(fit["moransISem"])
        self.assertEqual(fit["spatialModel"], "sem")
        self.assertTrue(0.0 < fit["r2"] < 1.0)                                  # centered R2, not statsmodels' uncentered ~1
        self.assertLess(abs(fit["r2"] - fit["spec"]["r2_ols"]), 0.4)
        self.assertLess(abs(fit["moransISem"]), abs(fit["moransI"]))
        self.assertIn(SUPERMARKET, fit["termBetas"])

    def test_the_fit_is_deterministic(self):
        first = price_model.fit_hedonic(synthetic(spatial=0.08), **FAST)
        second = price_model.fit_hedonic(synthetic(spatial=0.08), **FAST)
        self.assertEqual((first["moransI"], first["moransP"], first["termBetas"], first["screening"]),
                         (second["moransI"], second["moransP"], second["termBetas"], second["screening"]))

    def test_the_screening_report_is_json_safe(self):
        import json

        fit = price_model.fit_hedonic(synthetic(collinear=True), **FAST)
        json.dumps(fit["screening"], allow_nan=False)
        json.dumps(fit["termBetas"], allow_nan=False)

    def test_one_municipality_clusters_by_the_cluster_key_when_the_rows_carry_one(self):
        rows = synthetic(cities=False)
        for row in rows:
            row["cluster"] = f"P{int(row['x'] // 200)}"
        fit = price_model.fit_hedonic(rows, **FAST)
        self.assertEqual(fit["spec"]["errors"], "clustered by neighborhood")
        self.assertEqual(fit["spec"]["clusters"], 5)
        self.assertFalse(fit["spec"]["fixed_effects"])
        self.assertAlmostEqual(fit["termBetas"][SUPERMARKET], 0.004, delta=0.001)

    def test_a_control_that_is_mostly_missing_is_dropped_not_imputed(self):
        rows = synthetic()
        for row in rows[:30]:
            row["energyLabel"] = None
        fit = price_model.fit_hedonic(rows, **FAST)
        self.assertIn("energyLabel", fit["spec"]["dropped_controls"])
        self.assertEqual(fit["n"], 100)

    def test_one_municipality_uses_robust_errors_and_no_fixed_effects(self):
        fit = price_model.fit_hedonic(synthetic(cities=False), **FAST)
        self.assertEqual(fit["spec"]["errors"], "HC1 (one municipality)")
        self.assertFalse(fit["spec"]["fixed_effects"])
        self.assertAlmostEqual(fit["termBetas"][SUPERMARKET], 0.004, delta=0.001)

    def test_exploratory_fit_without_controls_runs_on_a_small_area(self):
        rows = synthetic(n=3, cities=False)
        with self.assertRaisesRegex(price_model.PriceModelError, "at least 30"):
            price_model.fit_hedonic(rows, **FAST)
        fit = price_model.fit_hedonic(rows, use_controls=False, exploratory=True, **FAST)
        self.assertEqual(fit["n"], 9)
        self.assertEqual(fit["spec"]["controls"], [])
        self.assertTrue(fit["spec"]["exploratory"])
        self.assertIn("exploratory, not interpretable", fit["method"])
        self.assertIn(chain.PRICE_LABEL, fit["method"])
        with self.assertRaisesRegex(price_model.PriceModelError, "at least 8"):
            price_model.fit_hedonic(synthetic(n=2, cities=False), use_controls=False, exploratory=True, **FAST)

    def test_too_few_areas_is_a_clear_error(self):
        with self.assertRaisesRegex(price_model.PriceModelError, "at least 30"):
            price_model.fit_hedonic(synthetic(n=4), **FAST)
        with self.assertRaises(price_model.PriceModelError):
            price_model.fit_hedonic([], **FAST)

    def test_too_few_areas_for_the_parameters_is_a_clear_error(self):
        with mock.patch.object(price_model, "MIN_OBS_PER_PARAMETER", 50):
            with self.assertRaisesRegex(price_model.PriceModelError, "per parameter"):
                price_model.fit_hedonic(synthetic(), **FAST)

    def test_rows_without_any_term_are_a_clear_error(self):
        rows = synthetic()
        for row in rows:
            row["terms"] = {}
        with self.assertRaisesRegex(price_model.PriceModelError, "per amenity category"):
            price_model.fit_hedonic(rows, **FAST)

    def test_queen_contiguity_includes_corners(self):
        neighbors = price_model.queen_neighbors([box(0, 0, 1, 1), box(1, 1, 2, 2), box(5, 5, 6, 6)])
        self.assertEqual(neighbors, {0: [1], 1: [0], 2: []})


# ── the edge, the stored value and the dashboard ─────────────────────

class PropertyPriceTests(TestCase):
    """DAG edge: Accessibility -> Property. One equation for the city, applied to each dwelling's own variables."""

    def setUp(self):
        self.city = make_city(id=503, cityName="Delft")
        self.hood = make_neighborhood(id="BU05030101", city=self.city)
        self.building = Building.objects.create(id=1, buildingType="residential", constructionYear=1970,
                                                geom=make_polygon(257000.0, 470000.0, 30))
        self.other = Building.objects.create(id=2, buildingType="residential", constructionYear=1970,
                                             geom=make_polygon(257200.0, 470000.0, 30))
        self.home = self._dwelling(257000.0, "7511 AA")
        self.neighbour = self._dwelling(257200.0, "7511AB")
        for code, woz in (("7511AA", 5000.0), ("7511AB", 3000.0)):    # the WOZ values differ, the variables do not
            PostcodePrice.objects.create(postcode6=code, year=2024, avgWOZ_EUR=woz * 90, meanArea_sqm=90.0, dwellings=10,
                                         city=self.city, neighborhood=self.hood, baselineAccessWalk=60.0, baselineAccessBike=50.0,
                                         baselineCategories={SUPERMARKET: 60.0})
        self.prediction = {"form": "linear", "intercept": 7.0, "terms": {SUPERMARKET: 0.004}, "controls": {"constructionYear": -0.002},
                           "control_means": {"constructionYear": 1960.0}, "cities": {"503": 0.0}, "smearing": 1.0}
        self.model = PriceModel.objects.create(n=100, wozYear=2024, form="linear", termBetas=self.prediction["terms"],
                                               prediction=self.prediction, isActive=True, method=chain.PRICE_METHOD)

    def _dwelling(self, x, postal_code):
        return Property.objects.create(name="p", grossArea=90, usageFunction=DWELLING, unitaryPrice_EUR_per_sqm=4000.0,
                                       postalCode=postal_code, geom=Point(x, 470000.0, srid=SRID))

    def _supermarket(self, building, metres):
        """The nearest supermarket of the building is `metres` away on the walk network."""
        Accessibility.objects.update_or_create(
            building=building, mode="walk",
            defaults=dict(score=50.0, method="m1", distances={"supermarket": [metres]}, geom=Point(257000.0, 470000.0, srid=SRID)))

    def _send(self, *buildings, mode="walk"):
        accessibility_changed.send(sender=Building, mode=mode, building_ids=[b.pk for b in buildings])

    def price(self, prop):
        prop.refresh_from_db()
        return prop.modelledPrice_EUR_per_sqm

    def expected(self, metres, year=1970):
        return math.exp(7.0 + 0.004 * value_at("supermarket", metres) - 0.002 * year)

    def test_an_accessibility_change_reprices_the_dwellings_of_that_building_only(self):
        self._supermarket(self.building, 400.0)
        self._supermarket(self.other, 400.0)
        self._send(self.building)
        self.assertAlmostEqual(self.price(self.home), self.expected(400.0), places=2)
        self.assertIsNone(self.price(self.neighbour))

    def test_the_woz_value_is_calibration_not_an_input(self):
        self._supermarket(self.building, 400.0)
        self._supermarket(self.other, 400.0)
        property_price.reprice()
        self.assertAlmostEqual(self.price(self.home), self.price(self.neighbour))     # WOZ 5000 against 3000 per m2
        PostcodePrice.objects.filter(postcode6="7511AA").update(avgWOZ_EUR=999_000.0)
        property_price.reprice()
        self.assertAlmostEqual(self.price(self.home), self.expected(400.0), places=2)

    def test_a_new_amenity_nearby_raises_the_price_and_the_label_and_fit_are_stored(self):
        self._supermarket(self.building, 1000.0)
        self._send(self.building)
        before = self.price(self.home)
        self._supermarket(self.building, 150.0)      # a supermarket was added next door
        self._send(self.building)
        self.assertAlmostEqual(self.price(self.home) / before, math.exp(0.004 * (100.0 - value_at("supermarket", 1000.0))), places=2)
        self.home.refresh_from_db()
        self.assertEqual(self.home.priceModel_id, self.model.pk)
        self.assertIn(chain.PRICE_LABEL, self.home.priceMethod)
        self.assertIn("WOZ 2024", self.home.priceMethod)
        self.assertIn("1 terms", self.home.priceMethod)
        self.assertEqual(self.home.unitaryPrice_EUR_per_sqm, 4000.0)   # the observed price is untouched

    def test_each_category_is_priced_with_its_own_beta(self):
        prediction = {**self.prediction, "terms": {SUPERMARKET: 0.004, "walk:train_station": -0.003}}
        PriceModel.objects.filter(pk=self.model.pk).update(termBetas=prediction["terms"], prediction=prediction)
        Accessibility.objects.create(building=self.building, mode="walk", score=50.0, method="m1",
                                     distances={"supermarket": [400.0], "train_station": [400.0]},
                                     geom=Point(257000.0, 470000.0, srid=SRID))
        self._send(self.building)
        self.assertAlmostEqual(self.price(self.home), math.exp(7.0 + 0.004 * 100 - 0.003 * 100 - 0.002 * 1970), places=2)

    def test_the_controls_of_the_building_are_used_and_a_missing_one_is_the_fit_mean(self):
        self._supermarket(self.building, 400.0)
        Building.objects.filter(pk=self.building.pk).update(constructionYear=1920)
        self._send(self.building)
        self.assertAlmostEqual(self.price(self.home), self.expected(400.0, year=1920), places=2)
        Building.objects.filter(pk=self.building.pk).update(constructionYear=1005)      # a BAG placeholder
        self._send(self.building)
        self.assertAlmostEqual(self.price(self.home), self.expected(400.0, year=1960), places=2)

    def test_a_municipality_the_fit_does_not_know_keeps_the_stored_value(self):
        Property.objects.filter(pk=self.home.pk).update(modelledPrice_EUR_per_sqm=1234.0)
        PostcodePrice.objects.update(city=None)
        self._supermarket(self.building, 400.0)
        self._send(self.building)
        self.assertEqual(self.price(self.home), 1234.0)

    def test_without_a_fit_nothing_is_written(self):
        PriceModel.objects.update(isActive=False)
        self._supermarket(self.building, 400.0)
        self._send(self.building)
        self.assertIsNone(self.price(self.home))

    def test_a_fit_without_the_equation_writes_nothing(self):
        PriceModel.objects.update(prediction={})
        self._supermarket(self.building, 400.0)
        self._send(self.building)
        self.assertIsNone(self.price(self.home))

    def test_missing_inputs_keep_the_stored_value(self):
        Property.objects.filter(pk=self.home.pk).update(modelledPrice_EUR_per_sqm=1234.0)
        self._send(self.building)                          # no distances stored for the building
        self.assertEqual(self.price(self.home), 1234.0)
        PostcodePrice.objects.all().delete()               # the dwelling's postcode area is not stored
        self._supermarket(self.building, 400.0)
        self._send(self.building)
        self.assertEqual(self.price(self.home), 1234.0)

    def test_only_dwellings_are_priced(self):
        shop = Property.objects.create(name="s", grossArea=50, usageFunction=["Shop function"], postalCode="7511AA",
                                       geom=Point(257005.0, 470000.0, srid=SRID))
        self._supermarket(self.building, 400.0)
        self._send(self.building)
        self.assertIsNone(self.price(shop))

    def test_a_signal_with_many_buildings_is_one_refresh(self):
        self._supermarket(self.building, 400.0)
        self._supermarket(self.other, 300.0)
        with mock.patch.object(property_price, "reprice", wraps=property_price.reprice) as reprice:
            self._send(self.building, self.other)
        self.assertEqual(reprice.call_count, 1)
        self.assertIsNotNone(self.price(self.home))
        self.assertIsNotNone(self.price(self.neighbour))

    def test_a_failure_never_blocks_the_source_save(self):
        with mock.patch.object(property_price, "reprice", side_effect=RuntimeError("boom")):
            with self.assertLogs("housing.signals", level="ERROR"):
                self._send(self.building)

    def test_empty_signal_does_nothing(self):
        with mock.patch.object(property_price, "reprice") as reprice:
            accessibility_changed.send(sender=Building, mode="walk", building_ids=[])
        reprice.assert_not_called()

    def test_reprice_of_everything_matches_the_signal_path(self):
        self._supermarket(self.building, 400.0)
        self._supermarket(self.other, 400.0)
        self.assertEqual(property_price.reprice(), 2)
        self.assertAlmostEqual(self.price(self.home), self.price(self.neighbour))

    # dashboard parity and the market what-if ------------------------------------------

    def _mp(self, prefix=None):
        summary, model = property_price.unit_summary([self.hood.pk], postcode_prefix=prefix)
        return {"summary": summary, "model": model}

    def test_dashboard_with_default_controls_equals_the_stored_mean(self):
        self._supermarket(self.building, 400.0)
        self._supermarket(self.other, 700.0)
        property_price.reprice()
        indicators = views._modelled_price_indicators(self._mp(), 0.0)
        stored = list(Property.objects.filter(usageFunction__contains=DWELLING).values_list("modelledPrice_EUR_per_sqm", flat=True))
        self.assertTrue(indicators["mp_available"])
        self.assertAlmostEqual(indicators["mp_price"], sum(stored) / len(stored), delta=0.51)   # price is rounded to whole EUR
        self.assertEqual(indicators["mp_priced"], 2)
        self.assertFalse(indicators["mp_whatif"])
        self.assertEqual(indicators["mp_level"], 4000)                                          # mean CBS WOZ of the two areas

    def test_the_dashboard_uses_the_chain_factor_of_the_stored_equation(self):
        self._supermarket(self.building, 400.0)
        property_price.reprice()
        stored = Property.objects.get(pk=self.home.pk).modelledPrice_EUR_per_sqm
        direct = chain.modelled_price_per_sqm(self.prediction, {SUPERMARKET: value_at("supermarket", 400.0)},
                                              {"constructionYear": 1970}, 503, growth_pct=10.0)
        self.assertAlmostEqual(stored * chain.market_growth_factor(10.0), direct, places=1)
        shown = property_price.mean_price(self._mp(prefix="7511AA")["summary"], 10.0)
        self.assertAlmostEqual(shown["price"], direct, places=1)

    def test_the_market_what_if_changes_the_card_and_writes_nothing(self):
        self._supermarket(self.building, 400.0)
        self._supermarket(self.other, 400.0)
        property_price.reprice()
        before = list(Property.objects.order_by("pk").values_list("modelledPrice_EUR_per_sqm", "priceMethod", "last_updated"))
        mp = self._mp()
        default = views._modelled_price_indicators(mp, 0.0)
        growth = views._modelled_price_indicators(mp, 10.0)
        self.assertAlmostEqual(growth["mp_price"], default["mp_price"] * 1.1, delta=1)
        self.assertAlmostEqual(growth["mp_level"], default["mp_level"] * 1.1, delta=1)
        self.assertTrue(growth["mp_whatif"])
        self.assertEqual(before, list(Property.objects.order_by("pk").values_list(
            "modelledPrice_EUR_per_sqm", "priceMethod", "last_updated")))
        self.assertEqual(default["mp_label"], chain.PRICE_LABEL)

    def test_the_card_lists_the_kept_and_the_screened_out_terms(self):
        screening = {"candidates": 3, "kept": 1, "terms": {
            SUPERMARKET: {"status": "kept", "reason": "", "beta": 0.004, "p": 0.01, "effect_per_sd": 0.08, "vif": 1.2},
            "walk:shop": {"status": "dropped", "reason": "redundant with walk:supermarket (|r| = 0.99 >= 0.9)"},
            "walk:park": {"status": "dropped", "reason": "too little variation (sd 0.00 < 1 score points)"}}}
        PriceModel.objects.filter(pk=self.model.pk).update(screening=screening)
        self._supermarket(self.building, 400.0)
        property_price.reprice()
        model = views._modelled_price_indicators(self._mp(), 0.0)["mp_model"]
        self.assertEqual([(t["category"], t["mode"]) for t in model["kept"]], [("supermarket", "walk")])
        self.assertEqual({t["term"] for t in model["dropped"]}, {"walk:shop", "walk:park"})
        self.assertEqual((model["candidates"], model["id"]), (3, self.model.pk))

    def test_card_without_a_fit_says_so_and_stays_unavailable(self):
        PriceModel.objects.update(isActive=False)
        indicators = views._modelled_price_indicators(self._mp(), 0.0)
        self.assertFalse(indicators["mp_available"])
        self.assertFalse(indicators["mp_has_model"])

    def test_panel_renders_the_card_with_the_market_slider_only(self):
        self._supermarket(self.building, 400.0)
        property_price.reprice()
        url = reverse("housing:housing_indicators", args=["neighborhood", self.hood.pk, 2025])
        response = Client().get(url, HTTP_HX_REQUEST="true")
        self.assertContains(response, 'id="market-growth-slider"')
        self.assertContains(response, "% on the WOZ level")
        self.assertNotContains(response, 'id="beta-slider"')
        self.assertNotContains(response, 'id="access-delta-slider"')
        self.assertNotContains(response, "Accessibility Effect")
        self.assertNotContains(response, "Accessibility Change")
        self.assertNotContains(response, "NVM")
        self.assertContains(response, "Modelled Price")
        self.assertNotContains(response, "Fit price model")           # staff only
        self.assertNotContains(response, "data-add-amenity")
        staff = get_user_model().objects.create_user("s", password="x", is_staff=True)
        client = Client()
        client.force_login(staff)
        html = client.get(url, HTTP_HX_REQUEST="true").content.decode()
        self.assertIn("Fit price model", html)
        self.assertIn('data-add-amenity="builtup.Facility"', html)
        self.assertNotIn("Fit on neighborhoods", html)
        self.assertNotIn("data-price-model-unit", html)

    def test_recalculate_clamps_the_market_parameter_and_ignores_the_removed_ones(self):
        self._supermarket(self.building, 400.0)
        property_price.reprice()
        url = reverse("housing:recalculate_indicators", args=["neighborhood", self.hood.pk, 2025])
        response = Client().get(url, {"market_growth": "999", "beta_mult": "-5", "access_delta": "50"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Modelled Price")
        self.assertContains(response, chain.PRICE_LABEL)
        self.assertEqual(views._float_param({"market_growth": "999"}, "market_growth", chain.MARKET_GROWTH_MIN, chain.MARKET_GROWTH_MAX, 0.0),
                         chain.MARKET_GROWTH_MAX)
        self.assertEqual(views._float_param({"market_growth": "-999"}, "market_growth", chain.MARKET_GROWTH_MIN, chain.MARKET_GROWTH_MAX, 0.0),
                         chain.MARKET_GROWTH_MIN)
        self.assertEqual(views._float_param({"market_growth": "abc"}, "market_growth", chain.MARKET_GROWTH_MIN, chain.MARKET_GROWTH_MAX, 0.0), 0.0)


class PriceModelEndpointTests(TestCase):
    def setUp(self):
        self.staff = get_user_model().objects.create_user("staff", password="x", is_staff=True)
        self.url_fit = reverse("housing:price_model_fit")
        self.url_reprice = reverse("housing:price_model_reprice")

    def test_only_staff_may_fit_or_reprice(self):
        client = Client()
        self.assertEqual(client.post(self.url_fit).status_code, 403)
        self.assertEqual(client.post(self.url_reprice).status_code, 403)
        self.assertEqual(client.get(self.url_fit).status_code, 405)

    def test_a_fit_that_cannot_be_made_is_a_409_with_the_reason(self):
        client = Client()
        client.force_login(self.staff)
        response = client.post(self.url_fit)
        self.assertEqual(response.status_code, 409)
        self.assertIn("WOZ", response.json()["error"])

    def test_reprice_without_a_fit_is_a_409(self):
        client = Client()
        client.force_login(self.staff)
        self.assertEqual(client.post(self.url_reprice).status_code, 409)

    def test_exploratory_mode_is_passed_on_and_never_applied(self):
        client = Client()
        client.force_login(self.staff)
        fit = price_model.fit_hedonic(synthetic(n=3, cities=False), use_controls=False, exploratory=True, **FAST)
        with mock.patch.object(price_model, "build_rows", return_value=(synthetic(n=3, cities=False), [], [])), \
                mock.patch.object(postcode_woz, "prepare"), \
                mock.patch.object(price_model, "latest_woz_year", return_value=2024), \
                mock.patch.object(price_model, "fit_hedonic", return_value=fit) as fitted, \
                mock.patch.object(property_price, "reprice") as reprice:
            body = client.post(self.url_fit, {"mode": "exploratory"}).json()
        self.assertEqual(fitted.call_args.kwargs, {"use_controls": False, "exploratory": True, "cluster_name": "neighborhood"})
        self.assertTrue(body["exploratory"])
        self.assertEqual(body["repriced"], 0)
        self.assertIsNone(PriceModel.active())
        self.assertEqual(PriceModel.objects.count(), 1)
        reprice.assert_not_called()

    def test_a_unit_is_not_a_parameter_any_more(self):
        client = Client()
        client.force_login(self.staff)
        with mock.patch.object(price_model, "fit_and_store", side_effect=price_model.PriceModelError("stop")) as fitted:
            client.post(self.url_fit, {"unit": "neighborhood"})
        self.assertEqual(fitted.call_args.kwargs, {"use_controls": True, "exploratory": False})

    def test_a_fit_is_stored_activated_and_reported(self):
        client = Client()
        client.force_login(self.staff)
        fit = price_model.fit_hedonic(synthetic(), **FAST)
        with mock.patch.object(price_model, "build_rows", return_value=(synthetic(), [], [])), \
                mock.patch.object(postcode_woz, "prepare"), \
                mock.patch.object(price_model, "latest_woz_year", return_value=2024), \
                mock.patch.object(price_model, "fit_hedonic", return_value=fit):
            first = client.post(self.url_fit).json()
            second = client.post(self.url_fit).json()
        self.assertEqual(PriceModel.objects.count(), 2)
        self.assertEqual(list(PriceModel.objects.filter(isActive=True).values_list("pk", flat=True)), [second["id"]])
        self.assertEqual(PriceModel.active().pk, second["id"])
        self.assertNotEqual(first["id"], second["id"])
        self.assertEqual(second["label"], chain.PRICE_LABEL)
        self.assertEqual((second["terms_kept"], second["terms_candidates"]), (2, 5))
        self.assertEqual(PriceModel.active().wozYear, 2024)
        self.assertEqual(sorted(PriceModel.active().betas), sorted([SUPERMARKET, STATION]))


class ModelInputTests(TestCase):
    def test_building_controls_of_a_postcode_area(self):
        city = make_city(id=503, cityName="Delft")
        make_neighborhood(id="BU05030101", city=city)
        Building.objects.create(id=1, buildingType="residential", usageFunction=DWELLING, constructionYear=1970,
                                energyLabel="C", geom=make_polygon(257000.0, 470000.0, 30))
        Building.objects.create(id=2, buildingType="residential", usageFunction=DWELLING, constructionYear=1005,
                                energyLabel="A", geom=make_polygon(257200.0, 470000.0, 30))
        for building, code, x in ((1, "7511 AA", 257000.0), (2, "7511AA", 257200.0)):
            Property.objects.create(name="a", grossArea=60, usageFunction=DWELLING, postalCode=code, building_id=building,
                                    geom=Point(x, 470000.0, srid=SRID))
        controls = postcode_woz.building_controls(["7511AA"])["7511AA"]
        self.assertEqual(controls["constructionYear"], 1970)              # the 1005 placeholder is ignored
        self.assertAlmostEqual(controls["energyLabel"], (price_model.ENERGY_ORDINAL["C"] + price_model.ENERGY_ORDINAL["A"]) / 2)

    def test_coverage_boundary_and_more_bag_than_cbs(self):
        class Row:
            def __init__(self, dwellings, area_dwellings):
                self.postcode6, self.dwellings, self.areaDwellings = "x", dwellings, area_dwellings
        kept, excluded = price_model.split_by_coverage([Row(1000, 800), Row(1000, 799), Row(1000, 1220), Row(None, 50)])
        self.assertEqual(len(kept), 2)          # exactly 80 % and more BAG dwellings than the CBS stock both stay
        self.assertEqual(len(excluded), 2)

    def test_a_fit_that_lacks_areas_names_the_excluded_ones(self):
        staff = get_user_model().objects.create_user("c", password="x", is_staff=True)
        excluded = [{"id": "7511AA", "coverage": 0.04, "area_dwellings": 43, "dwellings": 1000}]
        client = Client()
        client.force_login(staff)
        with mock.patch.object(price_model, "build_rows", return_value=(synthetic(n=2, cities=False), [], excluded)), \
                mock.patch.object(postcode_woz, "prepare"), \
                mock.patch.object(price_model, "latest_woz_year", return_value=2024):
            response = client.post(reverse("housing:price_model_fit"))
        self.assertEqual(response.status_code, 409)
        self.assertIn("1 areas were left out", response.json()["error"])
        self.assertIn("80%", response.json()["error"])

    def test_latest_woz_year_is_the_newest_year_with_baselines_of_every_kind(self):
        self.assertIsNone(price_model.latest_woz_year())
        full = dict(avgWOZ_EUR=450_000.0, meanArea_sqm=90.0, baselineAccessWalk=50.0, baselineAccessBike=50.0)
        PostcodePrice.objects.create(postcode6="7511AA", year=2023, baselineCategories={SUPERMARKET: 50.0}, **full)
        PostcodePrice.objects.create(postcode6="7511AA", year=2024, avgWOZ_EUR=450_000.0, meanArea_sqm=90.0,
                                     baselineAccessWalk=50.0, baselineCategories={SUPERMARKET: 50.0})   # no bike baseline
        PostcodePrice.objects.create(postcode6="7511AA", year=2025, baselineCategories={}, **full)       # no term baselines
        self.assertEqual(price_model.latest_woz_year(), 2023)
        PostcodePrice.objects.create(postcode6="7511AB", year=2025, baselineCategories={SUPERMARKET: 50.0}, **full)
        self.assertEqual(price_model.latest_woz_year(), 2025)           # the newest year available, not the year before


class PostcodeFitTests(TestCase):
    """PC6 postcode areas as the fitting unit: the rows, the frozen baselines and the repricing."""

    def setUp(self):
        self.city = make_city(id=153, cityName="Enschede", geom=make_polygon(257000.0, 470000.0, 2000))
        self.hood = make_neighborhood(id="BU01530101", city=self.city, geom=make_polygon(257000.0, 470000.0, 1000))
        NeighborhoodSocialProfile.objects.create(neighborhood=self.hood, socioEconomicStatus=0.4, geom=self.hood.geom)
        self.building = Building.objects.create(id=1, buildingType="residential", usageFunction=DWELLING, constructionYear=1970,
                                                energyLabel="C", geom=make_polygon(257000.0, 470000.0, 30))
        self.other = Building.objects.create(id=2, buildingType="residential", usageFunction=DWELLING, constructionYear=1950,
                                             energyLabel="A", geom=make_polygon(257200.0, 470000.0, 30))
        self.area = Postcode6.objects.create(
            code="7511AA", dataYear=2023, meanWOZ_EUR=360_000.0, dwellings=10, multiFamilyDwellings=5, rental_pct=40.0,
            geom=make_polygon(257000.0, 470000.0, 100))
        self.area2 = Postcode6.objects.create(
            code="7511AB", dataYear=2023, meanWOZ_EUR=450_000.0, dwellings=10, multiFamilyDwellings=0, rental_pct=10.0,
            geom=make_polygon(257200.0, 470000.0, 100))
        for i in range(10):    # the BAG postcode comes with a space in some sources
            self._dwelling(257000.0 + i, "7511 AA", building=self.building)
            self._dwelling(257200.0 + i, "7511AB", area=100.0, building=self.other)
        for building, metres, score_walk, score_bike in ((self.building, 400.0, 50.0, 60.0), (self.other, 1000.0, 70.0, 80.0)):
            for mode, score in (("walk", score_walk), ("bike", score_bike)):
                Accessibility.objects.create(building=building, mode=mode, score=score, method="m1",
                                             distances={"supermarket": [metres]},
                                             network_snapshot=datetime.date(2026, 11, 1),
                                             geom=Point(257000.0, 470000.0, srid=SRID))

    def _dwelling(self, x, postal_code, area=90.0, building=None):
        return Property.objects.create(name="p", grossArea=area, usageFunction=DWELLING, postalCode=postal_code, building=building,
                                       geom=Point(x, 470000.0, srid=SRID))

    def test_prepare_writes_one_row_per_area_with_the_per_m2_value_and_the_baselines(self):
        rows = postcode_woz.prepare()
        self.assertEqual(len(rows), 2)
        row = PostcodePrice.objects.get(postcode6="7511AA", year=2023)
        self.assertAlmostEqual(row.woz_per_sqm, 4000.0)                  # 360 000 / 90 m2
        self.assertEqual((row.postcode4, row.areaDwellings, row.dwellings), ("7511", 10, 10))
        self.assertAlmostEqual(row.multiFamilyShare_pct, 50.0)
        self.assertEqual(row.rentalShare_pct, 40.0)
        self.assertEqual((row.neighborhood_id, row.city_id), (self.hood.pk, 153))
        self.assertEqual((row.baselineAccessWalk, row.baselineAccessBike, row.baselineMethod), (50.0, 60.0, "m1"))
        self.assertEqual(row.method, chain.WOZ_METHOD)

    def test_the_baseline_of_every_term_is_the_mean_value_of_the_area(self):
        postcode_woz.prepare()
        near = PostcodePrice.objects.get(postcode6="7511AA").baselineCategories
        far = PostcodePrice.objects.get(postcode6="7511AB").baselineCategories
        self.assertEqual(len(near), len(chain.candidate_terms()))
        self.assertEqual(near["walk:supermarket"], 100.0)                 # 400 m: inside the full-value distance
        self.assertAlmostEqual(far["walk:supermarket"], round(value_at("supermarket", 1000.0), 2))
        self.assertAlmostEqual(far["bike:supermarket"], round(value_at("supermarket", 1000.0, "bike"), 2))
        self.assertEqual(near["walk:train_station"], 0.0)                 # none reachable

    def test_the_baseline_is_frozen_but_the_statistics_are_refreshed(self):
        postcode_woz.prepare()
        Accessibility.objects.filter(building=self.building, mode="walk").update(score=90.0, distances={"supermarket": [1500.0]})
        Postcode6.objects.filter(code="7511AA").update(meanWOZ_EUR=450_000.0)
        postcode_woz.prepare()
        row = PostcodePrice.objects.get(postcode6="7511AA")
        self.assertEqual(PostcodePrice.objects.count(), 2)               # updated, not duplicated
        self.assertEqual(row.baselineAccessWalk, 50.0)                   # frozen
        self.assertEqual(row.baselineCategories["walk:supermarket"], 100.0)   # frozen
        self.assertAlmostEqual(row.woz_per_sqm, 5000.0)                  # refreshed

    def test_a_row_frozen_before_the_terms_existed_gets_them_once_and_keeps_its_scores(self):
        postcode_woz.prepare()
        PostcodePrice.objects.filter(postcode6="7511AA").update(baselineCategories={}, baselineAccessWalk=55.0)
        postcode_woz.prepare()
        row = PostcodePrice.objects.get(postcode6="7511AA")
        self.assertEqual(row.baselineCategories["walk:supermarket"], 100.0)
        self.assertEqual(row.baselineAccessWalk, 55.0)                   # the aggregate score stays as it was frozen

    def test_prepare_without_postcode_areas_says_what_to_import(self):
        Postcode6.objects.all().delete()
        with self.assertRaisesRegex(ValueError, "PC6"):
            postcode_woz.prepare()

    def test_a_suppressed_woz_value_gives_no_row(self):
        Postcode6.objects.filter(code="7511AB").update(meanWOZ_EUR=None)
        self.assertEqual([r.postcode6 for r in postcode_woz.prepare()], ["7511AA"])

    def test_the_newest_statistics_year_is_prepared_by_default(self):
        Postcode6.objects.filter(code="7511AA").update(dataYear=2024)
        self.assertEqual(postcode_woz.latest_year(), 2024)
        self.assertEqual({r.year for r in postcode_woz.prepare()}, {2024})

    def test_rows_carry_the_terms_the_controls_the_cluster_and_the_weight(self):
        postcode_woz.prepare()
        rows, price_rows, excluded = price_model.build_rows(2023)
        row = next(r for r in rows if r["id"] == "7511AA")
        self.assertEqual((row["city"], row["cluster"], row["weight"]), (153, self.hood.pk, 10))   # clustered by the neighborhood under the area
        self.assertAlmostEqual(row["lnPrice"], math.log(4000.0))
        self.assertEqual(row["terms"]["walk:supermarket"], 100.0)
        self.assertEqual(len(row["terms"]), len(chain.candidate_terms()))
        self.assertAlmostEqual(row["apartmentShare"], 0.5)
        self.assertAlmostEqual(row["rentalShare"], 0.4)
        self.assertEqual(row["constructionYear"], 1970)
        self.assertEqual(row["energyLabel"], price_model.ENERGY_ORDINAL["C"])
        self.assertEqual(row["ses"], 0.4)
        far = next(r for r in rows if r["id"] == "7511AB")
        self.assertAlmostEqual(far["distCentre_km"], 0.2, places=2)   # 200 m east of the municipal centroid
        self.assertEqual(excluded, [])
        self.assertEqual(len(price_rows), 2)

    def test_an_area_with_a_thin_bag_sample_is_left_out(self):
        Postcode6.objects.filter(code="7511AB").update(dwellings=1000)       # 10 BAG dwellings of 1 000 in the CBS stock
        postcode_woz.prepare()
        rows, _price_rows, excluded = price_model.build_rows(2023)
        self.assertEqual([r["id"] for r in rows], ["7511AA"])
        self.assertEqual([(e["id"], e["coverage"]) for e in excluded], [("7511AB", 0.01)])

    PREDICTION = {"form": "linear", "intercept": 7.0, "terms": {SUPERMARKET: 0.004}, "controls": {},
                  "control_means": {}, "cities": {"153": 0.0}, "smearing": 1.0}

    def _model(self):
        return PriceModel.objects.create(n=100, wozYear=2023, form="linear", isActive=True,
                                         termBetas=self.PREDICTION["terms"], prediction=self.PREDICTION)

    def test_a_pc6_fit_prices_each_dwelling_by_its_own_variables_not_its_postcode_woz(self):
        postcode_woz.prepare()
        model = self._model()
        Accessibility.objects.filter(building=self.building, mode="walk").update(distances={"supermarket": [1000.0]})
        written = property_price.reprice(building_ids=[self.building.pk, self.other.pk])
        self.assertEqual(written, 20)
        home = Property.objects.filter(building=self.building).first()
        self.assertAlmostEqual(home.modelledPrice_EUR_per_sqm, round(math.exp(7.0 + 0.004 * value_at("supermarket", 1000.0)), 2), places=2)
        self.assertEqual(home.priceModel_id, model.pk)
        neighbour = Property.objects.filter(building=self.other).first()     # the same distance, in the area with a higher WOZ value
        self.assertAlmostEqual(neighbour.modelledPrice_EUR_per_sqm, home.modelledPrice_EUR_per_sqm, places=2)
        self.assertEqual(chain.PRICE_LABEL in home.priceMethod, True)

    def test_the_controls_of_the_postcode_area_and_the_dwelling_reach_the_price(self):
        postcode_woz.prepare()
        prediction = {**self.PREDICTION, "controls": {"apartmentShare": 0.1, "rentalShare": 0.2, "energyLabel": 0.05,
                                                       "distCentre_km": -0.3, "ses": 0.4},
                      "control_means": {"apartmentShare": 0.0, "rentalShare": 0.0, "energyLabel": 0.0, "distCentre_km": 0.0, "ses": 0.0}}
        PriceModel.objects.create(n=100, wozYear=2023, form="linear", isActive=True, termBetas=prediction["terms"], prediction=prediction)
        property_price.reprice()
        home = Property.objects.filter(building=self.building).first()
        expected = math.exp(7.0 + 0.004 * 100.0 + 0.1 * 0.5 + 0.2 * 0.4 + 0.05 * price_model.ENERGY_ORDINAL["C"]
                            - 0.3 * (math.hypot(home.geom.x - 257000.0, home.geom.y - 470000.0) / 1000.0) + 0.4 * 0.4)
        self.assertAlmostEqual(home.modelledPrice_EUR_per_sqm, round(expected, 2), places=1)

    def test_a_dwelling_with_an_unknown_postcode_keeps_its_stored_value(self):
        postcode_woz.prepare()
        self._model()
        stray = self._dwelling(257005.0, "9999ZZ", building=self.building)
        Property.objects.filter(pk=stray.pk).update(modelledPrice_EUR_per_sqm=1234.0)
        property_price.reprice()
        self.assertEqual(Property.objects.get(pk=stray.pk).modelledPrice_EUR_per_sqm, 1234.0)

    def test_the_dashboard_of_a_postcode_unit_counts_only_its_own_dwellings(self):
        postcode_woz.prepare()
        self._model()
        property_price.reprice()
        summary, model = property_price.unit_summary([self.hood.pk], postcode_prefix="7511AA")
        self.assertEqual(summary["priced"], 10)
        self.assertAlmostEqual(summary["stored_mean"], math.exp(7.0 + 0.004 * 100.0), places=1)
        self.assertAlmostEqual(summary["level_mean"], 4000.0, places=1)
        self.assertEqual(model.betas, {SUPERMARKET: 0.004})
        everything, _model = property_price.unit_summary([self.hood.pk])
        self.assertEqual(everything["priced"], 20)
        self.assertAlmostEqual(everything["level_mean"], 4250.0, places=1)

    def test_there_is_no_neighborhood_fit(self):
        self.assertFalse(hasattr(price_model, "_neighborhood_rows"))
        self.assertFalse(hasattr(price_model, "latest_neighborhood_year"))
        self.assertNotIn("unit", [f.name for f in PriceModel._meta.get_fields()])
        with self.assertRaises(TypeError):
            price_model.fit_and_store(unit="neighborhood")
        for field in ("baselineAccessWalk", "baselineAccessBike", "baselineMethod", "baselineSnapshot"):
            self.assertNotIn(field, [f.name for f in WOZValue._meta.get_fields()])


class RefreezeTests(PostcodeFitTests):
    """The baselines can be frozen again after the accessibility was recomputed with other settings."""

    def test_refreeze_overwrites_the_baselines_and_prepare_alone_does_not(self):
        postcode_woz.prepare()
        Accessibility.objects.filter(building=self.building, mode="walk").update(distances={"supermarket": [1500.0]})
        postcode_woz.prepare()
        self.assertEqual(PostcodePrice.objects.get(postcode6="7511AA").baselineCategories["walk:supermarket"], 100.0)
        postcode_woz.prepare(refreeze=True)
        row = PostcodePrice.objects.get(postcode6="7511AA")
        self.assertAlmostEqual(row.baselineCategories["walk:supermarket"], round(value_at("supermarket", 1500.0), 2))

    def test_the_endpoint_is_staff_only_and_reports(self):
        url = reverse("housing:price_model_refreeze")
        self.assertEqual(Client().post(url).status_code, 403)
        staff = get_user_model().objects.create_user("r", password="x", is_staff=True)
        client = Client()
        client.force_login(staff)
        self.assertEqual(client.get(url).status_code, 405)
        body = client.post(url).json()
        self.assertIn("2 postcode areas", body["message"])


class ControlRowsTests(SimpleTestCase):
    def test_the_card_quotes_the_price_change_per_step_of_each_control(self):
        model = PriceModel(
            spec={"controls": ["constructionYear", "energyLabel"], "dropped_controls": ["ses", "rentalShare"], "controls_requested": True},
            coefficients={"constructionYear": {"coef": 0.002, "p": 0.01}, "energyLabel": {"coef": 0.03, "p": 0.2}})
        kept, dropped = views._control_rows(model)
        by_name = {c["control"]: c for c in kept}
        self.assertAlmostEqual(by_name["constructionYear"]["effect_pct"], (math.exp(0.02) - 1) * 100)   # +10 years
        self.assertEqual(by_name["constructionYear"]["step"], "+10 years")
        self.assertAlmostEqual(by_name["energyLabel"]["effect_pct"], (math.exp(0.03) - 1) * 100)
        self.assertEqual([c["control"] for c in dropped], ["ses", "rentalShare"])

    def test_a_fit_without_controls_lists_none_as_dropped(self):
        model = PriceModel(spec={"controls": [], "dropped_controls": list(price_model.CONTROLS), "controls_requested": False}, coefficients={})
        self.assertEqual(views._control_rows(model), ([], []))
