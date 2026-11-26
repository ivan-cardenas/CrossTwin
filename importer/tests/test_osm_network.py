"""OSM walk/bike network import (importer/osm_network.py)."""
from django.test import SimpleTestCase, TestCase

from importer import osm_network
from importer.external_catalog import CATALOG_BY_KEY


def _identity(lons, lats):
    """Pretend the project CRS is a metre grid: x = lon, y = lat."""
    return list(lons), list(lats)


def _way(way_id, node_ids, coords, **tags):
    tags.setdefault("highway", "residential")
    return {
        "type": "way", "id": way_id, "nodes": node_ids, "tags": tags,
        "geometry": [None if c is None else {"lon": c[0], "lat": c[1]} for c in coords],
    }


class WayModesTests(SimpleTestCase):
    def test_residential_street_is_both(self):
        self.assertEqual(osm_network.way_modes({"highway": "residential"}), (True, True))

    def test_footway_walk_only_unless_bicycle_allowed(self):
        self.assertEqual(osm_network.way_modes({"highway": "footway"}), (True, False))
        self.assertEqual(osm_network.way_modes({"highway": "footway", "bicycle": "designated"}), (True, True))

    def test_cycleway_bike_only_unless_foot_allowed(self):
        self.assertEqual(osm_network.way_modes({"highway": "cycleway"}), (False, True))
        self.assertEqual(osm_network.way_modes({"highway": "cycleway", "foot": "yes"}), (True, True))

    def test_steps_are_not_cyclable(self):
        self.assertEqual(osm_network.way_modes({"highway": "steps"}), (True, False))

    def test_private_and_parking_aisles_are_excluded(self):
        self.assertEqual(osm_network.way_modes({"highway": "service", "access": "private"}), (False, False))
        self.assertEqual(osm_network.way_modes({"highway": "service", "service": "parking_aisle"}), (False, False))
        self.assertEqual(osm_network.way_modes({"highway": "service", "access": "private", "foot": "yes"}), (True, False))

    def test_explicit_denial(self):
        self.assertEqual(osm_network.way_modes({"highway": "residential", "bicycle": "no"}), (True, False))


class SplitWaysTests(SimpleTestCase):
    def test_way_is_cut_at_a_shared_node(self):
        # A straight street 1-2-3-4 along x, crossed at node 3 by a second street 5-3-6 along y.
        main = _way(10, [1, 2, 3, 4], [(0, 0), (100, 0), (200, 0), (300, 0)])
        cross = _way(11, [5, 3, 6], [(200, -100), (200, 0), (200, 100)])
        nodes, edges = osm_network.split_ways([main, cross], _identity)
        pairs = sorted((e["osm_id"], e["from_node"], e["to_node"], round(e["length_m"])) for e in edges)
        self.assertEqual(pairs, [(10, 1, 3, 200), (10, 3, 4, 100), (11, 3, 6, 100), (11, 5, 3, 100)])
        self.assertEqual(set(nodes), {1, 3, 4, 5, 6})  # node 2 is an interior shape point

    def test_edge_keeps_the_intermediate_shape(self):
        nodes, edges = osm_network.split_ways([_way(1, [1, 2, 3], [(0, 0), (30, 40), (30, 140)])], _identity)
        self.assertEqual(len(edges), 1)
        self.assertEqual(edges[0]["coords"], [(0, 0), (30, 40), (30, 140)])
        self.assertAlmostEqual(edges[0]["length_m"], 150.0)

    def test_null_position_breaks_the_way(self):
        way = _way(1, [1, 2, 3, 4], [(0, 0), (10, 0), None, (30, 0)])
        _, edges = osm_network.split_ways([way], _identity)
        self.assertEqual([(e["from_node"], e["to_node"]) for e in edges], [(1, 2)])

    def test_closed_loop_without_other_node_yields_no_self_edge(self):
        loop = _way(1, [1, 2, 3, 1], [(0, 0), (10, 0), (10, 10), (0, 0)])
        _, edges = osm_network.split_ways([loop], _identity)
        # node 1 is visited twice, so the loop is cut there; the only cut points are its ends
        self.assertTrue(all(e["from_node"] != e["to_node"] for e in edges))

    def test_ways_without_a_mode_are_dropped(self):
        way = _way(1, [1, 2], [(0, 0), (10, 0)], highway="service", access="private")
        self.assertEqual(osm_network.split_ways([way], _identity), ({}, []))

    def test_modes_carry_over_to_edges(self):
        _, edges = osm_network.split_ways([_way(1, [1, 2], [(0, 0), (10, 0)], highway="cycleway")], _identity)
        self.assertEqual((edges[0]["walk"], edges[0]["bike"]), (False, True))


class CatalogTests(SimpleTestCase):
    def test_entry_uses_the_network_importer(self):
        entry = CATALOG_BY_KEY["osm_network"]
        self.assertEqual((entry["source"], entry["format"]), ("osm", "overpass_network"))
        self.assertEqual(entry["osm_query"], osm_network.OVERPASS_STATEMENTS)

    def test_query_hash_is_stable_and_short(self):
        entry = CATALOG_BY_KEY["osm_network"]
        self.assertEqual(osm_network.query_hash(entry), osm_network.query_hash(entry))
        self.assertEqual(len(osm_network.query_hash(entry)), 16)

    def test_amenity_query_is_exact_values_for_every_class(self):
        entry = CATALOG_BY_KEY["osm_access_amenities"]
        self.assertFalse([q for q in entry["osm_query"] if "~" in q], "regex filters time out on the public Overpass servers")
        expected = {(tag, value) for tag, values in entry["osm_classes"].items() for value in values}
        found = {tuple(part.strip('"') for part in q.split("[", 1)[1].rstrip("]").split("=")) for q in entry["osm_query"]}
        self.assertEqual(found, expected)

    def test_amenity_classes_are_facility_types(self):
        from builtup.models import Facility

        valid = {value for value, _ in Facility.TYPES}
        for key in ("osm_amenities", "osm_access_amenities"):
            for values in CATALOG_BY_KEY[key]["osm_classes"].values():
                self.assertLessEqual(set(values.values()), valid, key)


class SaveNetworkTests(TestCase):
    def test_reimport_replaces_the_edges_of_returned_ways(self):
        from builtup.models import NetworkEdge, NetworkNode

        main = _way(10, [1, 2], [(155000, 463000), (155100, 463000)])
        entry = CATALOG_BY_KEY["osm_network"]
        nodes, edges = osm_network.split_ways([main], _identity)
        self.assertEqual(osm_network.save_network(nodes, edges, entry), (2, 1))
        self.assertEqual(osm_network.save_network(nodes, edges, entry), (2, 1))  # nodes upserted, edge replaced
        self.assertEqual(NetworkNode.objects.count(), 2)
        edge = NetworkEdge.objects.get()
        self.assertEqual((edge.from_node_id, edge.to_node_id, round(edge.length_m)), (1, 2, 100))
        self.assertEqual(edge.query_hash, osm_network.query_hash(entry))
        self.assertIsNotNone(edge.snapshot_date)
