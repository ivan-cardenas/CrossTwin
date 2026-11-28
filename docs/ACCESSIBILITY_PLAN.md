# Accessibility score and property price — plan and progress

Plan for a network-accessibility score per building (walk and bike, pandana) and its use as a driver of modelled price per m². Moved here from the planning session (2026-11-25) so the phases can be tracked. Update the checkboxes and the "Status" lines as work lands.

Legend: `[x]` done, `[ ]` open. Commits: Phase 1 `020d4c3`, Phase 2 backend `8a54d82`; Phase 2 UI and docs follow in later commits (see `git log`); Phase 3 is not committed yet.

## Context

`core/DAG.dot` has `Facilities / Streets / Green_Area -> Accessibility -> Property` (lines ~235-238). Before this work none of the edges existed, `Building.connectivity` was an unused M2M, and there was no routing code, no price source and no regression code.

Goals:
1. A reproducible network-accessibility score per building.
2. The score rises when an amenity is added.
3. That change feeds a modelled price per m² through a hedonic coefficient.
4. Calibrated on open price data: CBS WOZ (per buurt, per PC6 postcode area). The NVM market reports were dropped on 2026-11-27.

Funda and Pararius are **not** scraped (their terms forbid it). A licensed export can go through the existing upload flow later.

## Decisions

| Decision | Choice | Note |
|---|---|---|
| Routing | pandana, optional `access` extra | Spike result: pandana 0.8.1 installs from a wheel on Python 3.12/Windows, so the scipy fallback was not needed. |
| Modes | walk and bike, OSM graph | |
| Reach | travel time, same for both modes: cut-off 15 min (Moreno et al. 2021), from speed 1.2 km walk (4.8 km/h) / 3.75 km bike (15 km/h); full value to 100 m walk / 400 m bike | Bike cut-off cut from 5 km to 2 km (2026-11-25) so one map edit recomputes a bounded area; replaced on 2026-11-28 by a 15 min cut-off in both modes (bike 3.75 km, method v5). Frozen price baselines made with the 2 km cut-off must be re-frozen. |
| Prices | CBS WOZ per PC6 postcode area (level; newest year available, no valuation-date shift) | NVM removed 2026-11-27. |
| Reading of the price result | association-based scenario, **upper bound**, not a forecast | A cross-neighbourhood fit credits accessibility with everything correlated with it (prestige, jobs, older housing); WOZ also lags the market. |

---

## Phase 0 — Dependencies

Status: **done**

- [x] `pandana` as the `access` extra; `statsmodels` and `pdfplumber` as regular dependencies; `uv.lock` updated
- [x] Install check (`uv sync --inexact --extra access`)
- [x] `docs/claude/dependencies.md`

## Phase 1 — Inputs

Status: **done** (commit `020d4c3`)

- [x] `Facility.type` extended: supermarket, shop, pharmacy, clinic_gp, childcare, library, sport, bus_stop, tram_metro_stop, train_station
- [x] Catalog entry `osm_access_amenities` (nodes and ways; kept disjoint from `osm_amenities` so existing station and school rows keep their meaning; old `transportNode`/`station` rows still count as train stations)
- [x] Parks from `nature.GreenSpaces.park_space()`, entry points every 50 m along the edge (`park_access_points`)
- [x] `builtup.NetworkNode` and `NetworkEdge` (snapshot date and query hash on each edge)
- [x] Catalog entry `osm_network` (format `overpass_network`), `importer/osm_network.py` (walk/bike classification, cut at intersections)
- [x] Tests: `importer/tests/test_osm_network.py`

Known limits: a way deleted from OSM is not removed on re-import; one-way streets and the bicycle one-way exemption are ignored.

## Phase 2 — Accessibility (stored node)

Status: **done**

Model and equations
- [x] `builtup.Accessibility` (unique per building and mode; `distances`, `score`, `method`, `network_snapshot`, centroid `geom`); `Building.connectivity` removed
- [x] Equations in `builtup/calculations/chain.py` (distance decay, category weights, score 0-100, named constants)
- [x] `Accessibility.method` stores the method label plus a hash of its constants (`chain.METHOD_STAMP`)
- [x] `building` FK is `CASCADE` (a derived row goes with its building)

Compute and edges
- [x] `builtup/calculations/accessibility.py` (graph cache, POI loading limited to the reachable box, pandana `nearest_pois`, snapping offsets, bulk upsert)
- [x] Receivers in `builtup/signals.py`: `Facilities`, `Green_Area`, `Streets` -> `Accessibility`; `accessibility_changed` signal
- [x] Bulk path: `deferred_accessibility_refresh` in `deferred_cascades()`, finalizer `_refresh_accessibility_over` for `builtup.Facility`, network import schedules its extent
- [x] Graph cache key includes `NetworkEdge.updated` (an edit in place reaches every worker)

UI
- [x] Map card "Network Accessibility" (`core/static/js/AccessibilityTool.js`), staff recompute and info endpoints (`builtup/views_accessibility.py`)
- [x] Map view: smooth raster `AccessibilityRaster` per mode (10 m cells, Gaussian 50 m, masked beyond 75 m; `access_raster.py`), shown by the card and the "On map" button; the building dots stay as a layer
- [x] Map layers: proxies `AccessibilityWalk` / `AccessibilityBike` (five score classes), `NetworkEdge` line layer
- [x] Dashboard card with "?" help and "On map" button (`calculate_accessibility`)

Docs and checks
- [x] `docs/DAG_COVERAGE.md` (67 implemented, 7 partial, 32 gaps), `core/dag_status.py`, `docs/functions_and_equations.tex`, `TODO.md`, `docs/claude/*`, `docs/DATA_SOURCES.md`
- [x] `dag-contract-reviewer` run; valid findings fixed
- [x] Tests: `builtup/tests/test_accessibility.py`, `test_accessibility_ui.py`
- [x] Commit the UI, docs and review fixes
- [ ] First real run on a city (Delft): import network and amenities, compute, check the score map and timing of a single map edit
- [x] Decided: no `Buildings -> Accessibility` edge in Phase 2 (a building added or moved is rescored at the next recompute; revisit with Phase 4 if price modelling needs it)
- [x] Name the geometry `tolerance=0.01` literal in the receivers (`GEOM_EQUAL_TOL_M` in `builtup/signals.py`)

Known issue outside this work: three `physicalEnv.tests.test_dsm_edited` tests fail (`cog_overview_level` imported in one function, used in another, `physicalEnv/calculations/dsm_edited.py`).

## Phase 3 — Price data

Status: **done in code** (2026-11-26; not committed yet); first real run on Delft still open

- [x] `housing.WOZValue`: neighborhood, year, `avgWOZ_EUR` (CBS Kerncijfers wijken en buurten), dwelling stock, mean BAG dwelling area, `woz_per_sqm`, `cbs_table_id`, `source`, `method`, frozen buurt-mean accessibility baseline per mode (with its method stamp and network snapshot)
- [x] Catalog entries `CBS_WOZ_2019` … `CBS_WOZ_2024` (tables 84583NED, 84799NED, 85039NED, 85318NED, 85618NED, 85984NED; column keys checked on each table), handler `importer/cbs_woz.py`
- [x] `housing.NVMMarketReport` (region, year, quarter, dwelling type, transactions, median price, price per m², days on market, asking gap, share above asking, `source_url`, `pdf_sha256`, `retrieved_at`, `parser_version`, report quarter) and `NVMRegionMapping` (municipality → COROP region)
- [x] `importer/nvm_reports.py`: parses the PDFs with `pdfplumber` (checked on the real "Marktoverzicht Nederland, 3e kwartaal 2026" and the COROP list), upserts, newest report wins
- [x] NVM robots.txt and terms checked (2026-11-26): robots.txt allows the pages, but the copyright and disclaimer pages allow non-commercial private use only and reserve reproduction and redistribution. **Decision: the PDFs are not downloaded by CrossTwin**; a person downloads them into `NVM_PDF_DIR` (default `media/nvm`) and the catalog entry `nvm_market_reports` reads that folder. Ask NVM for written permission before publishing or sharing the figures (research outputs, shared databases)
- [x] NVM and CBS registered in `core/data_sources.py`, `docs/DATA_SOURCES.md` regenerated
- [x] New DAG node `Market_Reports` and edge `Market_Reports -> House_Price_Index` (the plan's "NVM report" node): `HousePriceIndex.save()` derives the index from the region's annual mean price per m² (four quarters needed), receivers in `housing/signals.py`, deferred per region; docs per the `dag-edge` checklist (`docs/DAG_REVISIONS.md`, `DAG_COVERAGE.md`: 107 edges, 68 implemented)
- [x] Tests: `housing/tests/test_prices.py` (NVM parser on generated PDFs and on the layout of the real report, WOZ per m², baseline freezing, CBS import with a mocked response, the edge and its deferral). No NVM PDF is committed: its terms reserve reproduction, so the fixtures are PDFs generated in the test
- [ ] First real run: import neighborhoods and buildings for Delft, `CBS_WOZ_2024`, put the COROP list and the regional report PDFs in `media/nvm`, import `nvm_market_reports`, check `WOZValue` and `HousePriceIndex`

Known limits: CBS rounds the mean WOZ value to 1 000 EUR; the index is region-wide (all neighborhoods of a COROP area share it) and needs four NVM quarters per year, and each PDF holds only three quarters, so at least two consecutive reports per year are needed; the regional PDFs' footer text was assumed to follow the national one (`... kwartaalcijfers <region> | <q>e kwartaal <year>`), a report that does not match gives no rows.

## Phase 4 — Accessibility to price

Status: **done in code** (2026-11-26; not committed yet); first real run on Delft still open

- [x] `housing.PriceModel` (one row per fit): spec, coefficients, standard errors, r², n, WOZ year, network snapshot, method, **`design`** (`cross_section` now; a within-neighbourhood fit over time can sit beside it once licensed listing data exists); also the betas with and without controls, Moran's I and p (OLS and spatial error), lambda, the form comparison, seed, library versions and `isActive`
- [x] **PC6 postcode areas are the main fitting unit** (2026-11-27; a municipality has hundreds of them, a few dozen neighborhoods): `administrative.Postcode4` / `Postcode6` (CBS postcode statistics from PDOK, catalog `pdok_postcode4` / `pdok_postcode6`) hold the mean WOZ value and the dwelling count; `housing.PostcodePrice` (one row per PC6 and statistics year, `housing/calculations/postcode_woz.py`) adds the BAG mean dwelling area (by BAG postcode, spaces removed), the derived `woz_per_sqm`, the neighborhood and municipality under the area, and the accessibility baseline frozen once (mean over the buildings that hold its dwellings); `PriceModel.unit` is `postcode6` (default) or `neighborhood` (the first implementation, kept as a comparison); a dwelling is priced by its own BAG postcode. Rows with under 80 % BAG coverage are left out, as for neighborhoods
- [x] `housing/calculations/price_model.py`: statsmodels WLS on `ln(woz_per_sqm)` with accessibility (walk, bike), controls (construction year, apartment share, energy label, CBS SES, distance to centre; a control with under 80 % coverage is dropped, not imputed) and municipality fixed effects; weights by dwelling count; municipality-clustered errors (clustered by PC4 postcode area with one municipality, HC1 without PC4 clusters); controls at PC6: BAG construction year and energy label, CBS multi-family and rental shares, the socio-economic status of the neighborhood under the area, distance to the municipal centroid; beta with and without controls; run from a UI button (staff "Fit price model" on the housing dashboard, `/housing/price-model/fit/`)
- [x] Spatial autocorrelation: Moran's I on the OLS residuals (queen contiguity on the neighborhood polygons, `libpysal` + `esda`, regular dependencies, permutation seed stored with the fit). If significant (p < 0.05), also a spatial error model (`spreg`: lambda by ML, coefficients by WLS on the filtered data); the betas of the model whose residuals pass the diagnostic are stored, with the choice and Moran's I/p in `PriceModel`
- [x] Nonlinearity in accessibility: linear vs `ln(1 + A)` compared by AIC and spatially blocked cross-validated r² (municipalities as blocks from five of them, else a 3x3 grid of centroids; the comparison drops the municipality effects, a held-out municipality has none). The stored form is linear or log1p; the spline (4 df) is a diagnostic only and flags a strong departure
- [x] Pure equation in `housing/calculations/chain.py`: `modelled_price_per_sqm = woz_per_sqm * market_factor * (1 + growth) * exp(clip(k * sum_mode beta_mode * (T(A + delta) - T(A_baseline))))`; `market_factor` = NVM latest quarter / the quarter that ends on the WOZ valuation date (the 4th quarter of the table year - 2), 1 without both; the log effect is clipped to +-0.5 (named design guard)
- [x] Stored output on `builtup.Property`: `modelledPrice_EUR_per_sqm`, `priceModel` FK (lazy string reference, builtup does not import housing), `priceMethod` (observed `unitaryPrice_EUR_per_sqm` untouched)
- [x] Edge `Accessibility -> Property`: receiver `accessibility_cascaded` in `housing/signals.py` on `accessibility_changed`; `property_price.reprice` (one `bulk_update`, no signals, so no loop); missing inputs keep the stored price
- [x] What-if sliders (never write): market change %, beta multiplier (default 1, "conservative" preset 0.5), accessibility change in score points
- [x] Label every modelled price "association-based scenario (upper bound), not a forecast" (stored `priceMethod` and `PriceModel.method`, dashboard card, "?" help, `.tex`)
- [x] Dashboard/stored parity test; tests for the fit on synthetic data (recovers a known beta; Moran's I flags an injected spatial error and not noise; the form comparison picks a known log relation): `housing/tests/test_price_model.py`
- [x] Docs per the `dag-edge` checklist (`DAG_COVERAGE.md`: 107 edges, 69 implemented, 31 gaps; `dag_status.py`, `.tex`, `DATA_SOURCES.md`, `docs/claude/*`)
- [x] `dag-contract-reviewer` run
- [ ] First real run (the development database holds Enschede, CBS code 0153): import `Postcode areas - PC6` (CBS), make sure the BAG dwellings cover the whole area and the network accessibility is computed, then "Fit price model" (it writes the `PostcodePrice` rows and freezes their baselines first: do it before amenities or the network are edited); read the Moran result and the betas with and without controls before trusting a number

Known limits: the WOZ valuation date of the CBS postcode statistics is taken as 1 January of the statistics year - 1, the convention of the buurt tables (check it against the CBS documentation when the year changes); CBS suppresses the mean WOZ value of small postcode areas (no row, no fit); an area is fitted only when the BAG dwellings its mean area is taken over are at least 80 % of its CBS dwelling stock (`MIN_AREA_COVERAGE`; the PDOK import extent can clip a neighborhood, which leaves a thin, skewed sample); the ones left out are listed in `PriceModel.spec["excluded_low_coverage"]` and counted on the card; a new NVM quarter or WOZ year reaches the stored prices at the next "Reprice dwellings" or accessibility refresh (the DAG has no `Market_Reports -> Property` edge); a dwelling added later is priced at the next refresh that reaches its building; the spatial error lambda is estimated on the unweighted data; the model is a cross-section of neighborhoods (an association, not a causal effect); the distance to the centre is measured to the municipality's centroid.

Rent: no open per-buurt rent source yet, so `Property -> Rent` stays a gap. A licensed Pararius file can go into `housing.Rentals` through the upload flow (needs a CSV branch in `importer/forms.py::GeoUploadForm`).

## Verification (end to end)

- Unit tests: `uv run python manage.py test builtup housing importer --settings=DigitalTwin.settings_test --keepdb --noinput`
- Delft run: import network and amenities, compute accessibility, check the score map
- Add a supermarket in the map editor: nearby walk scores rise (and, after Phase 4, `modelledPrice_EUR_per_sqm`); buildings beyond the cut-off are unchanged
- Move the year slider of the House Price Index: the modelled prices follow the index and nothing is written

## Revision 2026-11-27

- Removed: NVM reports (models, importer, parser, `pdfplumber`, market factor, `Market_Reports -> House_Price_Index`), the neighborhood fit (`unit` of `PriceModel`, "Fit on neighborhoods", neighborhood baselines of `WOZValue`), and the *Accessibility Effect* and *Accessibility Change* sliders with `beta_mult`, `access_delta`. The WOZ value is read at the newest year available, not shifted to a valuation date. The *Market Change* slider now scales the WOZ level.
- Price model per amenity category: the terms are the 13 categories x walk and bike (`mode:category`, value 0-100 from `Accessibility.distances`), frozen per PC6 area in `PostcodePrice.baselineCategories`. Before the fit `price_model.screen_terms` drops terms with too little variation, redundant pairs (|r| >= 0.9), collinear terms (VIF > 10) and terms with too little influence (p > 0.10 or under 0.5 % per sd); every candidate and its reason is stored in `PriceModel.screening` and listed on the card.
- *Add amenity* button on the modelled-price card: opens the map editor on `builtup.Facility`; saving reprices the dwellings around it.
- First real run with the new terms still open (fits made before are deactivated by migration `housing/0017`).
- Amenities of one category within 50 m of each other are merged into one destination (`chain.POI_MERGE_M`, `accessibility.merge_close_points`; parks exempt), so a stop on each side of a street is not counted twice. `ACCESS_METHOD` is `v3`: recompute the accessibility, re-freeze the baselines and refit.
- Price = one city-wide equation (2026-11-27): `PriceModel.prediction` (intercept, term betas, control coefficients and means, municipality effects, Duan smearing factor) is applied to each dwelling's own accessibility terms and controls (`chain.log_price`, `property_price.reprice`). The PC6 WOZ value only calibrates it; the frozen baselines are the state the WOZ values were calibrated at, not a price anchor. Fits made before are deactivated (migration `housing/0019`); run Fit price model.
