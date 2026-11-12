"""
Degree of Urbanisation: builtup/calculations/degurba.py (grid rules), builtup/calculations/chain.py
(unit class, rate), builtup/calculations/urbanisation.py (allocation, refresh) and the
receivers in builtup/signals.py. docs/DEGREE_OF_URBANISATION.md.
"""
from unittest import mock

import numpy as np
from django.conf import settings
from django.contrib.gis.geos import MultiPolygon, Point, Polygon
from django.test import SimpleTestCase, TestCase

from builtup.calculations import chain, degurba, urbanisation
from builtup.models import Building, PopulationAllocation, Property, Urbanisation, UrbanisationCell

SRID = settings.COORDINATE_SYSTEM


def grid(shape, fill=0.0):
    return np.full(shape, float(fill))


def run(pop, resolution_m=1000, built=None, water=None, settlement=None, **kw):
    pop = np.asarray(pop, dtype=float)
    return degurba.classify(pop, np.zeros_like(pop) if built is None else built,
                            np.zeros_like(pop) if water is None else water,
                            (pop > 0) if settlement is None else settlement,
                            resolution_m=resolution_m, **kw)


class OriginalRulesTests(SimpleTestCase):
    """1 km cells: the GHSL/Eurostat rules as published."""

    def test_urban_centre_needs_50000_people_in_4_connected_dense_cells(self):
        pop = grid((7, 7))
        pop[1:6, 1:6] = 3000          # 25 cells x 3 000 = 75 000
        l2 = run(pop)["l2"]
        self.assertTrue((l2[1:6, 1:6] == 30).all())
        pop[1:6, 1:6] = 1900          # 47 500: too small for a centre -> dense urban cluster
        self.assertTrue((run(pop)["l2"][1:6, 1:6] == 23).all())

    def test_diagonal_cells_do_not_form_a_centre(self):
        pop = grid((4, 4))
        pop[1, 1] = pop[2, 2] = 30_000
        l2 = run(pop)["l2"]
        self.assertEqual((l2[1, 1], l2[2, 2]), (23, 23))   # two 4-connected dense clusters
        pop[2, 2], pop[1, 2] = 0, 30_000                   # side by side: one centre of 60 000
        l2 = run(pop)["l2"]
        self.assertEqual((l2[1, 1], l2[1, 2]), (30, 30))

    def test_rural_classes_and_water(self):
        pop = grid((5, 5))
        pop[0, 0], pop[4, 4], pop[2, 4] = 1000, 100, 10
        water = grid((5, 5))
        water[2, 2] = 0.8
        l2 = run(pop, water=water, settlement=np.ones((5, 5), bool))["l2"]
        self.assertEqual(l2[0, 0], 13)     # rural cluster: >= 300, 500-4 999
        self.assertEqual(l2[4, 4], 12)     # >= 50
        self.assertEqual(l2[2, 4], 11)     # < 50
        self.assertEqual(l2[2, 2], 10)     # water, nobody living there

    def test_semi_dense_far_from_a_centre_suburban_near_one(self):
        pop = grid((9, 20))
        pop[4, 14:20] = 1000               # 6 000 people at 300-1 499 /km²: urban cluster, no core
        self.assertTrue((run(pop)["l2"][4, 14:20] == 22).all())
        pop[0:8, 0:8] = 3000               # a centre 6 km away: still semi-dense
        self.assertTrue((run(pop)["l2"][4, 14:20] == 22).all())
        pop[4, 8:14] = 1000                # joined to the centre's cluster: suburban
        self.assertTrue((run(pop)["l2"][4, 9:20] == 21).all())

    def test_small_holes_in_a_centre_are_filled(self):
        pop = grid((7, 7))
        pop[1:6, 1:6] = 3000
        pop[3, 3] = 0
        l2 = run(pop)["l2"]
        self.assertEqual(l2[3, 3], 30)

    def test_built_up_cells_count_for_a_centre(self):
        pop = grid((7, 7))
        pop[1:6, 1:6] = 3000
        pop[1, 1] = 100                    # sparse, but half of it built up
        built = grid((7, 7))
        built[1, 1] = 600_000
        self.assertEqual(run(pop)["l2"][1, 1], 12)  # a corner: only 3 of 8 neighbours, no smoothing
        self.assertEqual(run(pop, built=built)["l2"][1, 1], 30)

    def test_edge_flag_when_the_cluster_reaches_the_import_edge(self):
        pop = grid((7, 7))
        pop[0:5, 0:5] = 3000
        result = run(pop)
        self.assertTrue(result["edge_effect"][0, 0])
        self.assertEqual(result["cluster_population"][2, 2], 75_000)


class LocalVariantTests(SimpleTestCase):
    """100 m cells: 3 x 3 window over settlement land, settlement-only rules."""

    def setUp(self):
        self.shape = (40, 40)
        self.pop = grid(self.shape)
        self.pop[5:35, 5:35] = 60          # 6 000 /km², 30 x 30 x 60 = 54 000 people
        self.settle = self.pop > 0

    def test_edge_cell_keeps_its_density_next_to_fields(self):
        d_masked = run(self.pop, 100, settlement=self.settle)["density"]
        d_gross = run(self.pop, 100, settlement=self.settle, masked=False)["density"]
        self.assertAlmostEqual(d_masked[5, 5], 6000)
        self.assertAlmostEqual(d_gross[5, 5], 6000 * 4 / 9)   # corner: diluted by fields

    def test_worked_example_three_dwelling_cells_and_a_street(self):
        pop = grid((3, 3))
        pop[1, 1] = pop[1, 2] = pop[2, 1] = 60
        settle = pop > 0
        settle[2, 2] = True                                    # street
        density, gross = degurba.density(pop, grid((3, 3)), settle, 100, 3, True)
        self.assertAlmostEqual(density[1, 1], 180 / 0.04)      # 45 / ha
        self.assertAlmostEqual(gross[1, 1], 180 / 0.09)        # 20 / ha over the whole window

    def test_street_gap_is_bridged(self):
        pop = self.pop.copy()
        pop[:, 20] = 0                                         # a street splits the block
        settle = self.settle.copy()
        self.assertEqual(run(pop, 100, settlement=settle)["l2"][15, 20], 30)
        own = run(pop, 100, settlement=settle, window_cells=1)["l2"]
        self.assertNotEqual(own[15, 10], 30)                   # each half 27 000 < 50 000

    def test_fields_never_join_a_centre(self):
        l2 = run(self.pop, 100, settlement=self.settle)["l2"]
        self.assertEqual(l2[15, 15], 30)
        self.assertNotEqual(l2[4, 15], 30)                     # field next to the edge
        self.assertNotEqual(l2[15, 35], 30)

    def test_park_hole_filled_farmland_hole_kept(self):
        pop = self.pop.copy()
        pop[17:23, 17:23] = 0
        settle = pop > 0
        self.assertNotEqual(run(pop, 100, settlement=settle)["l2"][20, 20], 30)   # farmland
        settle[17:23, 17:23] = True                                                # a park
        self.assertEqual(run(pop, 100, settlement=settle)["l2"][20, 20], 30)


class UnitChainTests(SimpleTestCase):
    def test_city_town_rural(self):
        self.assertEqual(chain.classify_unit({30: 60, 21: 40})[:2], (3, 30))
        self.assertEqual(chain.classify_unit({30: 30, 21: 25, 12: 45})[:2], (2, 21))
        self.assertEqual(chain.classify_unit({23: 20, 22: 20, 12: 60})[:2], (1, 12))

    def test_ties_go_to_the_denser_class(self):
        self.assertEqual(chain.classify_unit({23: 30, 21: 30, 12: 40})[:2], (2, 23))

    def test_empty_unit(self):
        self.assertEqual(chain.classify_unit({}), (None, None, {}))

    def test_rate_is_compound_annual_growth(self):
        self.assertAlmostEqual(chain.urbanization_rate(10, 2020, 12.1, 2022), 10.0)
        self.assertIsNone(chain.urbanization_rate(0, 2020, 5, 2022))
        self.assertIsNone(chain.urbanization_rate(5, 2022, 5, 2022))


def _rect(x0, y0, x1, y1):
    return MultiPolygon(Polygon(((x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0))), srid=SRID)


class _Fixture(TestCase):
    """Two neighborhoods side by side (1 km x 1 km each), origin on the RD grid."""

    X, Y = 250_000, 470_000

    def setUp(self):
        from administrative.models import City, District, Neighborhood, Province

        X, Y = self.X, self.Y
        province = Province.objects.create(ProvinceName="P", geom=_rect(X, Y, X + 2000, Y + 1000))
        self.city = City.objects.create(province=province, cityName="C", geom=_rect(X, Y, X + 2000, Y + 1000))
        district = District.objects.create(id="WK01", city=self.city, districtName="D", geom=_rect(X, Y, X + 2000, Y + 1000))
        self.west = Neighborhood.objects.create(id="BU01", district=district, neighborhoodName="West",
                                                currentPopulation=100, geom=_rect(X, Y, X + 1000, Y + 1000))
        self.east = Neighborhood.objects.create(id="BU02", district=district, neighborhoodName="East",
                                                currentPopulation=50, geom=_rect(X + 1000, Y, X + 2000, Y + 1000))
        # A 40-flat building in cell (50 m, 50 m) and a house with a shop in cell (550 m, 50 m).
        Building.objects.create(id=1, geom=_rect(X + 10, Y + 10, X + 90, Y + 90))
        Building.objects.create(id=2, geom=_rect(X + 510, Y + 10, X + 590, Y + 90))
        Building.objects.create(id=3, geom=_rect(X + 110, Y + 10, X + 190, Y + 90))
        for k in range(40):
            self._property(X + 50, Y + 50, residential=True)
        self._property(X + 550, Y + 50, residential=True)
        self._property(X + 560, Y + 50, residential=False)

    def _property(self, x, y, residential):
        return Property.objects.create(name="p", grossArea=80, geom=Point(x, y, srid=SRID),
                                       usageFunction=["Residential function" if residential else "Shop function"])


class AllocationTests(_Fixture):

    def test_population_is_shared_per_dwelling_never_per_building(self):
        urbanisation.allocate(["BU01", "BU02"], 2025)
        rows = PopulationAllocation.objects.filter(neighborhood=self.west, resolution_m=100, population__gt=0)
        by_cell = {(r.ix - self.X // 100, r.iy - self.Y // 100): (r.population, r.dwellings) for r in rows}
        self.assertAlmostEqual(by_cell[(0, 0)][0], 100 * 40 / 41)
        self.assertEqual(by_cell[(0, 0)][1], 40)
        self.assertAlmostEqual(by_cell[(5, 0)][0], 100 / 41)   # the shop gets no share
        self.assertEqual(by_cell[(5, 0)][1], 1)

    def test_neighborhood_without_dwellings_is_spread_by_area(self):
        urbanisation.allocate(["BU02"], 2025)
        rows = PopulationAllocation.objects.filter(neighborhood=self.east, resolution_m=100)
        self.assertEqual(rows.count(), 100)
        self.assertTrue(all(r.by_area for r in rows))
        self.assertAlmostEqual(sum(r.population for r in rows), 50)

    def test_population_is_conserved_at_both_resolutions(self):
        urbanisation.allocate(["BU01", "BU02"], 2025)
        for r in (100, 1000):
            total = sum(PopulationAllocation.objects.filter(resolution_m=r).values_list("population", flat=True))
            self.assertAlmostEqual(total, 150)

    def test_rebuild_writes_cells_and_units(self):
        summary = urbanisation.rebuild(year=2025)
        self.assertIsNotNone(summary)
        self.assertEqual(UrbanisationCell.objects.filter(resolution_m=100, year=2025).count(), 200)
        self.assertEqual(UrbanisationCell.objects.filter(resolution_m=1000, year=2025).count(), 2)
        cell = UrbanisationCell.objects.get(resolution_m=100, ix=self.X // 100, iy=self.Y // 100)
        self.assertEqual(cell.cell_code, f"E{self.X // 100}N{self.Y // 100}")
        self.assertEqual(cell.dwellings, 40)
        city = Urbanisation.objects.get(level="city", unit_id=str(self.city.pk), resolution_m=100, year=2025)
        self.assertAlmostEqual(city.population, 150)
        self.assertEqual(city.degurba_l1, 1)               # 150 people: rural
        self.assertEqual(Urbanisation.objects.filter(level="neighborhood", year=2025).count(), 4)

    def test_rate_from_two_years(self):
        Urbanisation(level="city", unit_id=str(self.city.pk), resolution_m=100, year=2020).save(
            by_class={21: 10}, urban_area_m2=1e6)
        row = Urbanisation(level="city", unit_id=str(self.city.pk), resolution_m=100, year=2022)
        row.save(by_class={21: 10}, urban_area_m2=1.21e6)
        self.assertAlmostEqual(row.urbanization_rate_pct_yr, 10.0)
        self.assertEqual(row.rate_base_year, 2020)
        urbanisation.mirror_city_rates()
        self.city.refresh_from_db()
        self.assertAlmostEqual(self.city.urbanizationRate, 10.0)


class UrbanisationSignalTests(_Fixture):
    """Receivers keep the grid current once it was built (builtup/signals.py)."""

    def test_nothing_runs_before_the_grid_is_built(self):
        with mock.patch.object(urbanisation, "refresh") as refresh:
            self._property(self.X + 150, self.Y + 50, residential=True)
        refresh.assert_not_called()

    def test_new_dwelling_reallocates_its_neighborhood(self):
        urbanisation.rebuild(year=2025)
        self._property(self.X + 150, self.Y + 50, residential=True)
        cell = UrbanisationCell.objects.get(resolution_m=100, year=2025, ix=self.X // 100 + 1, iy=self.Y // 100)
        self.assertEqual(cell.dwellings, 1)
        self.assertAlmostEqual(cell.population, 100 / 42)

    def test_population_change_updates_units(self):
        urbanisation.rebuild(year=2025)
        self.west.currentPopulation = 200
        self.west.save()
        row = Urbanisation.objects.get(level="neighborhood", unit_id="BU01", resolution_m=100, year=2025)
        self.assertAlmostEqual(row.population, 200)

    def test_attribute_only_save_does_not_refresh(self):
        urbanisation.rebuild(year=2025)
        with mock.patch.object(urbanisation, "refresh") as refresh:
            self.west.neighborhoodName = "West 2"
            self.west.save()
        refresh.assert_not_called()

    def test_bulk_import_refreshes_once(self):
        from importer.batching import deferred_cascades

        urbanisation.rebuild(year=2025)
        with mock.patch.object(urbanisation, "refresh", wraps=urbanisation.refresh) as refresh:
            with deferred_cascades():
                for k in range(5):
                    self._property(self.X + 150 + k, self.Y + 50, residential=True)
                self.east.currentPopulation = 70
                self.east.save()
        self.assertEqual(refresh.call_count, 1)
        self.assertEqual(set(refresh.call_args[0][0]), {"BU01", "BU02"})


class UrbanisationViewTests(_Fixture):
    """Map card endpoints and the dashboard card (builtup/views_degurba.py, urbanisation.dashboard)."""

    def test_info_before_and_after_build(self):
        data = self.client.get("/builtup/degurba/info/").json()
        self.assertFalse(data["built"])
        urbanisation.rebuild(year=2025)
        data = self.client.get("/builtup/degurba/info/").json()
        self.assertTrue(data["built"])
        self.assertEqual(data["resolutions"]["100"]["cells"], 200)
        self.assertEqual(data["cities"][0]["name"], "C")

    def test_calculate_is_staff_only(self):
        from django.contrib.auth.models import User

        self.assertEqual(self.client.post("/builtup/degurba/calculate/").status_code, 403)
        User.objects.create_user("staff", password="x", is_staff=True)
        self.client.login(username="staff", password="x")
        response = self.client.post("/builtup/degurba/calculate/")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["built"])

    def test_dashboard_default_equals_stored_row(self):
        """Parity: with the default controls the card shows the stored Urbanisation row."""
        urbanisation.rebuild(year=2025)
        card = urbanisation.dashboard(self.city, 2025, "prognose", 0.0)
        stored = Urbanisation.objects.get(level="city", unit_id=str(self.city.pk), resolution_m=100, year=2025)
        self.assertFalse(card["whatif"])
        self.assertEqual(card["l2"], stored.degurba_l2)
        self.assertAlmostEqual(card["population"], stored.population)
        recomputed = urbanisation.whatif_unit(self.city, {self.city.pk: 1.0}, 2025)
        self.assertAlmostEqual(sum(recomputed[0].values()), stored.population)
        self.assertAlmostEqual(recomputed[1] / 1e6, stored.urban_area_km2)

    def test_whatif_scales_population_without_writing(self):
        urbanisation.rebuild(year=2025)
        before = list(UrbanisationCell.objects.order_by("pk").values_list("population", "l2"))
        by_class, _ = urbanisation.whatif_unit(self.city, {self.city.pk: 2.0}, 2025)
        self.assertAlmostEqual(sum(by_class.values()), 300)
        self.assertEqual(list(UrbanisationCell.objects.order_by("pk").values_list("population", "l2")), before)



class UrbanisationBackgroundRefreshTests(TestCase):
    """urbanisation.schedule(): outside an import, the refresh runs after the commit in a worker thread."""

    def test_schedule_returns_at_once_and_merges_queued_changes(self):
        import threading
        from unittest import mock

        from django.test import override_settings

        from builtup.calculations import urbanisation
        started, release = threading.Event(), threading.Event()
        calls = []

        def slow_refresh(ids=(), landcover=False, **kwargs):
            calls.append(set(ids))
            started.set()
            release.wait(5)

        with override_settings(DEGURBA_BACKGROUND=True),                 mock.patch.object(urbanisation, "is_built", return_value=True),                 mock.patch.object(urbanisation, "refresh", side_effect=slow_refresh),                 mock.patch("django.db.connection.close"):
            with self.captureOnCommitCallbacks(execute=True):
                urbanisation.schedule([1])
                self.assertEqual(calls, [])          # nothing before the commit
            self.assertTrue(started.wait(5))
            self.assertTrue(urbanisation.refreshing())
            with self.captureOnCommitCallbacks(execute=True):
                urbanisation.schedule([2])           # while the first refresh runs
                urbanisation.schedule([3])
            release.set()
            for _ in range(100):
                if not urbanisation.refreshing():
                    break
                threading.Event().wait(0.05)
        self.assertFalse(urbanisation.refreshing())
        self.assertEqual(calls, [{1}, {2, 3}])       # the two later edits in one refresh
