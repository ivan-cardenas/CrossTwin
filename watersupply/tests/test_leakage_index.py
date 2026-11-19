"""
ILI = CARL / UARL with the IWA UARL (Lambert et al. 1999), stored per year in
LeakageIndex. DAG edges: Real_Losses -> ILI, Network -> ILI.
"""
from unittest import mock

from django.conf import settings
from django.contrib.gis.geos import LineString, MultiLineString
from django.test import SimpleTestCase, TestCase

from importer.batching import deferred_cascades
from watersupply import signals
from watersupply.calculations import chain
from watersupply.calculations.indicators import calculate_nrw
from watersupply.models import CoverageWaterSupply, LeakageIndex, NonRevenueWater, PipeNetwork

from .factories import make_city, make_neighborhood, make_users_location

RD = settings.COORDINATE_SYSTEM
X, Y = 257000.0, 470000.0   # centre of the factory city ([X-500, X+500] x [Y-500, Y+500])

# One city (1 km square) with 1000 connections at 40 m; a 2 km pipe with 500 m inside it.
# city:  (18 x 0.5 + 0.8 x 1000 + 25 x 1000 x 5 m / 1000) x 40 m / 1000 = 37.36 m³/d
# rest:  18 x 1.5 km x 30 m (default pressure) / 1000                    =  0.81 m³/d
CITY_UARL = 37.36
REST_UARL = 0.81


def make_pipe(length_m=2000.0, x0=X, y=Y):
    line = LineString((x0, y), (x0 + length_m, y), srid=RD)
    return PipeNetwork.objects.create(geom=MultiLineString(line, srid=RD), length_km=0)


class UarlEquationTests(SimpleTestCase):
    def test_iwa_uarl_in_m3_per_day(self):
        # (18 x 100 + 0.8 x 5000 + 25 x 25) x 30 / 1000
        self.assertAlmostEqual(chain.uarl_m3_d(100, 5000, 25, 30), 192.75)

    def test_ili_is_carl_over_uarl(self):
        self.assertEqual(chain.ili(385.5, 192.75), 2.0)
        self.assertIsNone(chain.ili(100, 0))
        self.assertIsNone(chain.ili(None, 50))

    def test_reliability_range(self):
        self.assertTrue(chain.uarl_reliable(100, 5000, 30))
        self.assertFalse(chain.uarl_reliable(100, 2000, 30))    # < 3000 connections
        self.assertFalse(chain.uarl_reliable(500, 5000, 30))    # 10 connections/km
        self.assertFalse(chain.uarl_reliable(100, 5000, 20))    # pressure below 25 m


class NetworkFixture:
    def setUp(self):
        self.pipe = make_pipe()
        self.city = make_city()
        make_users_location(make_neighborhood(city=self.city), usersTotal=1000)
        self.coverage = CoverageWaterSupply.objects.create(
            city=self.city, year=2024, coveredArea_km2=0, coveragePCT=0, avg_pressure_m=40)

    def _loss(self, code, quantity, year=2024):
        pipe = self.pipe if code in NonRevenueWater.REAL_CHOICES else None
        return NonRevenueWater.objects.create(
            year=year, specificLoss=code, loss_Quantity_m3=quantity,
            WaterCost_EUR_day=quantity * 0.5, UnavoidableLossses_PCT=25, pipe=pipe)


class LeakageIndexTests(NetworkFixture, TestCase):
    def test_connections_come_from_coverage(self):
        self.coverage.refresh_from_db()
        self.assertEqual(self.coverage.households_covered, 1000)

    def test_real_loss_creates_the_years_index(self):
        """DAG edge: Real_Losses -> ILI."""
        self._loss('LP', 100)
        row = LeakageIndex.objects.get(year=2024)
        self.assertAlmostEqual(row.uarl_m3_d, CITY_UARL + REST_UARL, places=3)
        self.assertEqual(row.carl_m3_d, 100)
        self.assertEqual(row.ILI, round(100 / (CITY_UARL + REST_UARL), 2))
        self.assertEqual(row.connections, 1000)
        self.assertAlmostEqual(row.mains_km, 2.0)
        self.assertFalse(row.uarl_reliable)        # 1000 connections: below the IWA range
        city_part, rest = row.city_inputs
        self.assertEqual(city_part['city_id'], self.city.pk)
        self.assertEqual(city_part['pressure_m'], 40)
        self.assertEqual(city_part['coverage_year'], 2024)
        self.assertIsNone(rest['city_id'])

    def test_apparent_losses_do_not_enter_the_ili(self):
        self._loss('CM', 500)
        self.assertFalse(LeakageIndex.objects.exists())
        self._loss('LP', 100)
        self._loss('CM', 900)
        self.assertEqual(LeakageIndex.objects.get(year=2024).carl_m3_d, 100)

    def test_deleting_the_last_real_loss_empties_the_ili(self):
        self._loss('LP', 100).delete()
        row = LeakageIndex.objects.get(year=2024)
        self.assertIsNone(row.carl_m3_d)
        self.assertIsNone(row.ILI)

    def test_editing_a_citys_pressure_moves_the_ili(self):
        """DAG edge: Network -> ILI (the city's editable average pressure)."""
        self._loss('LP', 100)
        self.coverage.refresh_from_db()
        self.coverage.avg_pressure_m = 60
        self.coverage.save()
        row = LeakageIndex.objects.get(year=2024)
        self.assertAlmostEqual(row.uarl_m3_d, CITY_UARL * 60 / 40 + REST_UARL, places=3)

    def test_a_new_pipe_moves_the_latest_ili(self):
        """DAG edge: Network -> ILI (mains length)."""
        self._loss('LP', 100)
        make_pipe(length_m=1000.0, y=Y + 5000)     # 1 km outside every city
        row = LeakageIndex.objects.get(year=2024)
        self.assertAlmostEqual(row.mains_km, 3.0)
        self.assertAlmostEqual(row.uarl_m3_d, CITY_UARL + REST_UARL + 18 * 1.0 * 30 / 1000, places=3)

    def test_missing_connections_keep_the_stored_uarl(self):
        self._loss('LP', 100)
        CoverageWaterSupply.objects.all().delete()   # queryset delete: no signal
        row = LeakageIndex.objects.get(year=2024)
        row.save()
        self.assertAlmostEqual(row.uarl_m3_d, CITY_UARL + REST_UARL, places=3)
        self.assertEqual(row.ILI, round(100 / (CITY_UARL + REST_UARL), 2))

    def test_bulk_pipe_import_refreshes_the_index_once(self):
        self._loss('LP', 100)
        with mock.patch.object(signals, '_resave', wraps=signals._resave) as resave:
            with deferred_cascades():
                for i in range(3):
                    make_pipe(length_m=500.0, y=Y + 5000 + 100 * i)
        leakage_calls = [c for c in resave.call_args_list
                         if getattr(c.args[0], 'model', None) is LeakageIndex]
        self.assertEqual(len(leakage_calls), 1)
        self.assertAlmostEqual(LeakageIndex.objects.get(year=2024).mains_km, 3.5)


class DashboardIsADeviationFromTheBaselineTests(NetworkFixture, TestCase):
    """The dashboard shows the stored ILI network-wide and the same equation per unit."""

    def setUp(self):
        super().setUp()
        self._loss('LP', 100)

    def test_network_wide_equals_stored(self):
        row = LeakageIndex.objects.get(year=2024)
        nrw = calculate_nrw(2024)
        self.assertEqual(nrw['ili'], row.ILI)
        self.assertEqual(nrw['uarl_m3_d'], row.uarl_m3_d)

    def test_city_uses_its_own_mains_connections_and_pressure(self):
        nrw = calculate_nrw(2024, self.city)
        self.assertAlmostEqual(nrw['uarl_m3_d'], CITY_UARL, places=3)
        self.assertEqual(nrw['ili'], round(25 / CITY_UARL, 2))   # 100 m³/d x 0.25 of the pipe inside
