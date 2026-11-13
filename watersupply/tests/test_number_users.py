"""
DAG edges Total_Population -> NumberUsers, Coverage_WS_Area -> NumberUsers,
NumberUsers -> Coverage_WS and NumberUsers -> Metered_Res_Water: the water users
of a neighborhood are the residents of its properties, the population served
those within the pipe buffer.
"""
from unittest import mock

from django.conf import settings
from django.contrib.gis.geos import LineString, MultiLineString, Point
from django.test import TestCase

from builtup.models import Building, Property
from housing.models import HouseholdSize
from importer.batching import deferred_cascades
from watersupply import signals
from watersupply.models import CoverageWaterSupply, MeteredResidential, PipeNetwork, UsersLocation

from .factories import make_consumption_capita, make_neighborhood, make_polygon, make_users_location

RD = settings.COORDINATE_SYSTEM
X, Y = 257000.0, 470000.0   # centre of the factory neighborhood (1 km square)


class NumberUsersTests(TestCase):
    def setUp(self):
        self.hood = make_neighborhood()
        self.city = self.hood.district.city
        self.building = Building.objects.create(
            id=1, buildingType="residential", geom=make_polygon(X, Y, 450))
        HouseholdSize.objects.create(city=self.city, year=2025, population=100_000, households=50_000)  # 2.0
        # two homes at y = Y + 100, one at y = Y - 300
        self.near = [self._dwelling(X - 200, Y + 100), self._dwelling(X + 200, Y + 100)]
        self.far = self._dwelling(X, Y - 300)

    def _dwelling(self, x, y, usage=("Residential function",)):
        return Property.objects.create(name="p", grossArea=80, usageFunction=list(usage),
                                       geom=Point(x, y, srid=RD))

    def _pipe(self, y=Y + 200):
        line = LineString((X - 400, y), (X + 400, y), srid=RD)
        return PipeNetwork.objects.create(geom=MultiLineString(line, srid=RD), length_km=0)

    def _users(self):
        return UsersLocation.objects.get(neighborhood=self.hood)

    def test_users_location_is_created_and_counts_the_residents(self):
        users = self._users()                    # created by the dwelling receivers
        self.assertEqual(users.usersTotal, 6)    # 3 homes x 2.0
        self.assertEqual(users.ResidentialUsers, 6)
        self.assertEqual(users.populationServed, 0)   # no pipes yet
        self.assertEqual(users.buffer_m, 50.0)

    def test_population_served_is_the_residents_within_the_pipe_buffer(self):
        pipe = self._pipe()
        CoverageWaterSupply.objects.create(city=self.city, year=2025, buffer_m=150,
                                           coveredArea_km2=0, coveragePCT=0)
        users = self._users()
        self.assertEqual(users.buffer_m, 150)
        self.assertEqual(users.populationServed, 4)   # the two homes 100 m from the pipe
        coverage = CoverageWaterSupply.objects.get(city=self.city)
        self.assertEqual((coverage.population_served, coverage.population_total), (4, 6))
        self.assertEqual((coverage.households_covered, coverage.households_total), (2, 3))
        self.assertAlmostEqual(coverage.coveragePCT, 66.7)

        pipe.geom = MultiLineString(LineString((X - 400, Y - 250), (X + 400, Y - 250), srid=RD), srid=RD)
        pipe.save()                                   # moved next to the far home
        self.assertEqual(self._users().populationServed, 2)
        pipe.delete()
        self.assertEqual(self._users().populationServed, 0)
        self.assertEqual(CoverageWaterSupply.objects.get(city=self.city).coveragePCT, 0)

    def test_a_smaller_coverage_buffer_re_derives_the_users(self):
        self._pipe()
        coverage = CoverageWaterSupply.objects.create(city=self.city, year=2025, buffer_m=500,
                                                      coveredArea_km2=0, coveragePCT=0)
        self.assertEqual(self._users().populationServed, 6)
        coverage.buffer_m = 50
        coverage.save()                               # terminates: the refresh re-saves it once
        self.assertEqual(self._users().populationServed, 0)
        self.assertEqual(self._users().buffer_m, 50)

    def test_household_size_change_updates_the_users(self):
        HouseholdSize.objects.create(city=self.city, year=2026, population=100_000, households=40_000)  # 2.5
        self.assertEqual(self._users().usersTotal, 8)   # round(3 x 2.5)

    def test_a_shop_has_no_users(self):
        self._dwelling(X, Y, usage=("Shop function",))
        self.assertEqual(self._users().usersTotal, 6)

    def test_metered_billing_follows_the_population_served(self):
        make_consumption_capita(city=self.city, year=2025, consumption_capita_L_d=100.0)
        meters = MeteredResidential.objects.create(
            userLocation=self._users(), installed_meters=10, functional_meters=10, collected_meters=10,
            userTariff_EUR_m3=1.0, userAffordability_PCT=3.0)
        self.assertIsNone(meters.consumption_m3_yr)   # nobody served yet
        CoverageWaterSupply.objects.create(city=self.city, year=2025, buffer_m=500,
                                           coveredArea_km2=0, coveragePCT=0)
        self._pipe()
        meters.refresh_from_db()
        self.assertAlmostEqual(meters.consumption_m3_yr, 0.1 * 365 * 6)

    def test_deferred_import_refreshes_each_neighborhood_once(self):
        with mock.patch.object(signals, '_resave', wraps=signals._resave) as resave:
            with deferred_cascades():
                for i in range(5):
                    self._dwelling(X - 400 + i * 10, Y + 400)
        refreshed = [obj for call in resave.call_args_list for obj in call.args[0]
                     if isinstance(obj, UsersLocation)]
        self.assertEqual(len(refreshed), 1)
        self.assertEqual(self._users().usersTotal, 16)

    def _unserved_ids(self, **params):
        import json
        response = self.client.get('/watersupply/unserved/', params)
        self.assertEqual(response.status_code, 200)
        return {f['properties']['id'] for f in json.loads(response.content)['features']}

    def test_the_map_shows_the_homes_outside_the_pipe_buffer(self):
        everyone = {p.pk for p in self.near} | {self.far.pk}
        self.assertEqual(self._unserved_ids(), everyone)          # no pipes yet
        self._pipe()
        CoverageWaterSupply.objects.create(city=self.city, year=2025, buffer_m=150,
                                           coveredArea_km2=0, coveragePCT=0)
        self.assertEqual(self._unserved_ids(), {self.far.pk})    # the city's buffer, not the default
        self._dwelling(X, Y, usage=("Shop function",))            # no residents: never shown
        self.assertEqual(self._unserved_ids(), {self.far.pk})
        self.assertEqual(self._unserved_ids(bbox='0,0,1,1'), set())   # outside the view
        self.assertEqual(self.client.get('/watersupply/unserved/', {'bbox': 'x'}).status_code, 400)


class StoredUsersTests(TestCase):
    def test_without_properties_the_supplied_counts_are_kept(self):
        users = make_users_location(usersTotal=500, populationServed=1200)
        users.refresh_from_db()
        self.assertEqual((users.usersTotal, users.populationServed), (500, 1200))
        self.assertIsNone(users.buffer_m)
