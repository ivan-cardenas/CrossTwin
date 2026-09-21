from unittest import mock

from django.conf import settings
from django.contrib.gis.geos import MultiPoint, Point
from django.core.exceptions import ValidationError
from django.db import models
from django.test import TestCase

from administrative.models import City, Province
from builtup.models import Property
from Energy.models import ElectricityCost
from housing.models import Rentals
from physicalEnv.models import EnvironmentalCosts
from watersupply.models import (
    AreaAffectedDrought, AvailableFreshWater, ConsumptionCapita, ExtractionWater,
    ImportedWater, NonRevenueWater, OPEX, SupplySecurity, TotalWaterDemand,
    TotalWaterProduction,
)

from .factories import (
    make_city, make_consumption_capita, make_neighborhood, make_polygon, make_province,
)

RD = settings.COORDINATE_SYSTEM
X, Y = 257000.0, 470000.0  # centre of the factory polygon (inside every factory geometry)


def make_source(**kwargs):
    defaults = dict(
        SourceName="Test source", geom=make_polygon(),
        infiltrationRate_cm_h=1.0, infiltrationDepth_cm=10.0,
        totalQuantity_Mm3=100.0, yield_Mm3_year=10.0,
    )
    defaults.update(kwargs)
    return AvailableFreshWater.objects.create(**defaults)


def make_well(**kwargs):
    defaults = dict(
        geom=MultiPoint(Point(X, Y), srid=RD), stationName="Well 1",
        pumpflow_m3_s=0.1, pumpMaxFlow_m3_s=0.2, OperationTime_h_day=10.0,
        depth_m=50.0, pumpEfficiency=70.0, pumpEnergyRate_kWh_h=50.0,
        pumpEmmissionFactor_kg_CO2_kWh=0.4,
        labor_EUR_m3=0.01, energy_EUR_m3=0.01, chemicals_EUR_m3=0.01, tax_EUR_m3=0.01,
        current_extraction_Mm3_yr=1.0,
    )
    defaults.update(kwargs)
    return ExtractionWater.objects.create(**defaults)


class ProvinceSaveTests(TestCase):
    def test_new_province_without_population_saves(self):
        province = make_province()  # used to raise TypeError (None division)
        self.assertEqual(province.currentPopulation, 0)
        self.assertAlmostEqual(province.area_km2, 1.0, places=3)

    def test_population_defaults_to_sum_of_cities(self):
        province = make_province()
        make_city(province=province, currentPopulation=100)
        make_city(province=province, currentPopulation=250, cityName="Other")
        province.currentPopulation = None
        province.save()
        self.assertEqual(province.currentPopulation, 350)


class ConsumptionAndDemandTests(TestCase):
    def test_total_consumption_is_calculated(self):
        city = make_city(currentPopulation=10000)
        cc = make_consumption_capita(city=city, consumption_capita_L_d=120.0)
        self.assertAlmostEqual(cc.total_consumption_m3_yr, 120 / 1000 * 10000 * 365)

    def test_demand_is_in_million_m3(self):
        city = make_city(currentPopulation=10000)
        make_consumption_capita(city=city, year=2024, consumption_capita_L_d=120.0)
        demand = TotalWaterDemand.objects.create(city=city, year=2024, demandDay=0)
        self.assertAlmostEqual(demand.demandDay, 10000 * 120 / 1e9)  # Mm3/day
        self.assertAlmostEqual(demand.demandYR, demand.demandDay * 365)

    def test_demand_without_consumption_record_is_a_validation_error(self):
        city = make_city()
        with self.assertRaises(ValidationError):
            TotalWaterDemand.objects.create(city=city, year=2024, demandDay=0)

    def test_population_cascade_refreshes_consumption_and_demand(self):
        """Neighborhood -> District -> City uses update(); the custom signal must still reach water."""
        city = make_city(currentPopulation=10000)
        cc = make_consumption_capita(city=city, year=2024, consumption_capita_L_d=120.0)
        demand = TotalWaterDemand.objects.create(city=city, year=2024, demandDay=0)

        make_neighborhood(city=city, currentPopulation=1200)

        city.refresh_from_db()
        self.assertEqual(city.currentPopulation, 1200)
        cc.refresh_from_db()
        demand.refresh_from_db()
        self.assertAlmostEqual(cc.total_consumption_m3_yr, 120 / 1000 * 1200 * 365)
        self.assertAlmostEqual(demand.demandDay, 1200 * 120 / 1e9)

    def test_changing_consumption_refreshes_demand(self):
        city = make_city(currentPopulation=10000)
        cc = make_consumption_capita(city=city, year=2024, consumption_capita_L_d=120.0)
        demand = TotalWaterDemand.objects.create(city=city, year=2024, demandDay=0)
        cc.consumption_capita_L_d = 200.0
        cc.save()
        demand.refresh_from_db()
        self.assertAlmostEqual(demand.demandDay, 10000 * 200 / 1e9)


class SupplySecurityTests(TestCase):
    def test_supply_security_follows_demand_and_production(self):
        city = make_city(currentPopulation=10000)
        make_consumption_capita(city=city, year=2024, consumption_capita_L_d=120.0)  # 1200 m3/d
        TotalWaterDemand.objects.create(city=city, year=2024, demandDay=0)
        security = SupplySecurity.objects.create(
            city=city, year=2024, supply_security_pct=0, security_goal_pct=90, service_time_hours=0)
        self.assertEqual(security.supply_security_pct, 0)  # no production yet: values are kept

        ImportedWater.objects.create(sourceName="Imp", quantity_m3_d=600, price_EUR_m3=1.0)

        security.refresh_from_db()
        self.assertAlmostEqual(security.supply_security_pct, 50.0)
        self.assertAlmostEqual(security.service_time_hours, 12.0)

    def test_full_service_when_production_covers_demand(self):
        city = make_city(currentPopulation=10000)
        make_consumption_capita(city=city, year=2024, consumption_capita_L_d=120.0)
        TotalWaterDemand.objects.create(city=city, year=2024, demandDay=0)
        ImportedWater.objects.create(sourceName="Imp", quantity_m3_d=2400, price_EUR_m3=1.0)
        security = SupplySecurity.objects.create(
            city=city, year=2024, supply_security_pct=0, security_goal_pct=90, service_time_hours=0)
        self.assertAlmostEqual(security.supply_security_pct, 200.0)
        self.assertEqual(security.service_time_hours, 24)


class ExtractionAndProductionTests(TestCase):
    def setUp(self):
        self.source = make_source()
        EnvironmentalCosts.objects.create(price_EUR_kg_CO2=0.05, price_EUR_droughtDamage_m3=0.02)

    def test_extraction_derives_source_emissions_and_costs(self):
        well = make_well()
        self.assertEqual(well.source, self.source)  # assigned from location
        self.assertAlmostEqual(well.pumpEmissionRate_kg_CO2_h, 20.0)
        self.assertAlmostEqual(well.pumpEmission_day_kg_CO2, 200.0)
        self.assertAlmostEqual(well.pumpEmission_year_kg_CO2, 73000.0)
        self.assertAlmostEqual(well.opex_EUR_m3, 0.04)
        self.assertAlmostEqual(well.co2_cost_EUR_m3, 200.0 / (0.1 * 10 * 3600) * 0.05)
        self.assertAlmostEqual(well.drought_damage_EUR_m3, 0.02)

    def test_explicit_source_is_not_overridden(self):
        other = make_source(SourceName="Elsewhere", geom=make_polygon(x=300000.0, y=400000.0))
        well = make_well(source=other)
        self.assertEqual(well.source, other)

    def test_extraction_outside_any_source_is_a_validation_error(self):
        with self.assertRaises(ValidationError):
            make_well(geom=MultiPoint(Point(1000.0, 1000.0), srid=RD))

    def test_production_uses_3600_seconds_per_hour_and_default_price(self):
        make_well()
        production = TotalWaterProduction.objects.create(year=2024, productionDay=0)
        production.source.add(self.source)  # m2m signal recalculates

        production.refresh_from_db()
        self.assertAlmostEqual(production.productionDay, 0.1 * 10 * 3600 / 1e6)  # Mm3/day
        self.assertAlmostEqual(production.productionYR, production.productionDay * 365)
        self.assertAlmostEqual(production.costDay, 50 * 10 * TotalWaterProduction.DEFAULT_ELECTRICITY_EUR_KWH)

    def test_production_uses_province_electricity_price(self):
        province = make_province()
        ElectricityCost.objects.create(province=province, year=2024, cost_EUR_kWh=0.30)
        make_well()
        production = TotalWaterProduction.objects.create(year=2024, productionDay=0)
        production.source.add(self.source)
        production.refresh_from_db()
        self.assertAlmostEqual(production.costDay, 50 * 10 * 0.30)

    def test_new_well_updates_existing_production(self):
        production = TotalWaterProduction.objects.create(year=2024, productionDay=0)
        production.source.add(self.source)
        production.refresh_from_db()
        self.assertEqual(production.productionDay, 0)

        make_well()
        production.refresh_from_db()
        self.assertAlmostEqual(production.productionDay, 0.0036)

    def test_inactive_wells_are_excluded(self):
        make_well(is_active=False)
        production = TotalWaterProduction.objects.create(year=2024, productionDay=0)
        production.source.add(self.source)
        production.refresh_from_db()
        self.assertEqual(production.productionDay, 0)

    def test_imported_water_is_added_when_flagged(self):
        imported = ImportedWater.objects.create(sourceName="Imp", quantity_m3_d=1000, price_EUR_m3=2.0)
        production = TotalWaterProduction.objects.create(year=2024, productionDay=0, imported_boolean=True)
        production.source_imported.add(imported)
        production.refresh_from_db()
        self.assertAlmostEqual(production.productionDay, 1000 / 1e6)
        self.assertAlmostEqual(production.costDay, 1000 * 2.0)


class OpexTests(TestCase):
    def setUp(self):
        self.source = make_source()

    def test_opex_is_calculated_from_extraction(self):
        opex = OPEX.objects.create(year=2024, UnitaryOPEX_EUR_m3=0, totalOPEX_EUR=0)
        self.assertEqual(opex.totalOPEX_EUR, 0)  # no cost data: supplied values kept

        make_well()  # 0.04 EUR/m3 x 1 Mm3/yr
        opex.refresh_from_db()
        self.assertAlmostEqual(opex.totalOPEX_EUR, 0.04 * 1e6)
        self.assertAlmostEqual(opex.UnitaryOPEX_EUR_m3, 0.04)

    def test_imported_water_and_treatment_are_included(self):
        from watersupply.models import WaterTreatment
        make_well()
        ImportedWater.objects.create(sourceName="Imp", quantity_m3_d=1000, price_EUR_m3=2.0)
        WaterTreatment.objects.create(
            year=2024, UnitaryOPEX_EUR_m3=0.10, treatment_efficiency=98.0,
            samplesWaterQuality_OK=9, samplesWaterQualityTaken=10, EnergyConsumption_MW_day=1.0,
            acceptanceRate=90.0, geom=MultiPoint(Point(X, Y), srid=RD))
        opex = OPEX.objects.create(year=2024, UnitaryOPEX_EUR_m3=0, totalOPEX_EUR=0)

        volume = 1e6 + 1000 * 365                      # extraction + imported, m3/yr
        expected = 0.04 * 1e6 + 1000 * 365 * 2.0 + 0.10 * volume
        self.assertAlmostEqual(opex.totalOPEX_EUR, expected)
        self.assertAlmostEqual(opex.UnitaryOPEX_EUR_m3, expected / volume)

    def test_only_the_latest_year_is_refreshed_by_a_state_change(self):
        old = OPEX.objects.create(year=2020, UnitaryOPEX_EUR_m3=1.0, totalOPEX_EUR=1.0)
        new = OPEX.objects.create(year=2024, UnitaryOPEX_EUR_m3=0, totalOPEX_EUR=0)
        make_well()
        old.refresh_from_db()
        new.refresh_from_db()
        self.assertEqual(old.totalOPEX_EUR, 1.0)              # historical snapshot untouched
        self.assertAlmostEqual(new.totalOPEX_EUR, 0.04 * 1e6)


class NonRevenueWaterTests(TestCase):
    def _loss(self, code, quantity, unavoidable_pct):
        return NonRevenueWater.objects.create(
            year=2024, specificLoss=code, loss_Quantity_m3=quantity,
            WaterCost_EUR_day=quantity * 0.5, UnavoidableLossses_PCT=unavoidable_pct)

    def test_ili_of_sibling_records_follows_new_losses(self):
        first = self._loss('LP', 100, 25)   # CARL 100 / UARL 25 = 4.0
        self.assertEqual(first.ILI, 4.0)
        self._loss('LS', 100, 75)           # CARL 200 / UARL 100 = 2.0
        first.refresh_from_db()
        self.assertEqual(first.ILI, 2.0)

    def test_apparent_losses_have_no_ili(self):
        self.assertIsNone(self._loss('CM', 100, 25).ILI)


class AreaAffectedDroughtTests(TestCase):
    def test_area_and_province_are_derived_from_geometry(self):
        province = make_province()
        area = AreaAffectedDrought.objects.create(geom=make_polygon(), areaName="Dry", year=2024, areaAffected_km2=0)
        self.assertAlmostEqual(area.areaAffected_km2, 1.0, places=3)
        self.assertEqual(area.Province, province)


class RentalsTests(TestCase):
    def test_price_to_rent_uses_sale_price_then_listing_price(self):
        # Property.save() cannot build a full fixture here, so only Model.save is stubbed.
        with mock.patch.object(models.Model, 'save'):
            rental = Rentals(monthlyRent=1000.0, property=Property(salePrice_EUR=240000.0))
            rental.save()
            self.assertEqual(rental.annualRent, 12000.0)
            self.assertEqual(rental.priceToRentRatio, 20.0)

            rental = Rentals(monthlyRent=1000.0, property=Property(listingPrice_EUR=120000.0))
            rental.save()
            self.assertEqual(rental.priceToRentRatio, 10.0)
