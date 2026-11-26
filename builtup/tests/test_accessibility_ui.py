"""Accessibility UI backend: map layers, indicator, info / calculate endpoints, help text."""
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import LineString, MultiPolygon, Point, Polygon
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from administrative.models import City, District, Neighborhood, Province
from builtup import views
from builtup.calculations import chain
from builtup.calculations.indicators import calculate_accessibility
from builtup.models import (Accessibility, AccessibilityBike, AccessibilityWalk, Building, Facility, NetworkEdge,
                            NetworkNode)
from core.indicator_help import HELP
from core.utils import VECTOR_REGISTRY
from mainMap.styles.layerStyles import ACCESS_CLASSES, ACCESS_LEGEND, LAYER_STYLES

SRID = settings.COORDINATE_SYSTEM
X0, Y0 = 155000.0, 463000.0


def _rect(x0, y0, x1, y1):
    return MultiPolygon(Polygon.from_bbox((x0, y0, x1, y1)), srid=SRID)


class StaticTests(SimpleTestCase):
    def test_only_the_mode_proxies_are_map_layers(self):
        self.assertIn("builtup.AccessibilityWalk", VECTOR_REGISTRY)
        self.assertIn("builtup.AccessibilityBike", VECTOR_REGISTRY)
        self.assertIn("builtup.NetworkEdge", VECTOR_REGISTRY)
        self.assertNotIn("builtup.Accessibility", VECTOR_REGISTRY)
        self.assertNotIn("builtup.NetworkNode", VECTOR_REGISTRY)

    def test_styles_and_legend_share_one_class_list(self):
        for key in ("builtup.AccessibilityWalk", "builtup.AccessibilityBike", "builtup.NetworkEdge"):
            self.assertIn(key, LAYER_STYLES)
        self.assertEqual([item["color"] for item in ACCESS_LEGEND], [color for _, color, _ in ACCESS_CLASSES])
        paint = LAYER_STYLES["builtup.AccessibilityWalk"]["layers"][0]["paint"]["circle-color"]
        self.assertEqual(paint[0], "step")
        self.assertEqual(paint[3::2], [bound for bound, _, _ in ACCESS_CLASSES[1:]])

    def test_help_text_quotes_the_current_constants(self):
        text = HELP["builtup.accessibility"]["how"]
        self.assertIn(f"({chain.FULL_VALUE_M['walk']:.0f} m; {chain.FULL_VALUE_M['bike']:.0f} m by bike)", text)
        self.assertIn(f"({chain.CUTOFF_M['walk'] / 1000:g} km; {chain.CUTOFF_M['bike'] / 1000:g} km by bike)", text)

    def test_the_card_value_comes_from_the_stored_means(self):
        indicators = views._build_indicators(views.MOCK_DATA)
        self.assertEqual(indicators["access_walk"]["mean_score"], 52.0)
        self.assertEqual(indicators["access_bike"]["buildings"], 58_000)


class DataTests(TestCase):
    def setUp(self):
        province = Province.objects.create(ProvinceName="P", geom=_rect(X0 - 500, Y0 - 500, X0 + 1000, Y0 + 500))
        city = City.objects.create(province=province, cityName="C", geom=_rect(X0 - 500, Y0 - 500, X0 + 1000, Y0 + 500))
        district = District.objects.create(id="WK01", city=city, districtName="D", geom=_rect(X0 - 500, Y0 - 500, X0 + 1000, Y0 + 500))
        self.hood = Neighborhood.objects.create(id="BU01", district=district, neighborhoodName="N", currentPopulation=10,
                                                geom=_rect(X0 - 500, Y0 - 500, X0 + 1000, Y0 + 500))
        self.a = Building.objects.create(id=1, buildingType="residential", geom=_rect(X0, Y0, X0 + 10, Y0 + 10))
        self.b = Building.objects.create(id=2, buildingType="residential", geom=_rect(X0 + 100, Y0, X0 + 110, Y0 + 10))

    def _row(self, building, mode, score):
        return Accessibility.objects.create(building=building, mode=mode, score=score, method=chain.METHOD_STAMP,
                                            geom=Point(X0, Y0, srid=SRID))

    def test_proxies_show_one_mode_each(self):
        self._row(self.a, "walk", 40)
        self._row(self.a, "bike", 70)
        self.assertEqual([r.score for r in AccessibilityWalk.objects.all()], [40])
        self.assertEqual([r.score for r in AccessibilityBike.objects.all()], [70])
        self.assertEqual(Accessibility.objects.count(), 2)

    def test_unit_means_per_mode(self):
        self._row(self.a, "walk", 40)
        self._row(self.b, "walk", 0)
        self._row(self.a, "bike", 70)
        result = calculate_accessibility(self.hood)
        self.assertEqual(result["walk"], {"mean_score": 20.0, "buildings": 2, "unconnected": 1})
        self.assertEqual(result["bike"], {"mean_score": 70.0, "buildings": 1, "unconnected": 0})

    def test_unit_without_scores_reports_none(self):
        result = calculate_accessibility(self.hood)
        self.assertEqual(result["walk"], {"mean_score": None, "buildings": 0, "unconnected": 0})

    def test_the_card_value_zero_is_shown_not_dashed(self):
        self._row(self.a, "walk", 0)
        data = {**views.MOCK_DATA, "accessibility": calculate_accessibility(self.hood)}
        self.assertEqual(views._build_indicators(data)["access_walk"]["mean_score"], 0.0)


class EndpointTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.staff = User.objects.create_user("staff", password="x", is_staff=True)
        Building.objects.create(id=1, buildingType="residential", geom=_rect(X0, Y0 + 15, X0 + 10, Y0 + 25))

    def _network(self):
        NetworkNode.objects.bulk_create([NetworkNode(osm_id=i, geom=Point(X0 + 100 * i, Y0, srid=SRID)) for i in range(1, 4)])
        NetworkEdge.objects.bulk_create([
            NetworkEdge(from_node_id=i, to_node_id=i + 1, length_m=100.0, walk=True, bike=i == 1,
                        geom=LineString((X0 + 100 * i, Y0), (X0 + 100 * i + 100, Y0), srid=SRID))
            for i in (1, 2)
        ])

    def test_info_is_open_and_reports_no_network(self):
        data = self.client.get(reverse("builtup:accessibility_info")).json()
        self.assertFalse(data["has_network"])
        self.assertFalse(data["can_calculate"])
        self.assertEqual(data["modes"]["walk"]["layer"], "builtup.AccessibilityWalk")
        self.assertEqual(data["modes"]["bike"]["cutoff_m"], chain.CUTOFF_M["bike"])

    def test_info_counts_edges_per_mode(self):
        self._network()
        data = self.client.get(reverse("builtup:accessibility_info")).json()
        self.assertTrue(data["has_network"])
        self.assertEqual((data["modes"]["walk"]["edges"], data["modes"]["bike"]["edges"]), (2, 1))

    def test_calculate_needs_staff(self):
        response = self.client.post(reverse("builtup:accessibility_calculate"))
        self.assertEqual(response.status_code, 403)

    def test_calculate_needs_a_network(self):
        self.client.force_login(self.staff)
        response = self.client.post(reverse("builtup:accessibility_calculate"))
        self.assertEqual(response.status_code, 409)
        self.assertIn("Walk & bike network", response.json()["error"])

    def test_calculate_scores_the_buildings(self):
        self._network()
        Facility.objects.create(name="S", type="supermarket", sourceID="s", geom=Point(X0 + 200, Y0 + 5, srid=SRID))
        self.client.force_login(self.staff)
        Accessibility.objects.all().delete()
        response = self.client.post(reverse("builtup:accessibility_calculate"))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["written"], {"walk": 1, "bike": 1})
        self.assertEqual(data["modes"]["walk"]["buildings"], 1)
        self.assertGreater(data["modes"]["walk"]["mean_score"], 0)

    def test_calculate_is_post_only(self):
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(reverse("builtup:accessibility_calculate")).status_code, 405)
