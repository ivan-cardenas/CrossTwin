"""
House prices (Phase 3 of docs/ACCESSIBILITY_PLAN.md): CBS WOZ per m2, the NVM
report parser and the edge Market_Reports -> House_Price_Index.
"""
import datetime
import tempfile
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.contrib.gis.geos import Point
from django.test import SimpleTestCase, TestCase

from builtup.models import Accessibility, Building, Property
from watersupply.tests.factories import make_city, make_district, make_neighborhood, make_polygon

from housing import signals
from housing.calculations import chain, prices, woz
from housing.models import HousePriceIndex, NVMMarketReport, NVMRegionMapping, WOZValue
from importer import cbs_woz, nvm_reports

SRID = settings.COORDINATE_SYSTEM
DWELLING = ["Residential function"]


# ── a report page as pdfplumber reads it (layout of NVM's 3e kwartaal 2026 overview) ──

PAGE = """Transactiecijfers
NVM Woningmarkt kwartaalcijfers Delft en Westland | 3e kwartaal 2026
Aantal transacties Aantal transacties 2025-3 2026-2 2026-3 %-jr. %-kw Aantal transacties
Het aantal transacties laat zien Tussenwoning 10.314 11.699 10.359 0% -11% 50.000
Totaal 41.497 45.420 41.732 1% -8% 2021 2022 2023 2024 2025 2026
Transactieprijs Transactieprijs 2025-3 2026-2 2026-3 %-jr. %-kw Prijsontwikkeling t.o.v. jaar eerder
De transactieprijs toont de (mediane) Tussenwoning 463 476 468 1,2% -1,6% 30%
Totaal 497 508 503 1,8% -1,3% 2021 2022 2023 2024 2025 2026
Transactieprijs per m2 Transactieprijs m2 2025-3 2026-2 2026-3 %-jr. %-kw Transactieprijsontwikkeling
Totaal 4.694 4.815 4.771 1,7% -1,1% 2021 2022 2023 2024 2025 2026
Verkooptijd Verkooptijd 2025-3 2026-2 2026-3 Verkooptijd in dagen
Totaal 29 27 31 2021 2022 2023 2024 2025 2026
Vraagprijs Vraagprijs 2025-3 2026-2 2026-3 %-jr. %-kw Vraagprijsontwikkeling t.o.v. jaar eerder
Totaal 594 595 595 2,0% 0,6% 2021 2022 2023 2024 2025 2026
Vraag-verkoopprijsverschil Vraag-verkoopprijs 2025-3 2026-2 2026-3 Vraag-verkoopprijs verschil
Totaal 5,0% 4,6% -0,1% 2021 2022 2023 2024 2025 2026
% Boven vraagprijs verkocht > vraagprijs verkocht 2025-3 2026-2 2026-3 % boven de vraagprijs verkocht
Totaal 71% 72% 66% 2021 2022 2023 2024 2025 2026
"""


def make_pdf(path, text):
    """A one-page PDF of Helvetica text lines, written by hand (no PDF library needed)."""
    lines = [line for line in text.splitlines() if line.strip()]
    content = "BT /F1 8 Tf 1 0 0 1 20 800 Tm 10 TL\n" + "".join(
        f"({line.replace('\\', '').replace('(', '[').replace(')', ']')}) '\n" for line in lines) + "ET"
    objects = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 900 842] /Contents 4 0 R "
        "/Resources << /Font << /F1 5 0 R >> >> >>",
        f"<< /Length {len(content)} >>\nstream\n{content}\nendstream",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
    ]
    out, offsets = b"%PDF-1.4\n", []
    for number, body in enumerate(objects, 1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n{body}\nendobj\n".encode("latin-1")
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    out += "".join(f"{offset:010d} 00000 n \n" for offset in offsets).encode()
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    Path(path).write_bytes(out)


class PriceEquationTests(SimpleTestCase):
    def test_woz_per_sqm_pinned(self):
        self.assertAlmostEqual(chain.woz_per_sqm(450_000, 100.0), 4500.0)

    def test_woz_per_sqm_needs_a_plausible_area(self):
        self.assertIsNone(chain.woz_per_sqm(450_000, None))
        self.assertIsNone(chain.woz_per_sqm(None, 100.0))
        self.assertIsNone(chain.woz_per_sqm(450_000, chain.MIN_DWELLING_AREA_SQM - 1))
        self.assertIsNone(chain.woz_per_sqm(450_000, chain.WOZ_AREA_MAX_SQM + 1))

    def test_valuation_year_is_the_year_before_the_table(self):
        self.assertEqual(chain.woz_valuation_year(2024), 2023)

    def test_annual_price_needs_four_quarters(self):
        self.assertAlmostEqual(chain.annual_price_per_sqm([4000, 4100, 4200, 4300]), 4150.0)
        self.assertIsNone(chain.annual_price_per_sqm([4000, 4100, 4200]))
        self.assertIsNone(chain.annual_price_per_sqm([4000, None, 4200, 4300]))

    def test_price_index_pinned(self):
        self.assertAlmostEqual(chain.price_index(4800.0, 4000.0), 120.0)
        self.assertEqual(chain.price_index(4000.0, 4000.0), 100.0)
        self.assertIsNone(chain.price_index(None, 4000.0))
        self.assertIsNone(chain.price_index(4800.0, 0))

    def test_index_from_prices_uses_the_earliest_year_as_base(self):
        record = prices.index_from_prices({2024: 4500.0, 2023: 4000.0, 2025: 5000.0}, 2025)
        self.assertEqual(record["base_year"], 2023)
        self.assertAlmostEqual(record["index"], 125.0)
        self.assertIsNone(prices.index_from_prices({2023: 4000.0}, 2024))


class NVMParserTests(SimpleTestCase):
    def test_numbers_are_dutch(self):
        self.assertEqual(nvm_reports.parse_number("10.314"), 10314.0)
        self.assertEqual(nvm_reports.parse_number("1,2%"), 1.2)
        self.assertEqual(nvm_reports.parse_number("-0,1%"), -0.1)
        self.assertEqual(nvm_reports.parse_number("25"), 25.0)
        self.assertIsNone(nvm_reports.parse_number("abc"))

    def test_report_page_is_read_into_records(self):
        region, report, records = nvm_reports.parse_text([PAGE])
        self.assertEqual(region, "Delft en Westland")
        self.assertEqual(report, (2026, 3))
        by_key = {(r["year"], r["quarter"], r["dwellingType"]): r for r in records}
        self.assertEqual(len(by_key), 6)            # 3 quarters x {Tussenwoning, Totaal}
        total = by_key[(2026, 3, "Totaal")]
        self.assertEqual(total["transactions"], 41732)
        self.assertEqual(total["medianPrice_EUR"], 503000)
        self.assertEqual(total["pricePerSqm_EUR"], 4771.0)
        self.assertEqual(total["daysOnMarket"], 31.0)
        self.assertEqual(total["askingGap_pct"], -0.1)
        self.assertEqual(total["aboveAsking_pct"], 66.0)
        self.assertEqual(by_key[(2025, 3, "Totaal")]["pricePerSqm_EUR"], 4694.0)
        self.assertEqual(by_key[(2026, 2, "Tussenwoning")]["transactions"], 11699)

    def test_asking_side_figures_are_ignored(self):
        _, _, records = nvm_reports.parse_text([PAGE])
        # the "Vraagprijs" block (595) must not leak into any field
        self.assertNotIn(595000, [r.get("medianPrice_EUR") for r in records])
        self.assertNotIn(595.0, [r.get("pricePerSqm_EUR") for r in records])

    def test_unknown_layout_gives_nothing(self):
        region, report, records = nvm_reports.parse_text(["Marktoverzicht\nNederland"])
        self.assertEqual((region, report, records), (None, None, []))

    def test_pdf_text_is_extracted_and_parsed(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "regio-test.pdf"
            make_pdf(path, PAGE)
            _, report, records = nvm_reports.parse_text(nvm_reports.extract_pages(path))
        self.assertEqual(report, (2026, 3))
        self.assertEqual(len(records), 6)

    def test_region_rows_join_wrapped_names(self):
        rows = [["Nr", "COROP-gebied", "Gemeenten"],
                ["26", "Agglomeratie 's-\nGravenhage", "'s-Gravenhage, Hendrik-Ido-\nAmbacht, Wassenaar"],
                ["27", "Delft en Westland", "Delft, Westland"]]
        self.assertEqual(nvm_reports.parse_region_rows(rows), [
            (26, "Agglomeratie 's-Gravenhage", ["'s-Gravenhage", "Hendrik-Ido-Ambacht", "Wassenaar"]),
            (27, "Delft en Westland", ["Delft", "Westland"]),
        ])


class NVMIngestTests(TestCase):
    def _pdf(self, folder, name, text):
        path = Path(folder) / name
        make_pdf(path, text)
        return path

    def test_report_is_stored_with_its_provenance(self):
        with tempfile.TemporaryDirectory() as folder:
            path = self._pdf(folder, "regio-delft.pdf", PAGE)
            created, updated, kept = nvm_reports.ingest_report(path)
            sha = nvm_reports.sha256_of(path)
        self.assertEqual((created, updated, kept), (6, 0, 0))
        row = NVMMarketReport.objects.get(region="Delft en Westland", year=2026, quarter=3, dwellingType="Totaal")
        self.assertEqual(row.pricePerSqm_EUR, 4771.0)
        self.assertEqual((row.reportYear, row.reportQuarter), (2026, 3))
        self.assertEqual(row.pdf_sha256, sha)
        self.assertEqual(row.parser_version, nvm_reports.PARSER_VERSION)
        self.assertEqual(row.source_file, "regio-delft.pdf")

    def test_an_older_report_never_replaces_a_newer_figure(self):
        older = PAGE.replace("3e kwartaal 2026", "2e kwartaal 2026").replace("4.771", "1.111")
        with tempfile.TemporaryDirectory() as folder:
            nvm_reports.ingest_report(self._pdf(folder, "new.pdf", PAGE))
            created, updated, kept = nvm_reports.ingest_report(self._pdf(folder, "old.pdf", older))
        self.assertEqual((created, updated, kept), (0, 0, 6))
        self.assertEqual(NVMMarketReport.objects.get(year=2026, quarter=3, dwellingType="Totaal").pricePerSqm_EUR, 4771.0)

    def test_a_later_report_corrects_a_figure(self):
        newer = PAGE.replace("3e kwartaal 2026", "4e kwartaal 2026").replace("4.771", "4.800")
        with tempfile.TemporaryDirectory() as folder:
            nvm_reports.ingest_report(self._pdf(folder, "a.pdf", PAGE))
            _, updated, _ = nvm_reports.ingest_report(self._pdf(folder, "b.pdf", newer))
        self.assertEqual(updated, 6)
        row = NVMMarketReport.objects.get(year=2026, quarter=3, dwellingType="Totaal")
        self.assertEqual((row.pricePerSqm_EUR, row.reportQuarter), (4800.0, 4))

    def test_text_without_figures_stores_nothing(self):
        with tempfile.TemporaryDirectory() as folder:
            result = nvm_reports.ingest_report(self._pdf(folder, "x.pdf", "Marktoverzicht Nederland"))
        self.assertEqual(result, (0, 0, 0))

    def test_catalog_entry_reads_the_folder_and_skips_files_already_read(self):
        with tempfile.TemporaryDirectory() as folder, self.settings(NVM_PDF_DIR=folder):
            self._pdf(folder, "regio-delft.pdf", PAGE)
            first = nvm_reports.fetch({"params": {}})
            second = nvm_reports.fetch({"params": {}})
        self.assertEqual((first.status, first.records_created), ("success", 6))
        self.assertEqual((second.status, second.records_created), ("success", 0))
        self.assertEqual(NVMMarketReport.objects.count(), 6)

    def test_empty_folder_is_an_error_that_names_the_folder(self):
        with tempfile.TemporaryDirectory() as folder, self.settings(NVM_PDF_DIR=folder):
            result = nvm_reports.fetch({"params": {}})
        self.assertEqual(result.status, "error")
        self.assertIn(folder, result.message)


class PriceIndexEdgeTests(TestCase):
    """DAG edge: Market_Reports -> House_Price_Index."""
    REGION = "Delft en Westland"

    def setUp(self):
        self.city = make_city(id=503, cityName="Delft")
        self.hood = make_neighborhood(city=self.city)
        NVMRegionMapping.objects.create(city=self.city, region=self.REGION)

    def _quarters(self, year, price, n=4):
        for quarter in range(1, n + 1):
            NVMMarketReport.objects.create(
                region=self.REGION, year=year, quarter=quarter, dwellingType="Totaal", pricePerSqm_EUR=price,
                reportYear=year, reportQuarter=quarter, pdf_sha256="x", parser_version="1")

    def _index(self, year):
        return HousePriceIndex.objects.get(neighborhood=self.hood, year=year)

    def test_full_years_create_an_index_for_each_neighborhood(self):
        self._quarters(2023, 4000.0)
        self._quarters(2024, 4400.0)
        row = self._index(2024)
        self.assertAlmostEqual(row.index_value, 110.0)
        self.assertEqual((row.baseYear, row.pricePerSqm_EUR, row.nvmRegion), (2023, 4400.0, self.REGION))
        self.assertEqual(row.indexMethod, chain.INDEX_METHOD)
        self.assertAlmostEqual(self._index(2023).index_value, 100.0)

    def test_a_part_year_gives_no_index(self):
        self._quarters(2023, 4000.0, n=3)
        self.assertFalse(HousePriceIndex.objects.exists())

    def test_a_corrected_quarter_moves_the_index(self):
        self._quarters(2023, 4000.0)
        self._quarters(2024, 4400.0)
        NVMMarketReport.objects.filter(year=2024, quarter=4).update(pricePerSqm_EUR=4400.0)
        NVMMarketReport.objects.get(year=2024, quarter=4).save()                 # same value: unchanged
        self.assertAlmostEqual(self._index(2024).index_value, 110.0)
        report = NVMMarketReport.objects.get(year=2024, quarter=4)
        report.pricePerSqm_EUR = 4800.0
        report.save()
        self.assertAlmostEqual(self._index(2024).index_value, 100 * (4400 * 3 + 4800) / 4 / 4000)

    def test_deleting_a_quarter_keeps_the_stored_index_of_a_year_that_is_no_longer_complete(self):
        self._quarters(2023, 4000.0)
        self._quarters(2024, 4400.0)
        NVMMarketReport.objects.get(year=2024, quarter=4).delete()
        self.assertAlmostEqual(self._index(2024).index_value, 110.0)             # rule 4: stored value kept

    def test_a_mapping_imported_after_the_reports_gets_the_index(self):
        NVMRegionMapping.objects.all().delete()
        self._quarters(2023, 4000.0)
        self.assertFalse(HousePriceIndex.objects.exists())
        NVMRegionMapping.objects.create(city=self.city, region=self.REGION)
        self.assertAlmostEqual(self._index(2023).index_value, 100.0)

    def test_without_nvm_data_the_stored_index_is_kept(self):
        row = HousePriceIndex.objects.create(neighborhood=self.hood, year=2020, index_value=87.5)
        row.refresh_from_db()
        self.assertEqual((row.index_value, row.indexMethod, row.baseYear), (87.5, "", None))

    def test_other_regions_are_untouched(self):
        other = make_neighborhood(city=make_city(id=518, cityName="Den Haag"))
        self._quarters(2023, 4000.0)
        self.assertFalse(HousePriceIndex.objects.filter(neighborhood=other).exists())

    def test_a_bulk_import_refreshes_each_region_once(self):
        from importer.batching import deferred_cascades

        with mock.patch.object(signals, "_resave", wraps=signals._resave) as resave:
            with deferred_cascades():
                self._quarters(2023, 4000.0)
                self._quarters(2024, 4400.0)
                self.assertEqual(resave.call_count, 0)           # queued, nothing done yet
        # one pass: 1 neighborhood x 2 complete years (the pass is _resave per row)
        self.assertEqual(resave.call_count, 2)
        self.assertEqual(HousePriceIndex.objects.count(), 2)

    def test_raw_saves_do_nothing(self):
        report = NVMMarketReport(region=self.REGION, year=2023, quarter=1, dwellingType="Totaal",
                                 reportYear=2023, reportQuarter=1, pdf_sha256="x", parser_version="1")
        with mock.patch.object(signals, "_refresh_region_index") as refresh:
            signals.nvm_report_changed(NVMMarketReport, report, raw=True)
        refresh.assert_not_called()


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

    def test_baseline_is_the_mean_score_of_residential_buildings_and_is_frozen(self):
        self._property(90.0)
        shop_building = Building.objects.create(id=2, buildingType="commercial", geom=make_polygon(257100.0, 470000.0, 30))
        Property.objects.create(name="s", grossArea=50, usageFunction=["Shop function"],
                                geom=Point(257100.0, 470000.0, srid=SRID))
        snapshot = datetime.date(2026, 11, 1)
        for building, walk, bike, x in ((self.building, 60.0, 80.0, 257000.0), (shop_building, 10.0, 10.0, 257100.0)):
            for mode, score in (("walk", walk), ("bike", bike)):
                Accessibility.objects.create(building=building, mode=mode, score=score, method="m1",
                                             network_snapshot=snapshot, geom=Point(x, 470000.0, srid=SRID))
        row = WOZValue.objects.create(neighborhood=self.hood, year=2024, avgWOZ_EUR=450_000.0)

        woz.freeze_baselines([row])

        row.refresh_from_db()
        self.assertEqual((row.baselineAccessWalk, row.baselineAccessBike), (60.0, 80.0))   # the shop is left out
        self.assertEqual((row.baselineSnapshot, row.baselineMethod), (snapshot, "m1"))

        Accessibility.objects.filter(building=self.building, mode="walk").update(score=90.0)
        woz.freeze_baselines([row])                                         # frozen: not refreshed
        row.refresh_from_db()
        self.assertEqual(row.baselineAccessWalk, 60.0)
        woz.freeze_baselines([row], overwrite=True)
        row.refresh_from_db()
        self.assertEqual(row.baselineAccessWalk, 90.0)


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

    def test_import_writes_stored_neighborhoods_only_and_fills_area_and_baseline(self):
        city = make_city(id=503, cityName="Delft")
        hood = make_neighborhood(id="BU05030101", city=city)
        make_neighborhood(id="BU05030102", district=hood.district, geom=make_polygon(300000.0, 470000.0, 100))
        building = Building.objects.create(id=1, buildingType="residential", geom=make_polygon(257000.0, 470000.0, 30))
        Property.objects.create(name="p", grossArea=90.0, usageFunction=DWELLING, geom=Point(257000.0, 470000.0, srid=SRID))
        Accessibility.objects.create(building=building, mode="walk", score=55.0, method="m1",
                                     geom=Point(257000.0, 470000.0, srid=SRID))

        with mock.patch("importer.cbs_woz.requests.get", return_value=self._response()) as get:
            result = cbs_woz.fetch(self.DATASET)

        self.assertEqual((result.status, result.records_created), ("success", 2))   # BU05039999 is not stored
        self.assertIn("startswith(WijkenEnBuurten,'BU0503')", get.call_args.kwargs["params"]["$filter"])
        row = WOZValue.objects.get(neighborhood=hood, year=2024)
        self.assertEqual((row.avgWOZ_EUR, row.dwellings, row.cbs_table_id), (450000.0, 1200, "85984NED"))
        self.assertAlmostEqual(row.woz_per_sqm, 5000.0)
        self.assertEqual(row.baselineAccessWalk, 55.0)
        self.assertIsNone(row.baselineAccessBike)
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
        self.assertEqual(CATALOG_BY_KEY["nvm_market_reports"]["target_model"], "housing.NVMMarketReport")


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
