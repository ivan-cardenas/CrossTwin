
# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CrossTwin is a Django-based digital twin platform for geospatial urban data (water supply, urban heat, energy, housing, nature). It uses PostgreSQL/PostGIS for spatial storage, Mapbox GL JS for map rendering, and TiTiler (FastAPI) for raster tile serving.

The project focuses on **Dutch geospatial data** — the default CRS is EPSG:28992 (Amersfoort / RD New), configured via `COORDINATE_SYSTEM` in `.env`.

## Common Commands

```bash
# Activate virtual environment (Windows)
.venv\Scripts\Activate

# Start both Django and TiTiler (or use start.bat)
python manage.py runserver 8000
uvicorn tiler:app --port 8001 --reload

# Database migrations
python manage.py makemigrations
python manage.py migrate

# Run all tests (uses custom PostGIS test runner). Always pass --keepdb: without it
# Django drops the test DB the runner prepared and recreates it without PostGIS
# ("type geometry does not exist"). --noinput avoids the interactive prompt.
python manage.py test --settings=DigitalTwin.settings_test --keepdb --noinput

# Run tests for a single app
python manage.py test importer --settings=DigitalTwin.settings_test --keepdb --noinput

# Export COGs for raster models
python manage.py export_cogs

# Slowest SQL statements from pg_stat_statements (--order mean|calls|rows, --reset)
python manage.py db_stats

# Profile GET requests (run 1 = cold process, run 2 = warm); --save x.prof for snakeviz
python tools/profile_requests.py "/api/admin-unit/?lng=6.895&lat=52.219" --runs 2

# Which modules are slow to import
python -X importtime -c "import django; django.setup(); import DigitalTwin.urls" 2> imports.log
```

Measurement flags in `.env` (see `docs/PERFORMANCE.md` §0): `QUERY_STATS=true` (default = `DEBUG`) adds a `Server-Timing` header (DB time + query count, visible in DevTools → Network → Timing) and `X-DB-Queries` to every response and logs each request on `crosstwin.querystats` (WARNING above `QUERY_STATS_SLOW_MS`, default 500). `SQL_LOG=true` prints every SQL statement (only when `DEBUG=true`).

## Architecture

### Django Settings & Two-Server Setup

- **Django project**: `DigitalTwin/` — settings load from `.env` via `python-dotenv`
- **TiTiler**: `tiler.py` — a separate FastAPI app serving COG raster tiles on port 8001. Django proxies to it via `TITILER_BASE_URL` env var.
- Windows GDAL/GEOS DLLs are auto-discovered from the venv's `osgeo` package in `settings.py`.

### Model Registry System (`core/utils.py`)

The central architectural pattern. `build_model_registry()` scans a hardcoded list of allowed apps (`administrative`, `physicalEnv`, `urbanHeat`, `watersupply`, `weather`, `builtup`, `Energy`, `housing`, `nature`) and builds four registries:

- **`MODEL_REGISTRY`** — all models from allowed apps
- **`VECTOR_REGISTRY`** — models with GeometryField (no RasterField)
- **`RASTER_REGISTRY`** — models with RasterField
- **`WMS_REGISTRY`** — models with "WMS" in the registry key

These registries power generic API endpoints, the map layer catalog, and the importer. When adding a new domain app, it must be added to the `allowed_apps` list in `core/utils.py` and to `INSTALLED_APPS` in `settings.py`.

### DPSIR Causal Network (`core/DAG.dot`)

The project follows the **DPSIR framework** (Driver → Pressure → State → Impact → Response) to model causal relationships between urban systems. The full causal graph is defined in `core/DAG.dot` (Graphviz format). Each domain app's `calculations.py` documents which DAG edges its functions implement via comments like `# DAG edges: Central_Bank -> Mortgage`.

When adding new calculations, trace the relevant DAG edges and document them in the function docstring to maintain traceability between the causal model and code.

#### DAG Edge Coverage Gaps

Of the 102 edges in `core/DAG.dot`, only 28 are backed by real derivation logic (a `save()` method or a `calculations.py` function that actually reads the source field, not just a docstring claiming the edge). The rest are either flat stored fields with no computation, or `calculations.py` functions whose docstring claims a DAG edge the code doesn't actually implement. Verified gaps, by app:

**administrative** — `Population_Growth -> Total_Population` is implemented at city level: CBS 85173NED forecasts are imported into `PopulationProjection` (per City, year and variant `prognose|low|high`; catalog entry `CBS_PopulationForecast`), and `administrative/population.py::get_population()` derives any unit's projected population (District/Neighborhood = city projection x their share of the city, Province = sum of its cities, plus an optional `growth_adjust_pct` what-if). The water and housing dashboards use it via `?pop_scenario=&pop_growth=`. The what-if controls and a Photoshop-Curves-style forecast graph (smooth curve, square handles, shaded 67% interval band; geometry in `mainMap/charts.py`) live in the map's bottom **Population dock** (Population pill, `/api/population/panel/`), independent of the side panel so an indicator panel can stay open beside it. Still open: `City.popGrowthRate`/`urbanizationRate` remain flat fields never used for projection, housing supply/demand and urban heat do not depend on the projected population (housing shows it but its demand still comes from stored `HousingSupplyDemand` rows), and no `Urbanization` model exists, so `Urbanization -> CityArea/Buildings/Streets/LandCover` has nowhere to live.

**physicalEnv** — `RS_Imagery -> LandCover/LST` — raster models are plain imports with no ingestion/derivation code. `LandCover -> Infiltration` — `AvailableFreshWater.infiltrationRate_cm_h` is flat (see existing TODO). `New_Units -> LandCover` — `calculate_new_units()` never touches LandCover.

**urban_heat** — the whole `DSM -> SVF -> Tmrt/PET`, `LST -> PET`, `Tmrt -> UTCI`, `Canyon_Aspect -> DSM`, `Vegetation_Coverage -> DSM`, `Streets -> Canyon_Aspect` chain is unimplemented: SVF/Tmrt/PET/UTCI/LST models are `RasterField` containers with no `save()`; `calculate_urban_morphology()`/`get_thermal_indices()` only compute *statistics over* existing rasters, they don't derive one raster from another (these are expected to come pre-computed from SOLWEIG externally). `PET -> NBS` — `calculate_nbs_coverage()` counts NBS geometries but never reads PET values.

**builtup / housing** — No `Accessibility` model exists anywhere, so `Facilities/Streets/Green_Area -> Accessibility -> Property` has no implementation (`Building.connectivity` is the closest analog, still under its own TODO). `Zoning_Status -> Property`, `Property -> House_Price_Index/Mortgage` — none of `Property`/`Mortgage`/`HousePriceIndex` have `save()` logic; the `calculations.py` functions only average pre-existing stored values. `HousingAffordability.save()` computes `affordabilityIndex` only from its own stored fields — it never pulls from `Mortgage`, `Rentals`, or watersupply tariff data, so `Rent/Mortgage/Water_Tariff_Afford -> Income_Expenses -> Affordability_Stress` and `Credit_Supply -> Mortgage` are unimplemented. `NumberUsers -> Water_Tariff_Afford` — no `NumberUsers` model; `MeteredResidential.userAffordability_PCT` is a flat input.

**watersupply** — Implemented via `save()` + `watersupply/signals.py` (population cascade → `ConsumptionCapita` → `TotalWaterDemand` → `SupplySecurity`; `ExtractionWater`/`ImportedWater` → `TotalWaterProduction`, `OPEX`, `SupplySecurity`; `WaterTreatment`/`MeteredResidential`/`PipeNetwork` → `OPEX`; `PipeNetwork`/`UsersLocation` → `CoverageWaterSupply`; `NonRevenueWater` → same-year ILI): `Supply_Security -> Service_Time` (same formula as `views._build_indicators`), `Imported_Water/WT_Cost/Network -> OPEX` (`OPEX.save()` sums extraction `opex_EUR_m3 * current_extraction_Mm3_yr`, imported water, mean treatment `UnitaryOPEX_EUR_m3` of the year x volume, and pipe maintenance; `TotalWaterProduction` is deliberately not added, its energy cost is already inside `opex_EUR_m3`). `TotalWaterDemand`/`TotalWaterProduction` are stored in Mm³/day; `calculate_supply_security()` converts to m³/day. Still unimplemented: `Network -> Real_Losses` (`NonRevenueWater` records are entered directly, not linked to `PipeNetwork`); `calculate_collection_ratio()` ignores `userAffordability_PCT` and acceptance rate despite its docstring; `calculate_opex_recovery()` computes directly from stored totals rather than calling `calculate_collection_ratio()` or referencing NRW; `calculate_water_quality()`'s `acceptance_rate` is `Avg('acceptanceRate')`, unrelated to computed compliance — so `Samples_WQ -> User_Acceptance_WS` is unimplemented; `WaterTreatment` has no `save()`, so `WT_Efficiency -> WT_Cost` is unimplemented; `NonRevenueWater` ILI is only defined for real losses, so `Apparent_Losses -> ILI` is unimplemented; `UsersLocation.usersTotal/populationServed` and `SupplySecurity` for non-latest years are not refreshed by signals (OPEX/ExtractionWater/MeteredResidential/ImportedWater carry no year, so only the latest OPEX/SupplySecurity record is refreshed).

### Domain Apps

Each domain app contains spatial models related to a topic:

- **`administrative`** — Administrative hierarchy: Province > City > District > Neighborhood. Population and urban area cascade upward via signals.
- **`physicalEnv`** — LandCover (vector + raster), DEM, DSM, satellite imagery, surface/wall material properties, environmental costs.
- **`watersupply`** — Water infrastructure: extraction, treatment, pipe networks, coverage, NRW (non-revenue water), OPEX. Has `calculations.py` (pure query functions) + `views.py` (indicator assembly + HTMX recalculation).
- **`urban_heat`** — Thermal comfort rasters (UTCI, PET, MRT, LST, SVF, SUHII) and Nature-Based Solutions.
- **`housing`** — Supply/demand, mortgages, rentals, HPI, affordability stress. Has `calculations.py` + `views.py` following the same pattern as watersupply.
- **`builtup`** — Physical urban fabric: ZoningArea, Street, Park, Facility, Building, Property.
- **`nature`**, **`weather`**, **`Energy`** — Additional domain data.

### Indicator Pattern (watersupply, housing, urban_heat)

Domain dashboards follow a three-layer pattern:
1. **`calculations.py`** — Pure query functions that aggregate DB data. Each function documents its DAG edges.
2. **`views.py`** — `_get_province_data()` assembles all calculations into a dict; `_build_indicators()` is a pure function that derives display-ready metrics (supports what-if overrides like `consumption_override` or `interest_rate_override`); view functions render templates or return JSON.
3. **Templates** — HTMX-driven: a main page includes a partial grid that gets swapped on slider/input changes via `hx-get` to a `recalculate_indicators` endpoint.

`MOCK_DATA` dicts provide fallback values when the province doesn't exist in DB, allowing frontend development without a populated database.

Each domain's standalone dashboard (`water_indicators.html`, `heat_indicators.html`, `housing_indicators.html`) and its HTMX side-panel partial (`<app>/partials/indicators_panel.html`) render the **same** slider/gauge markup and are driven by the **same** JS file — do not duplicate slider/gauge logic between the two.

- **`Templates/indicators_base.html`** — shared `<html>/<head>`/htmx-script shell for the standalone pages. Extend it with `{% block slider %}`, `{% block grid %}`, `{% block extra_js %}`, etc.; put only domain-specific markup in the child template.
- **`core/static/js/indicators/<domain>.js`** (e.g. `water.js`, `heat.js`, `housing_panel.js`) — the slider/gauge JS for that domain, wrapped in an IIFE. Must re-run safely after every `htmx:afterSwap`, since the panel partial gets swapped back in on every recalculation — expose any function the swap needs to re-invoke (e.g. `window.initGauges`) as a global rather than a closure-local.
- **Do not write inline `<script>` blocks in indicator templates.** When adding or changing dashboard behavior, put the JS in `core/static/js/indicators/<domain>.js` and load it via `{% static %}`, following the existing files as the pattern to match.

### Signal-Driven Computations

- **`administrative/signals.py`** — When a Neighborhood is saved/deleted, population, density and urban_area cascade up through District > City > Province using `_recompute_population()` (sums both `currentPopulation` and `urban_area` per level). Uses `update()` (not `save()`) to avoid infinite loops.
- **`physicalEnv/signals.py`** — When a `LandCoverVector` row is saved/deleted, recomputes the affected City's Neighborhoods' `urban_area` from PostGIS intersection area against qualifying (urban fabric/road/rail/transport) land-cover polygons for the most recent `year`, in **one set-based `UPDATE … RETURNING`** (polygons fully inside a neighborhood skip `ST_Intersection`). It then re-enters `administrative/signals.py`'s cascade (`_recompute_population`) once per district and once for the city and province, since the `UPDATE` does not fire `post_save`. Area is `ST_Area` in the storage CRS's metres (geography cast if the CRS is geodetic).
- **`core/signals.py`** — `post_save` on every RASTER_REGISTRY model auto-exports to COG via `export_raster_to_cog()`; `post_save`/`post_delete` on every VECTOR_REGISTRY model bumps its cache version (`core/cache.py`), which invalidates the map's cached GeoJSON. Code that writes vector rows with `update()`/`bulk_create` must call `bump_layer_version()` itself.
- **Bulk writes** — wrap them in `importer/batching.py::deferred_cascades()` (= `administrative.signals.deferred_population_cascade()` + `physicalEnv.signals.deferred_urban_area()`) so the cascades run once per affected parent when the block ends instead of once per row. Both flush even if the block raises (errors during that flush are logged, not raised over the original). Use `physicalEnv.signals.schedule_urban_area_recompute(city_id)` rather than calling the recompute directly, so it respects an enclosing deferral.

### Importer System (`importer/`)

Two import paths:
1. **File upload** (`views.py`) — Upload GeoJSON/Shapefile, map fields to any registered model, preview, then import with savepoints. Uses `MODEL_OVERRIDES` dict for per-model upsert keys.
2. **External data** (`views_external.py`, `external_catalog.py`, `external_data.py`) — Catalog-driven import from PDOK, CBS, Sentinel-2, Google Earth Engine and the KNMI Data Platform. The KNMI source (`KNMIImporter.fetch_latest`, e.g. `knmi_wbgt` → `urban_heat.WetBulbGlobeTemperature`) uses the server-side `KNMI_API_KEY`, needs no bbox, and skips a file whose valid time is already stored. For districts and neighborhoods the import map picks the area of interest from cities and districts respectively (`bbox_from` in the catalog).

**Batching (`importer/batching.py`):**
- `SpatialParentIndex` resolves `__spatial_fk__` parents with prepared geometries + a bbox pre-check, probing each feature's `point_on_surface` (not its centroid). Parents are loaded with `.only("pk", "geom", <attrs read off them>)`.
- `BulkWriter` writes models listed in `BULK_IMPORT_MODELS` (LandCoverVector, Street, the nature layers) with `bulk_create`, 500 rows at a time, `ON CONFLICT DO UPDATE` for upserts on a unique field. Rows are grouped by their set of mapped fields so a missing property never blanks a stored value, and a failing batch is retried row by row. `bulk_create` skips `save()` and signals: a model belongs in the registry only if it has no `save()` override (`BulkImportRegistryTests` checks this) and its receivers are replayed by its finalizer. Add a `post_save` receiver to one of these models → add it to the finalizer or remove the model from the registry.
- `_import_geojson_features` and `_generic_import` run inside `deferred_cascades()`.
- Known gap: `_generic_import` (file upload) builds `field_by_name` from geometry/raster fields only, so mapped attribute columns (names, populations, FKs) are not imported.

### Raster Pipeline (`core/rasterOperations.py`)

1. PostGIS raster → `ST_AsGDALRaster` → temp GeoTIFF
2. Reproject to EPSG:4326 via rasterio
3. Convert to Cloud-Optimized GeoTIFF (COG) via `rio-cogeo`
4. COG stored on disk under `cogs/<app_label>/`
5. TiTiler serves tiles from the COG path

### Map Frontend (`mainMap/`)

- `map_view` renders `mainMap.html` with Mapbox token
- `available_layers` returns the full layer catalog (vector + WMS + raster) as JSON
- `model_geojson` builds one raw SQL statement per request (`_geojson_sql`): `ST_AsGeoJSON(ST_Transform(..., 4326), 6)`, FK display names via `LEFT JOIN` (not per-row sub-SELECTs), optional `?bbox=minLng,minLat,maxLng,maxLat` (`&&` on the GiST index) and `?zoom=z` (`ST_SimplifyPreserveTopology` to ~1 px below zoom 14; points never simplified). It returns PostgreSQL's JSON text as-is (`HttpResponse`, not `JsonResponse`) with an `X-Cache: HIT|MISS` header.
- GeoJSON responses are cached in the `geojson` cache alias (`CACHES` in settings: local memory, 64 entries, bodies ≤ 8 MB, 2 min) under a per-model version from `core/cache.py` (`layer_version` / `bump_layer_version`). The version only changes on writes made through Django, so edits from QGIS/psql/other scripts show up only when the entry expires — hence the short TTL (`GEOJSON_CACHE_TTL`). Local memory is per process: with several workers, point `CACHES` at Redis so invalidation reaches all of them.
- `layer_bounds` returns WGS84 `[[west, south], [east, north]]`, using `ST_EstimatedExtent` only for tables with ≥ `ESTIMATED_EXTENT_MIN_ROWS` (100 000) rows. The estimate is as old as the last `ANALYZE`, so smaller tables get an exact `ST_Extent`.
- `Layers.js`: vector layers with ≥ `VIEWPORT_LOAD_MIN_FEATURES` (5 000, in `Config.js`) features load by viewport and reload on `moveend` (debounced, superseded requests aborted); `zoomToLayer` uses `/bounds/` for them. Administrative layers always load whole — their click handlers and the admin-unit panels need every unit.
- Floating map overlays (toolbar, layers panel, side panel, population dock, legends, WMS scrubber, tour card) share `--overlay-bg`/`--overlay-blur`/`--overlay-shadow` tokens in `mainMap.css` and are draggable by their header via `core/static/js/Draggable.js::makeDraggable(el, handleSelector)` (delegated, so handles added later work; double-click the handle to reset; disabled below 768 px). Wiring is in `Events.js::initializeUI`.
- WMS tiles (`addWmsLayer`, `wmsTileUrlForTime`, the groundwater source) use `WMS_TILE_SIZE` (512, `Config.js`) for both `tileSize` and the `width`/`height` params — keep the two equal. Remote WMS cost is per request (~0.5–3 s each at KNMI), so bigger tiles = fewer requests. `weather/views.py::wms_tile_proxy` caches tiles in `CACHES["wms_tiles"]` (24 h for `TIME=` frames, 5 min otherwise), sends matching `Cache-Control`, and reports `upstream;dur` / `cache;desc` in `Server-Timing`. Upstream calls go through the module-level `_session` (keep-alive); mock `weather.views._session.get` or `_fetch_with_retry` in tests, and clear `get_cache("wms_tiles")` in `setUp`.
- All legends live in `#legend-stack`; `Layers.js::repositionDynamicLegends()` moves the stack so it clears the side panel and the population dock (re-run by observers in `Events.js`), unless the user has dragged it. Append new legends to `#legend-stack`, not `.map-wrapper`.
- Templates live in `Templates/` (capital T, configured in settings)
- `core/static/js/mainMap.js` holds `mainMap.html`'s page-level wiring (map init, right-panel button handlers, year selector, guided tour, the admin-unit-driven panel registry). It depends on `Config.js`/`map_init.js` and on `window.MAPBOX_ACCESS_TOKEN` being set inline by `mainMap.html` before it loads. As with the indicator dashboards, keep new map-page behavior in this file rather than adding inline `<script>` blocks to `mainMap.html`.

### API Routes

| Path | Purpose |
|---|---|
| `/` | Main map view |
| `/api/layers/` | Layer catalog JSON |
| `/api/layers/<app>/<model>/geojson/` | GeoJSON for vector model (`?bbox=` WGS84, `?zoom=`; cached) |
| `/api/layers/<app>/<model>/bounds/` | Bounding box extent in WGS84 |
| `/api/raster/<app>/<model>/tiles/` | TiTiler tile URL for raster |
| `/api/raster/<app>/<model>/info/` | Raster metadata |
| `/importer/` | File upload import |
| `/watersupply/` | Water supply indicators dashboard |
| `/urban_heat/` | Urban heat views |
| `/housing/` | Housing indicators dashboard |

### Testing

Tests use `PostGISTestRunner` (`DigitalTwin/test_runner.py`) which creates the test DB, installs PostGIS extensions, and patches Django's `prepare_database` to avoid superuser requirement. Always use `--settings=DigitalTwin.settings_test --keepdb` (see Common Commands). Tests that hit the GeoJSON endpoint should clear the `geojson` cache in `setUp` (`core.cache.get_cache('geojson').clear()`): `TestCase` rolls back the DB but not the cache. Pin query counts with `assertNumQueries` on hot endpoints (`ModelGeoJsonTests` keeps `model_geojson` at one query).

## Key Patterns to Follow

- All spatial models use `srid=settings.COORDINATE_SYSTEM` (EPSG:28992), not hardcoded SRIDs
- Models with computed fields implement logic in `save()` — check existing patterns before adding new ones
- Use `models.DO_NOTHING` for FK on_delete in spatial/reference models (project convention)
- Population cascading uses `update()` not `save()` to prevent signal recursion
- Raster models need a `cog_path` field to participate in the COG auto-export pipeline
- The GeoJSON API transforms to EPSG:4326 at query time via `ST_Transform`
- No top-level imports of heavy libraries (numpy, scipy, pandas, geopandas, rasterio, rio-cogeo, rio-tiler, openeo, ee) in modules loaded at startup or by the URLconf — models, signals, `apps.py`, views, `core/rasterStyles.py`, `importer/utils.py`. Import them inside the function that uses them. At module level they cost 0.4–1.6 s each at every process start and on the first request after each `runserver` reload. When a test mocks such a function, patch it where it's defined (e.g. `core.rasterOperations.export_raster_to_cog`), not where it's used.
- Performance work is tracked in `docs/PERFORMANCE.md`: §0–§3 are implemented (measurement, GeoJSON endpoint, land-cover signal, importer batching); §4–§12 are still proposals
- Frontend CSS uses Tailwind with crispy-tailwind for forms
- Frontend JS lives in `core/static/js/` (page-level files like `mainMap.js`, domain files under `indicators/`), not in inline `<script>` blocks in templates — see [Indicator Pattern](#indicator-pattern-watersupply-housing-urban_heat) and [Map Frontend](#map-frontend-mainmap)

## TODOs

Collected from inline `#TODO` comments across the codebase:


### physicalEnv
- Auto-calculate `LandCoverVector.percentage` from geom area vs Province total area (`physicalEnv/models.py`)
- Add Vegetation Coverage and Builtup Coverage as additional fields on `LandCoverVector` (`physicalEnv/models.py`)

### builtup
- Define connectivity index and calculation method for `Building.connectivity` (`builtup/models.py`)
- Define green visibility index and calculation method for `Property.greenVisibility` (`builtup/models.py`)

### watersupply
- `UsersLocation.neighborhood` FK — decide whether this should be City-level or per-point (`watersupply/models.py`)
- `AvailableFreshWater.infiltrationRate_cm_h` — should be calculated from land cover and soil type (`watersupply/models.py`)
- `TotalWaterProduction.source` — handle imported or multiple sources (`watersupply/models.py`)

### housing
- Validate affordability stress level thresholds against literature (`housing/models.py`)
- Connect `HousingAffordability.medianExpenditure` with water and electricity expenditure data (`housing/models.py`)
- Decide whether affordability index should use median disposable income instead of median income (`housing/models.py`)

### urban_heat
- Add measurement method, source, and metadata fields to raster models: MRT, UTCI, SVF, LST (`urban_heat/models.py`)


## graphify
- **graphify** (`.claude/skills/graphify/SKILL.md`) - any input to knowledge graph. Trigger: `/graphify`
When the user types `/graphify`, use the installed graphify skill or instructions before doing anything else.


This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

Rules:
- For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.

