# Accessibility score and property price — plan and progress

Plan for a network-accessibility score per building (walk and bike, pandana) and its use as a driver of modelled price per m². Moved here from the planning session (2026-11-25) so the phases can be tracked. Update the checkboxes and the "Status" lines as work lands.

Legend: `[x]` done, `[ ]` open. Commits: Phase 1 `020d4c3`, Phase 2 backend `8a54d82`; the Phase 2 UI, docs and review fixes are not committed yet.

## Context

`core/DAG.dot` has `Facilities / Streets / Green_Area -> Accessibility -> Property` (lines ~235-238). Before this work none of the edges existed, `Building.connectivity` was an unused M2M, and there was no routing code, no price source and no regression code.

Goals:
1. A reproducible network-accessibility score per building.
2. The score rises when an amenity is added.
3. That change feeds a modelled price per m² through a hedonic coefficient.
4. Calibrated on open price data: CBS WOZ per buurt and the NVM market-report PDFs.

Funda and Pararius are **not** scraped (their terms forbid it). A licensed export can go through the existing upload flow later.

## Decisions

| Decision | Choice | Note |
|---|---|---|
| Routing | pandana, optional `access` extra | Spike result: pandana 0.8.1 installs from a wheel on Python 3.12/Windows, so the scipy fallback was not needed. |
| Modes | walk and bike, OSM graph | |
| Reach | walk: full value to 400 m, cut-off 1.6 km; bike: full value to 800 m, cut-off 2 km | Bike cut-off cut from 5 km to 2 km (2026-11-25) so one map edit recomputes a bounded area. |
| Prices | CBS WOZ per buurt (level) + NVM quarterly PDFs (market trend), new tables | Both editable later; they drive what-if sliders. |
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

Status: **not started**

- [ ] `housing.WOZValue`: neighborhood, year, `avgWOZ_EUR` (CBS Kerncijfers wijken en buurten), living area from BAG, `woz_per_sqm`, `cbs_table_id`, `source`, frozen buurt-mean accessibility baseline per mode
- [ ] Catalog entries for CBS WOZ tables 2019-2024 in `importer/external_catalog.py`
- [ ] `housing.NVMMarketReport` (region, period, transactions, average price, price per m², percent above asking, days on market, `source_url`, `pdf_sha256`, `retrieved_at`, `parser_version`) and `NVMRegionMapping`
- [ ] `importer/nvm_reports.py`: collect PDF links from the NVM market-information page, download to `media/nvm/<sha256>.pdf`, parse with `pdfplumber`, upsert
- [ ] Check NVM's robots.txt and terms before the first run
- [ ] Register NVM and CBS in `core/data_sources.py`, rerun `tools/data_sources.py`
- [ ] Edge `NVM report -> House_Price_Index` (derive the index from NVM price per m²); update DAG docs and status
- [ ] Tests: NVM parser on a committed fixture PDF; WOZ per m²

## Phase 4 — Accessibility to price

Status: **not started**

- [ ] `housing.PriceModel` (one row per fit): spec, coefficients, standard errors, r², n, WOZ year, network snapshot, method, **`design`** (`cross_section` now; a within-neighbourhood fit over time can sit beside it once licensed listing data exists)
- [ ] `housing/calculations/price_model.py`: statsmodels OLS on `ln(woz_per_sqm)` with accessibility (walk, bike), controls (construction year, apartment share, energy label, CBS SES, distance to centre) and municipality fixed effects; weights by dwelling count; municipality-clustered errors; report beta with and without controls; run from a UI button
- [ ] Pure equation in `housing/calculations/chain.py`: `modelled_price_per_sqm = woz_per_sqm * market_factor * exp(sum_mode beta_mode * (A - A_baseline))`, `market_factor` from NVM at the current quarter vs the WOZ reference date (1 January of the year before)
- [ ] Stored output on `builtup.Property`: `modelledPrice_EUR_per_sqm`, `priceModel` FK, `priceMethod` (observed `unitaryPrice_EUR_per_sqm` untouched)
- [ ] Edge `Accessibility -> Property`: receiver in `housing/signals.py` on `accessibility_changed`
- [ ] What-if sliders (never write): market growth %, beta multiplier (default 1, "conservative" preset 0.5), accessibility delta
- [ ] Label every modelled price "association-based scenario (upper bound), not a forecast" (stored method, dashboard, "?" help, `.tex`)
- [ ] Dashboard/stored parity test; tests for the fit on synthetic data (recovers a known beta)
- [ ] Docs per the `dag-edge` checklist; rerun `dag-contract-reviewer`

Rent: no open per-buurt rent source yet, so `Property -> Rent` stays a gap. A licensed Pararius file can go into `housing.Rentals` through the upload flow (needs a CSV branch in `importer/forms.py::GeoUploadForm`).

## Verification (end to end)

- Unit tests: `uv run python manage.py test builtup housing importer --settings=DigitalTwin.settings_test --keepdb --noinput`
- Delft run: import network and amenities, compute accessibility, check the score map
- Add a supermarket in the map editor: nearby walk scores rise (and, after Phase 4, `modelledPrice_EUR_per_sqm`); buildings beyond the cut-off are unchanged
- Move the market-growth slider: prices change on the dashboard and nothing is written
