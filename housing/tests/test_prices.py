"""
House prices (Phase 3 of docs/ACCESSIBILITY_PLAN.md): CBS WOZ per m2 and the WOZ map layer.
"""
from unittest import mock

from django.conf import settings
from django.contrib.gis.geos import Point
from django.test import SimpleTestCase, TestCase

from builtup.models import Building, Property
from watersupply.tests.factories import make_city, make_neighborhood, make_polygon

from housing.calculations import chain, woz
from housing.models import WOZValue
from importer import cbs_woz

SRID = settings.COORDINATE_SYSTEM
DWELLING = ["Residential function"]


class PriceEquationTests(SimpleTestCase):
    def test_woz_per_sqm_pinned(self):
        self.assertAlmostEqual(chain.woz_per_sqm(450_000, 100.0), 4500.0)

    def test_woz_per_sqm_needs_a_plausible_area(self):
        self.assertIsNone(chain.woz_per_sqm(450_000, None))
        self.assertIsNone(chain.woz_per_sqm(None, 100.0))
        self.assertIsNone(chain.woz_per_sqm(450_000, chain.MIN_DWELLING_AREA_SQM - 1))
        self.assertIsNone(chain.woz_per_sqm(450_000, chain.WOZ_AREA_MAX_SQM + 1))


class WozTests(TestCase):
    def setUp(self):
        self.city = make_city(id=503, cityName="Delft")
        self.hood = make_neighborhood(id="BU05030101", city=self.city)
        self.building = Building.objects.create(id=1, buildingType="residential", geom=make_polygon(257000.0, 470000.0, 30))

    def _property(self, area, usage=DWELLING, dx=0.0, living=None):
        return Property.objects.create(name="p", grossArea=area, livingArea=living, usageFunction=usage,
                                       geom=Point(257000.0 + dx, 470000.0, srid=SRID))

    def test_mean_dwelling_area_counts_dwellings_with_a_plausible_area_only(self):
        self._property(100.0)
        self._property(80.0, dx=1.0)
        self._property(95.0, dx=2.0, living=60.0)                          # livingArea wins over grossArea
        self._property(500.0, usage=["Shop function"], dx=3.0)             # not a dwelling
        self._property(5.0, dx=4.0)                                        # below the Bbl minimum: dropped
        mean, count = woz.mean_dwelling_area([self.hood.pk])[self.hood.pk]
        self.assertEqual(count, 3)
        self.assertAlmostEqual(mean, (100 + 80 + 60) / 3)

    def test_woz_value_derives_the_per_m2_value(self):
        row = WOZValue.objects.create(neighborhood=self.hood, year=2024, avgWOZ_EUR=450_000.0, meanArea_sqm=90.0)
        self.assertAlmostEqual(row.woz_per_sqm, 5000.0)
        self.assertEqual(row.method, chain.WOZ_METHOD)
        gap = WOZValue.objects.create(neighborhood=self.hood, year=2023, avgWOZ_EUR=None, meanArea_sqm=90.0)
        self.assertIsNone(gap.woz_per_sqm)
        self.assertEqual(gap.method, "")


class CbsWozImportTests(TestCase):
    KEYS = {"year": 2024, "woz_key": "GemiddeldeWOZWaardeVanWoningen_39", "stock_key": "Woningvoorraad_35"}
    DATASET = {"key": "CBS_WOZ_2024", "table_id": "85984NED", "params": KEYS}

    ROWS = [
        {"WijkenEnBuurten": "GM0503    ", "GemiddeldeWOZWaardeVanWoningen_39": 400, "Woningvoorraad_35": 50000},
        {"WijkenEnBuurten": "WK050301  ", "GemiddeldeWOZWaardeVanWoningen_39": 410, "Woningvoorraad_35": 3000},
        {"WijkenEnBuurten": "BU05030101", "GemiddeldeWOZWaardeVanWoningen_39": 450, "Woningvoorraad_35": 1200},
        {"WijkenEnBuurten": "BU05030102", "GemiddeldeWOZWaardeVanWoningen_39": None, "Woningvoorraad_35": 15},
        {"WijkenEnBuurten": "BU05039999", "GemiddeldeWOZWaardeVanWoningen_39": 300, "Woningvoorraad_35": 900},
    ]

    def _response(self):
        response = mock.Mock()
        response.json.return_value = {"value": self.ROWS}
        return response

    def test_rows_keep_buurten_and_scale_to_euros(self):
        parsed = cbs_woz.parse_rows(self.ROWS, self.KEYS["woz_key"], self.KEYS["stock_key"])
        self.assertEqual(parsed, {"BU05030101": (450000, 1200), "BU05030102": (None, 15), "BU05039999": (300000, 900)})

    def test_import_writes_stored_neighborhoods_only_and_fills_the_area(self):
        city = make_city(id=503, cityName="Delft")
        hood = make_neighborhood(id="BU05030101", city=city)
        make_neighborhood(id="BU05030102", district=hood.district, geom=make_polygon(300000.0, 470000.0, 100))
        Building.objects.create(id=1, buildingType="residential", geom=make_polygon(257000.0, 470000.0, 30))
        Property.objects.create(name="p", grossArea=90.0, usageFunction=DWELLING, geom=Point(257000.0, 470000.0, srid=SRID))

        with mock.patch("importer.cbs_woz.requests.get", return_value=self._response()) as get:
            result = cbs_woz.fetch(self.DATASET)

        self.assertEqual((result.status, result.records_created), ("success", 2))   # BU05039999 is not stored
        self.assertIn("startswith(WijkenEnBuurten,'BU0503')", get.call_args.kwargs["params"]["$filter"])
        row = WOZValue.objects.get(neighborhood=hood, year=2024)
        self.assertEqual((row.avgWOZ_EUR, row.dwellings, row.cbs_table_id), (450000.0, 1200, "85984NED"))
        self.assertAlmostEqual(row.woz_per_sqm, 5000.0)
        self.assertIsNone(WOZValue.objects.get(neighborhood_id="BU05030102").avgWOZ_EUR)   # CBS gap stays visible

    def test_a_second_import_updates_instead_of_duplicating(self):
        city = make_city(id=503, cityName="Delft")
        make_neighborhood(id="BU05030101", city=city)
        with mock.patch("importer.cbs_woz.requests.get", return_value=self._response()):
            cbs_woz.fetch(self.DATASET)
            again = cbs_woz.fetch(self.DATASET)
        self.assertEqual((again.records_created, again.records_updated), (0, 1))
        self.assertEqual(WOZValue.objects.count(), 1)

    def test_without_neighborhoods_nothing_is_requested(self):
        make_city(id=503, cityName="Delft")
        with mock.patch("importer.cbs_woz.requests.get") as get:
            result = cbs_woz.fetch(self.DATASET)
        get.assert_not_called()
        self.assertEqual(result.status, "success")

    def test_catalog_has_one_entry_per_table_year(self):
        from importer.external_catalog import CATALOG_BY_KEY

        for year in range(2019, 2025):
            entry = CATALOG_BY_KEY[f"CBS_WOZ_{year}"]
            self.assertEqual(entry["params"]["year"], year)
            self.assertEqual(entry["target_model"], "housing.WOZValue")
        self.assertNotIn("nvm_market_reports", CATALOG_BY_KEY)


class WozLayerTests(TestCase):
    """The map layer is the proxy WOZValueLatest: latest year per neighborhood, painted by woz_per_sqm."""

    def setUp(self):
        self.hood = make_neighborhood(city=make_city(id=503, cityName="Delft"))

    def test_layer_is_registered_and_the_table_is_not(self):
        from core.utils import MODEL_REGISTRY, VECTOR_REGISTRY

        self.assertIn("housing.WOZValueLatest", VECTOR_REGISTRY)
        self.assertNotIn("housing.WOZValue", MODEL_REGISTRY)

    def test_row_carries_the_neighborhood_geometry(self):
        row = WOZValue.objects.create(neighborhood=self.hood, year=2024, avgWOZ_EUR=450_000.0, meanArea_sqm=90.0)
        self.assertTrue(row.geom.equals(self.hood.geom))

    def test_only_the_latest_year_of_each_neighborhood_is_shown(self):
        from housing.models import WOZValueLatest

        other = make_neighborhood(district=self.hood.district)
        for hood, year in ((self.hood, 2022), (self.hood, 2024), (other, 2023)):
            WOZValue.objects.create(neighborhood=hood, year=year, avgWOZ_EUR=400_000.0, meanArea_sqm=100.0)
        self.assertEqual(sorted(WOZValueLatest.objects.values_list("neighborhood_id", "year")),
                         sorted([(self.hood.pk, 2024), (other.pk, 2023)]))

    def test_style_classes_cover_the_legend(self):
        from mainMap.styles.layerStyles import LAYER_STYLES, WOZ_CLASSES

        style = LAYER_STYLES["housing.WOZValueLatest"]
        self.assertEqual(len(style["legend"]), len(WOZ_CLASSES) + 1)   # classes + "No value"
