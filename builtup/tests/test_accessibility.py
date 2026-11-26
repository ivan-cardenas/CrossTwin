"""Accessibility equations (builtup/calculations/chain.py): pinned values and monotonicity."""
import math

from django.test import SimpleTestCase

from builtup.calculations import chain


class DistanceDecayTests(SimpleTestCase):
    def test_full_value_inside_d0(self):
        self.assertEqual(chain.distance_decay(0, "walk"), 1.0)
        self.assertEqual(chain.distance_decay(400, "walk"), 1.0)
        self.assertEqual(chain.distance_decay(800, "bike"), 1.0)

    def test_value_at_cutoff_is_f_at_cutoff(self):
        self.assertAlmostEqual(chain.distance_decay(1600, "walk"), chain.F_AT_CUTOFF, places=12)
        self.assertAlmostEqual(chain.distance_decay(2000, "bike"), chain.F_AT_CUTOFF, places=12)

    def test_pinned_midpoint(self):
        # walk: D0 400, Dmax 1600, halfway (1000 m) -> exp(ln(0.05) * 0.5) = sqrt(0.05)
        self.assertAlmostEqual(chain.distance_decay(1000, "walk"), math.sqrt(0.05), places=12)

    def test_zero_beyond_cutoff_or_unreachable(self):
        self.assertEqual(chain.distance_decay(1600.01, "walk"), 0.0)
        self.assertEqual(chain.distance_decay(None, "walk"), 0.0)

    def test_monotone_non_increasing(self):
        values = [chain.distance_decay(d, "walk") for d in range(0, 2000, 50)]
        self.assertEqual(values, sorted(values, reverse=True))


class ScoreTests(SimpleTestCase):
    def test_no_amenities_scores_zero(self):
        self.assertEqual(chain.accessibility_score({}, "walk"), 0.0)

    def test_everything_next_door_scores_100(self):
        near = {name: [10.0] * len(omegas) for name, (_, omegas) in chain.CATEGORIES.items()}
        self.assertAlmostEqual(chain.accessibility_score(near, "walk"), 100.0, places=9)

    def test_single_category_pinned(self):
        # Only a supermarket at <= D0: that category's weight share of the total weight.
        weight_sum = sum(w for w, _ in chain.CATEGORIES.values())
        expected = 100.0 * chain.CATEGORIES["supermarket"][0] / weight_sum
        self.assertAlmostEqual(chain.accessibility_score({"supermarket": [250.0]}, "walk"), expected, places=9)

    def test_further_amenities_of_a_category_weigh_less(self):
        one = chain.category_value([100.0], "walk", (1.0, 0.5, 0.25))
        two = chain.category_value([100.0, 100.0], "walk", (1.0, 0.5, 0.25))
        three = chain.category_value([100.0, 100.0, 100.0], "walk", (1.0, 0.5, 0.25))
        self.assertAlmostEqual(one, 1.0 / 1.75)
        self.assertAlmostEqual(two, 1.5 / 1.75)
        self.assertAlmostEqual(three, 1.0)

    def test_adding_an_amenity_never_lowers_the_score(self):
        before = {"supermarket": [900.0], "park": [500.0]}
        after = {"supermarket": [300.0], "park": [500.0]}  # a new supermarket is nearer
        self.assertGreater(chain.accessibility_score(after, "walk"), chain.accessibility_score(before, "walk"))
        added = {"supermarket": [900.0], "park": [500.0], "pharmacy": [700.0]}
        self.assertGreater(chain.accessibility_score(added, "walk"), chain.accessibility_score(before, "walk"))

    def test_bike_reaches_further_than_walk(self):
        far = {"supermarket": [1800.0]}
        self.assertEqual(chain.accessibility_score(far, "walk"), 0.0)
        self.assertGreater(chain.accessibility_score(far, "bike"), 0.0)

    def test_minutes(self):
        self.assertAlmostEqual(chain.access_minutes(400, "walk"), 5.0, places=6)
        self.assertIsNone(chain.access_minutes(None, "bike"))


# ── network pass (pandana) on a synthetic street ───────────────────────

from django.conf import settings  # noqa: E402
from django.contrib.gis.geos import LineString, MultiPolygon, Point, Polygon  # noqa: E402
from django.test import TestCase  # noqa: E402

from builtup.calculations import accessibility  # noqa: E402
from builtup.models import Accessibility, Building, Facility, NetworkEdge, NetworkNode  # noqa: E402

SRID = settings.COORDINATE_SYSTEM
X0, Y0 = 155000.0, 463000.0


def _square(cx, cy, half=10.0):
    return MultiPolygon(Polygon.from_bbox((cx - half, cy - half, cx + half, cy + half)), srid=SRID)


class FacilityCategoryTests(SimpleTestCase):
    def test_new_and_legacy_types(self):
        f = accessibility.facility_category
        self.assertEqual(f("supermarket"), "supermarket")
        self.assertEqual(f("transportNode", "station"), "train_station")
        self.assertEqual(f("transportNode", "bus_station"), "bus_stop")
        self.assertIsNone(f("transportNode", "ferry_terminal"))
        self.assertEqual(f("hospital", "clinic"), "clinic_gp")
        self.assertEqual(f("hospital", "hospital"), "hospital")
        self.assertEqual(f("market"), "shop")
        self.assertIsNone(f("fire_station"))

    def test_park_access_points_follow_the_edge(self):
        from shapely.geometry import box

        points = accessibility.park_access_points(box(0, 0, 100, 100), spacing_m=50)
        self.assertEqual(len(points), 9)  # 400 m ring, one point every 400/9 m
        self.assertEqual(len(accessibility.park_access_points(box(0, 0, 10, 10), spacing_m=50)), 1)


class NetworkPassTests(TestCase):
    """Eight nodes 100 m apart along y = Y0, ids 1..8, walkable and cyclable."""

    def setUp(self):
        accessibility.clear_network_cache()
        NetworkNode.objects.bulk_create([NetworkNode(osm_id=i + 1, geom=Point(X0 + 100 * i, Y0, srid=SRID)) for i in range(8)])
        NetworkEdge.objects.bulk_create([
            NetworkEdge(from_node_id=i + 1, to_node_id=i + 2, length_m=100.0, walk=True, bike=True,
                        geom=LineString((X0 + 100 * i, Y0), (X0 + 100 * i + 100, Y0), srid=SRID))
            for i in range(7)
        ])
        # centroid (X0, Y0 + 20): snaps to node 1 with a 20 m offset
        self.building = Building.objects.create(id=1, buildingType="residential", geom=_square(X0, Y0 + 20))
        # far from every node: not connected
        self.remote = Building.objects.create(id=2, buildingType="residential", geom=_square(X0, Y0 + 2000))

    def _supermarket(self, i, offset, sid):
        return Facility.objects.create(name=f"S{sid}", type="supermarket", sourceID=sid,
                                       geom=Point(X0 + 100 * i, Y0 + offset, srid=SRID))

    def test_distance_adds_network_and_both_offsets(self):
        self._supermarket(4, 30, "a")  # node 5: 400 m along the street, 30 m off it
        written = accessibility.compute(Building.objects.all())
        self.assertEqual(written, {"walk": 2, "bike": 2})
        row = Accessibility.objects.get(building=self.building, mode="walk")
        self.assertEqual(row.distances, {"supermarket": [450.0]})
        self.assertEqual(row.method, chain.METHOD_STAMP)
        weight_sum = sum(w for w, _ in chain.CATEGORIES.values())
        # 450 m is just past D0 = 400 m on foot
        expected = 100 * chain.CATEGORIES["supermarket"][0] * chain.distance_decay(450, "walk") / weight_sum
        self.assertAlmostEqual(row.score, expected, places=9)

    def test_amenity_beyond_the_cutoff_is_not_reached_on_foot_but_by_bike(self):
        NetworkNode.objects.bulk_create([NetworkNode(osm_id=100 + i, geom=Point(X0 + 700 + 300 * i, Y0, srid=SRID)) for i in range(1, 8)])
        prev = 8
        for i in range(1, 8):
            NetworkEdge.objects.create(from_node_id=prev, to_node_id=100 + i, length_m=300.0, walk=True, bike=True,
                                       geom=LineString((X0 + 700 + 300 * (i - 1), Y0), (X0 + 700 + 300 * i, Y0), srid=SRID))
            prev = 100 + i
        accessibility.clear_network_cache()
        Facility.objects.create(name="far", type="pharmacy", sourceID="far", geom=Point(X0 + 1900, Y0, srid=SRID))  # ~1.9 km: past the 1.6 km walk cut-off, inside the 2 km bike one
        accessibility.compute(Building.objects.filter(pk=1))
        self.assertEqual(Accessibility.objects.get(building_id=1, mode="walk").distances, {})
        self.assertIn("pharmacy", Accessibility.objects.get(building_id=1, mode="bike").distances)

    def test_a_building_off_the_network_is_not_connected(self):
        self._supermarket(4, 30, "a")
        accessibility.compute(Building.objects.all())
        row = Accessibility.objects.get(building=self.remote, mode="walk")
        self.assertEqual((row.distances, row.score), ({}, 0.0))

    def test_adding_an_amenity_raises_the_score_and_recompute_is_idempotent(self):
        self._supermarket(6, 0, "far")  # 600 m + 20 m
        accessibility.compute(Building.objects.filter(pk=1))
        before = Accessibility.objects.get(building_id=1, mode="walk").score
        self._supermarket(1, 0, "near")  # 100 m + 20 m
        Facility.objects.create(name="pharm", type="pharmacy", sourceID="p", geom=Point(X0 + 200, Y0, srid=SRID))
        accessibility.compute(Building.objects.filter(pk=1))
        after = Accessibility.objects.get(building_id=1, mode="walk")
        self.assertGreater(after.score, before)
        # supermarkets keep only the nearest one (CATEGORIES omegas = (1.0,)): 100 m + the 20 m offset
        self.assertEqual(after.distances["supermarket"], [120.0])
        self.assertEqual(after.distances["pharmacy"], [220.0])
        accessibility.compute(Building.objects.filter(pk=1))
        self.assertEqual(Accessibility.objects.filter(building_id=1, mode="walk").count(), 1)
        self.assertAlmostEqual(Accessibility.objects.get(building_id=1, mode="walk").score, after.score, places=9)

    def test_no_network_writes_nothing(self):
        NetworkEdge.objects.all().delete()
        accessibility.clear_network_cache()
        self.assertEqual(accessibility.compute(Building.objects.all()), {})
        self.assertEqual(Accessibility.objects.count(), 0)


# ── receivers (Facilities / Green_Area / Streets -> Accessibility) ─────

from unittest import mock  # noqa: E402

from nature.models import GreenSpaces  # noqa: E402

from builtup import signals  # noqa: E402


class ReceiverFixture:
    """
    Shared setUp and helpers of the receiver test classes: the same eight-node street as
    NetworkPassTests, with a building at its west end. A mixin (not a TestCase), so the test
    classes that use it do not inherit and re-run each other's tests.
    """

    def setUp(self):
        accessibility.clear_network_cache()
        NetworkNode.objects.bulk_create([NetworkNode(osm_id=i + 1, geom=Point(X0 + 100 * i, Y0, srid=SRID)) for i in range(8)])
        NetworkEdge.objects.bulk_create([
            NetworkEdge(from_node_id=i + 1, to_node_id=i + 2, length_m=100.0, walk=True, bike=True,
                        geom=LineString((X0 + 100 * i, Y0), (X0 + 100 * i + 100, Y0), srid=SRID))
            for i in range(7)
        ])
        self.near = Building.objects.create(id=1, buildingType="residential", geom=_square(X0, Y0 + 20))
        # 1.8 km north of the street: outside the 1.6 km walk reach of an amenity on it, inside the 2 km bike reach
        self.north = Building.objects.create(id=2, buildingType="residential", geom=_square(X0, Y0 + 1800))
        self.received = []
        signals.accessibility_changed.connect(self._receive, dispatch_uid="test_access_changed")
        self.addCleanup(signals.accessibility_changed.disconnect, dispatch_uid="test_access_changed")

    def _receive(self, sender, mode, building_ids, **kwargs):
        self.received.append((mode, sorted(building_ids)))

    def _score(self, building_id=1, mode="walk"):
        row = Accessibility.objects.filter(building_id=building_id, mode=mode).first()
        return row.score if row else None

    def _facility(self, type_="supermarket", i=2, sid="f", **kw):
        return Facility.objects.create(name=sid, type=type_, sourceID=sid, geom=Point(X0 + 100 * i, Y0 + 5, srid=SRID), **kw)

class AccessibilityReceiverTests(ReceiverFixture, TestCase):
    def test_a_new_facility_scores_the_buildings_it_reaches_only(self):
        self._facility()
        self.assertGreater(self._score(1, "walk"), 0)
        self.assertGreater(self._score(1, "bike"), 0)
        self.assertIsNone(self._score(2, "walk"))   # beyond the 1.6 km walk reach: not even recomputed
        self.assertIsNotNone(self._score(2, "bike"))  # within the 2 km bike reach (but off the network: score 0)
        self.assertIn(("walk", [1]), self.received)

    def test_a_second_amenity_raises_the_score(self):
        self._facility("supermarket", 5, "a")
        before = self._score()
        self._facility("pharmacy", 2, "b")
        self.assertGreater(self._score(), before)

    def test_deleting_a_facility_lowers_the_score(self):
        self._facility("supermarket", 2, "a")
        shop = self._facility("pharmacy", 2, "b")
        with_both = self._score()
        shop.delete()
        self.assertLess(self._score(), with_both)

    def test_moving_a_facility_refreshes_old_and_new_place(self):
        facility = self._facility("supermarket", 2, "a")
        near_score = self._score()
        facility.geom = Point(X0 + 700, Y0 + 5, srid=SRID)  # 700 m + offsets: still inside the cut-off, far past D0
        facility.save()
        self.assertLess(self._score(), near_score)

    def test_edits_that_change_no_score_refresh_nothing(self):
        facility = self._facility("supermarket", 2, "a")
        fire = self._facility("fire_station", 3, "fire")  # not a destination
        with mock.patch.object(signals, "refresh_accessibility") as refresh:
            facility.name = "Renamed"
            facility.save()
            fire.geom = Point(X0 + 400, Y0, srid=SRID)
            fire.save()
            fire.delete()
        refresh.assert_not_called()

    def test_a_deferred_block_refreshes_once(self):
        with mock.patch.object(signals, "refresh_accessibility") as refresh:
            with signals.deferred_accessibility_refresh():
                for i in range(4):
                    self._facility("shop", i, f"s{i}")
            refresh.assert_called_once()
            extents = refresh.call_args.args[0]
            self.assertEqual(len(extents), 4)

    def test_a_park_is_a_destination_but_a_garden_is_not(self):
        garden = GreenSpaces.objects.create(name="Garden", type="garden", geom=_square(X0 + 200, Y0 + 40, 30))
        self.assertIsNone(self._score())
        park = GreenSpaces.objects.create(name="Park", type="park", geom=_square(X0 + 200, Y0 + 40, 30))
        self.assertGreater(self._score(), 0)
        self.assertEqual(Accessibility.objects.get(building_id=1, mode="walk").distances.keys(), {"park"})
        before = self._score()
        park.delete()
        self.assertLess(self._score(), before)
        garden.delete()

    def test_a_changed_segment_refreshes_the_buildings_around_it(self):
        self._facility("supermarket", 7, "far")  # 700 m away
        before = self._score()
        edge = NetworkEdge.objects.get(from_node_id=3)
        edge.length_m = 10.0  # a shortcut
        edge.save()
        self.assertGreater(self._score(), before)

    def test_without_a_network_nothing_is_written(self):
        NetworkEdge.objects.all().delete()
        accessibility.clear_network_cache()
        self._facility()
        self.assertEqual(Accessibility.objects.count(), 0)


class AccessibilityContractTests(ReceiverFixture, TestCase):
    """Remaining rule-10 cases: cascade, raw saves, deletes, bulk replay, cache key, parameter stamp."""

    def test_deleting_a_scored_building_removes_its_rows(self):
        self._facility()
        self.assertTrue(Accessibility.objects.filter(building_id=1).exists())
        self.near.delete()
        self.assertFalse(Accessibility.objects.filter(building_id=1).exists())

    def test_deleting_a_segment_cuts_the_building_off(self):
        self._facility("supermarket", 5, "far")
        before = self._score()
        NetworkEdge.objects.get(from_node_id=2).delete()  # the street is cut between nodes 2 and 3
        self.assertLess(self._score(), before)

    def test_moving_a_park_refreshes_old_and_new_place(self):
        park = GreenSpaces.objects.create(name="Park", type="park", geom=_square(X0 + 200, Y0 + 40, 30))
        near = self._score()
        park.geom = _square(X0 + 700, Y0 + 40, 30)
        park.save()
        self.assertLess(self._score(), near)

    def test_raw_saves_refresh_nothing(self):
        facility = self._facility("supermarket", 2, "a")
        with mock.patch.object(signals, "refresh_accessibility") as refresh:
            signals.facility_access_saved(Facility, facility, created=True, raw=True)
            signals.green_access_saved(GreenSpaces, GreenSpaces(type="park", geom=_square(X0, Y0)), created=True, raw=True)
            signals.network_edge_saved(NetworkEdge, NetworkEdge.objects.first(), raw=True)
        refresh.assert_not_called()

    def test_bulk_facility_finalizer_replays_the_receiver(self):
        from importer.batching import BULK_IMPORT_MODELS

        rows = [Facility(name="s", type="supermarket", geom=Point(X0 + 100, Y0, srid=SRID)),
                Facility(name="fire", type="fire_station", geom=Point(X0 + 300, Y0, srid=SRID))]
        with mock.patch("importer.batching.schedule_accessibility") as schedule:
            BULK_IMPORT_MODELS["builtup.Facility"](rows)
        (geoms,), _ = schedule.call_args
        self.assertEqual([g.x for g in geoms], [X0 + 100])  # the fire station is no destination

    def test_a_deferred_block_collects_parks_and_segments_too(self):
        with mock.patch.object(signals, "refresh_accessibility") as refresh:
            with signals.deferred_accessibility_refresh():
                GreenSpaces.objects.create(name="Park", type="park", geom=_square(X0 + 200, Y0 + 40, 30))
                edge = NetworkEdge.objects.first()
                edge.length_m = 90.0
                edge.save()
            refresh.assert_called_once()
            self.assertEqual(len(refresh.call_args.args[0]), 2)

    def test_an_edit_in_place_changes_the_graph_cache_key(self):
        before = accessibility._key("walk")[0]
        edge = NetworkEdge.objects.first()
        edge.length_m = 50.0
        edge.save()
        self.assertNotEqual(accessibility._key("walk")[0], before)

    def test_rows_carry_the_parameter_stamp(self):
        self._facility()
        method = Accessibility.objects.get(building_id=1, mode="walk").method
        self.assertTrue(method.startswith(chain.ACCESS_METHOD))
        self.assertEqual(method, f"{chain.ACCESS_METHOD} {chain._params_hash()}")
        self.assertEqual(len(chain._params_hash()), 8)
