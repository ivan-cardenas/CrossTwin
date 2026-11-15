
# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CrossTwin is a Django-based digital twin platform for geospatial urban data (water supply, urban heat, energy, housing, nature). It uses PostgreSQL/PostGIS for spatial storage, Mapbox GL JS for map rendering, and TiTiler (FastAPI) for raster tile serving.

The project focuses on **Dutch geospatial data** — the default CRS is EPSG:28992 (Amersfoort / RD New), configured via `COORDINATE_SYSTEM` in `.env`.

## Common Commands

```bash
# Install / update the environment from pyproject.toml + uv.lock (creates .venv)
uv sync                      # --python 3.13 to pick a version, --no-dev to skip ipykernel
uv add <pkg>                 # add a dependency (updates pyproject.toml and uv.lock)
uv lock --upgrade-package <pkg>

# First-time database setup (Windows): creates the PostGIS database + user,
# writes .env from .env_template and offers migrate or the example data.
# A cmd launcher with the PowerShell script embedded after its ##PS-START marker.
setup_db.bat

# Run everything through `uv run`: it uses .venv without activation and syncs it
# with uv.lock first (activating .venv + plain `python` also works after `uv sync`)

# Check PostgreSQL + PostGIS (start.bat runs this first and stops on failure)
uv run python tools/check_postgres.py

# Start both Django and TiTiler (or use start.bat)
uv run python manage.py runserver 8000
uv run uvicorn tiler:app --port 8001 --reload

# Database migrations: always generate them with makemigrations, never write a
# schema migration file by hand (it costs tokens and drifts from the models). For a
# data step, run `makemigrations <app> --empty -n <name>` and add only the RunPython.
uv run python manage.py makemigrations
uv run python manage.py migrate

# Run all tests (uses custom PostGIS test runner). Always pass --keepdb: without it
# Django drops the test DB the runner prepared and recreates it without PostGIS
# ("type geometry does not exist"). --noinput avoids the interactive prompt.
uv run python manage.py test --settings=DigitalTwin.settings_test --keepdb --noinput

# Run tests for a single app
uv run python manage.py test importer --settings=DigitalTwin.settings_test --keepdb --noinput

# Export COGs for raster models
uv run python manage.py export_cogs

# Thermal comfort (SOLWEIG-GPU: torch with CUDA 12.8 wheels, pet-adjusted for PET) — optional extra
uv sync --extra solweig

# LST from Landsat 9 + the NDVI layer (Earth Engine, GEE_PROJECT_ID); --list-scenes, --scene, --dry-run
uv run python manage.py calculate_lst --city Enschede

# Package the DB of .env + its COG files as example data, or load such a package into an empty DB
# (both default to example/crosstwin_example_data.zip, which is committed)
uv run python tools/example_db.py dump
uv run python tools/example_db.py load

# Tree heights from the DSM for stored trees without one (scales the 3D tree models)
uv run python manage.py fill_tree_heights --city Enschede

# Slowest SQL statements from pg_stat_statements (--order mean|calls|rows, --reset)
uv run python manage.py db_stats

# Profile GET requests (run 1 = cold process, run 2 = warm); --save x.prof for snakeviz
uv run python tools/profile_requests.py "/api/admin-unit/?lng=6.895&lat=52.219" --runs 2

# docs/DATA_SOURCES.md: every importer dataset (importer/external_catalog.py) + other sources and cited rules
# (core/data_sources.py); core/tests/test_data_sources.py fails when it is out of date
uv run python tools/data_sources.py

# Architecture diagrams: check the palette (contrast + colour-blind separation), build SVGs, export PNG/PDF
uv run python tools/palette_check.py && uv run python tools/arch_diagrams.py && uv run python tools/arch_export.py

# Interactive DAG view (docs/dag_view.html): core/DAG.dot + per-edge status from core/dag_status.py
# (update an edge's status there when it changes; core/tests/test_dag.py checks it matches DAG.dot)
uv run python tools/dag_view.py

# Which modules are slow to import
uv run python -X importtime -c "import django; django.setup(); import DigitalTwin.urls" 2> imports.log
```

Measurement flags in `.env` (see `docs/PERFORMANCE.md` §0): `QUERY_STATS=true` (default = `DEBUG`) adds a `Server-Timing` header (DB time + query count, visible in DevTools → Network → Timing) and `X-DB-Queries` to every response and logs each request on `crosstwin.querystats` (WARNING above `QUERY_STATS_SLOW_MS`, default 500). `SQL_LOG=true` prints every SQL statement (only when `DEBUG=true`).

## Architecture

### Django Settings & Two-Server Setup

- **Django project**: `DigitalTwin/` — settings load from `.env` via `python-dotenv`
- **TiTiler**: `tiler.py` — a separate FastAPI app serving COG raster tiles on port 8001. Django proxies to it via `TITILER_BASE_URL` env var.
- Windows GDAL/GEOS DLLs are auto-discovered from the venv's `osgeo` package in `settings.py`.

### Dependencies (`pyproject.toml`, `uv.lock`)

- Managed with uv; `uv.lock` is committed and resolved for every OS and Python ≥ 3.12 (no `[tool.uv] environments` restriction — keep it universal).
- `gdal` is a **Windows-only** dependency: PyPI has no Windows wheel, so `[tool.uv.sources]` maps it to Christoph Gohlke's GitHub release wheels (`cgohlke/geospatial-wheels`; `cgohlke.com` is *not* a package index), one entry per `python_version` × `platform_machine` (`AMD64`/`ARM64`), all GDAL 3.13.3 (v2026.8.20) for Python 3.12–3.15. Python ≥ 3.12 is set by `pet-adjusted` (solweig extra). To bump GDAL or add a new Python version, add the wheel URLs for each arch and update the `gdal==` line in `[project].dependencies`, then `uv lock` and regenerate `requirements.txt` (`uv export --format requirements-txt --no-hashes -o requirements.txt`).
- On Linux/macOS `osgeo` is not installed: GeoDjango loads the system libgdal/libgeos (`apt install gdal-bin libgdal-dev` / `brew install gdal`), and rasterio, pyogrio and pyproj bundle their own GDAL/PROJ. Code must not `import osgeo` outside the Windows block in `settings.py`.
- Optional extra `solweig` (`uv sync --extra solweig`): `solweig-gpu`, `torch`, `pet-adjusted` (PET; brings `pythermalcomfort`; not its own `[solweig]` extra, which pins `gdal` from PyPI) for the thermal comfort tool. `[tool.uv.sources]` takes `torch` from the explicit `pytorch-cu128` index on Windows/Linux (CUDA wheels; they fall back to the CPU at run time), PyPI on macOS. solweig-gpu imports `osgeo`: fine on Windows (Gohlke wheel), on Linux it needs GDAL Python bindings matching the system libgdal. Plain `uv sync` removes the extra again (and any package not in `uv.lock`). Without it the tool's views answer 503 with the install hint.
- PostgreSQL drivers are `psycopg[binary]` (Django, `test_runner.py`, `tools/example_db.py`) and `psycopg2-binary` (only tried first by `tools/check_postgres.py`, which falls back to `psycopg`), so no libpq headers are needed on any OS.

### Model Registry System (`core/utils.py`)

The central architectural pattern. `build_model_registry()` scans a hardcoded list of allowed apps (`administrative`, `physicalEnv`, `urbanHeat`, `watersupply`, `weather`, `builtup`, `Energy`, `housing`, `nature`) and builds four registries:

- **`MODEL_REGISTRY`** — all models from allowed apps
- **`VECTOR_REGISTRY`** — models with GeometryField (no RasterField)
- **`RASTER_REGISTRY`** — models with RasterField
- **`WMS_REGISTRY`** — models with "WMS" in the registry key

These registries power generic API endpoints, the map layer catalog, and the importer. When adding a new domain app, it must be added to the `allowed_apps` list in `core/utils.py` and to `INSTALLED_APPS` in `settings.py`.

### DPSIR Causal Network (`core/DAG.dot`)

The project follows the **DPSIR framework** (Driver → Pressure → State → Impact → Response) to model causal relationships between urban systems. The full causal graph is defined in `core/DAG.dot` (Graphviz format). Each domain app's `calculations/indicators.py` documents which DAG edges its functions implement via comments like `# DAG edges: Central_Bank -> Mortgage`.

When adding new calculations, trace the relevant DAG edges and document them in the function docstring to maintain traceability between the causal model and code. Edges whose target is stored must follow the signal/receiver contract in [Implementing a DAG Edge](#implementing-a-dag-edge-signalreceiver-contract).

#### DAG Edge Coverage Gaps

The count of implemented / partial / gap edges and the verified gap list per app live in [`docs/DAG_COVERAGE.md`](../docs/DAG_COVERAGE.md). Read it before claiming an edge is (not) implemented, and update it with every edge change. The `/dag-edge` skill walks through the whole contract.

### Domain Apps

Each domain app contains spatial models related to a topic:

- **`administrative`** — Administrative hierarchy: Province > City > District > Neighborhood. Population and urban area cascade upward via signals.
- **`physicalEnv`** — LandCover (vector + raster), DEM, DSM, satellite imagery, surface/wall material properties, environmental costs. `HILUCSLandUse` is the INSPIRE HILUCS codelist (code `6.3.2`, label, description; all 98 values loaded by migration 0003), referenced by FK (`builtup.ZoningArea.zone_type`). `physicalEnv/hilucs.py` parses a HILUCS URI into its code — always look up by code, PDOK misspells some URIs — and `hilucs_q(field, codes)` filters a code and everything below it (housing's zoning groups use it). `SoilType` (code + name of the BIS Nederland soil map 1:50 000, unique together) derives in `save()` the SCS hydrologic soil group A–D from the name's Dutch texture words (`physicalEnv/calculations/soil.py::classify_soil_group`; most restrictive layer wins, all 171 names of the 2025 map classify) and the group's final infiltration rate range; `SoilArea` polygons point to it (catalog `bodemdata_soil_map`, bulk-written). `SoilType.unitCode`/`unitName` hold the main legend unit (`first_soilcode`/`first_soilname`, filled by the lookup's `defaults_from`, which also updates existing rows); the map colours polygons by it with the BRO Bodemkaart legend colours in `mainMap/styles/soilStyles.py` (305 units; layer styles otherwise live in `mainMap/styles/layerStyles.py`). `soil.py` also holds the TR-55 curve numbers per CORINE land-cover class (keywords match at word starts) and the SCS equations; `soil_landcover_composition(geom)` is the one DB query (soil x latest land-cover year, clipped to the unit). The water dashboard's Groundwater Recharge card shows as its main value the unit's yearly recharge (mm/yr and Mm³/yr, with a rain = runoff + ET + recharge bar; `views._recharge_indicators` → `watersupply/calculations/chain.py::yearly_water_balance_mm`, the same balance `AvailableFreshWater.save()` stores, over the nearest station's latest complete KNMI year fetched by `calculate_infiltration`), and applies the SCS equations for the Rain Event slider (`rain_mm`, default 25 mm; event runoff depth in mm and infiltrated share) in the pure `_build_indicators`, weighting runoff per piece rather than averaging CN. Without daily KNMI rows the card falls back to the event runoff depth. `GroundwaterDepth` (raster, one row per `statistic` GHG/GLG/GVG; catalog `bodemdata_ghg`/`bodemdata_glg`, BIS Nederland WCS, 50 m, cm below ground, 254 = 254 cm or deeper, 255 nodata) stays in Postgres: the composition query reclassifies the season's statistic (`SEASONS`: wet = GHG, dry = GLG; dashboard switch `season`) below `SHALLOW_GROUNDWATER_CM` (60, NEH 630) to polygons and reports those pieces as group D, except on drained land covers (`DRAINED_LAND_COVER`: built-up and paved classes keep their texture group, the drained letter of NEH 630's dual group). BIS has no groundwater values for most built-up cells (85 % in Enschede) or water; nodata counts as not shallow, and water/wetland curve numbers are 100/98 for every group. WCS entries can set `wcs_axis_labels` (BIS needs `X`/`Y`, PDOK takes the default `x`/`y`), and `load_raster_into_target_model` adds a catalog `statistic` to the upsert key.
- **`watersupply`** — Water infrastructure: extraction, treatment, pipe networks, coverage, NRW (non-revenue water), OPEX. Has `calculations/indicators.py` (pure query functions) + `views.py` (indicator assembly + HTMX recalculation).
- **`urban_heat`** — Thermal comfort rasters (UTCI, PET, MRT, LST, SVF, SUHII) and Nature-Based Solutions. `urban_heat/lst/` computes LST from Landsat 9 (or 8) with the SMW algorithm and CrossTwin's NDVI layer: `coefficients.py` (SMW table), `smw.py` (pure numpy equations), `grid.py`, `gee.py` (Earth Engine inputs), `pipeline.py::calculate_lst()`. `urban_heat/solweig/` computes Tmrt, UTCI and PET for a map view and hour with SOLWEIG-GPU (`inputs.py`, `met.py`, `pipeline.py`, `views.py`; runs are `ThermalComfortRun` rows; `docs/THERMAL_COMFORT.md`). `urban_heat/calculations/chain.py` holds the pure weather-only heat-stress equations of the heat panel's weather what-if (see Weather pill). `NeighborhoodHeat` (one row per neighborhood, KEA): PET means 2012/2022, RIVM class, cooling indoors/outdoors, canopy and shade shares.
- **`housing`** — Supply/demand, household size (persons per home, from CBS), mortgages, rentals, HPI, affordability stress. Has `calculations/indicators.py` + `views.py` following the same pattern as watersupply, plus `chain.py` (pure equations) and `signals.py` (population / household size → demand and dwelling residents). `NeighborhoodSocialProfile` (one row per neighborhood, KEA): rental share, socio-economic status, frail health, loneliness, neighborhood type.
- **`builtup`** — Physical urban fabric: ZoningArea, Street, Facility, Building, Property (parks are `nature.GreenSpaces`, see `nature`). `Street.source_project` / `Building.source_project` (plain ids, builtup never imports housing) mark rows the neighbourhood generator wrote (`builtup/calculations/generative.py`: streets first, then blocks, plots and footprints per typology; `materialise.py` stores them; Map Frontend › Neighbourhood generator). `Building` carries KEA enrichment fields (`canopyCover_pct`, `meetsCanopy30Rule`, `facadeShadeScore`, `floodDepth_p99_m`, `floodDepthClass`), and `NeighborhoodClimateRisk` (one row per neighborhood, KEA) holds pile-rot and settlement risk per scenario and dry floors. These KEA values are stored inputs, no DAG edge reads them yet. `StreetCanyon` (one row per street, a map layer) stores the canyon H/W: inputs from `builtup/calculations/canyon.py::street_inputs` (one SQL statement: streets trimmed 10 m at the ends, cut into ≤ 100 m pieces, 30 m single-sided buffers; area-weighted building height per side, facade distance per side), equations in `builtup/calculations/chain.py` (H = mean of both sides, open side 0; W = typed `Street.width` (now nullable), else facade gap, else 8/12/20 m per class), refreshed by `builtup/signals.py::refresh_canyons` (set-based upsert, `bump_layer_version`, custom signal `canyons_changed`; deferred by `deferred_canyon_refresh` inside `deferred_cascades()`; the bulk `Street` finalizer `_refresh_canyons_over`; editor refreshes journalled via `canyon_rewriting`/`canyon_created`). Has `calculations/indicators.py` + `views.py` (building stock/coverage/FAR, type mix, construction period, street density clipped to the unit, park area and facilities per inhabitant; what-if `green_added_ha`). **Degree of Urbanisation** (DAG node `Degree_Urbanisation`, `docs/DEGREE_OF_URBANISATION.md`): each neighborhood's `currentPopulation` is shared equally over its residential properties (`Property` with *Residential function*, never per building; no dwellings → by area) into `PopulationAllocation` rows per 100 m and 1 km cell (EPSG:28992-aligned, CBS grid codes), summed into `UrbanisationCell` (concrete table hidden; map layers are the proxies `UrbanisationCellLocal` 100 m and `UrbanisationCellOriginal` 1 km, latest year via `current`), classified by `builtup/calculations/degurba.py` (GHSL thresholds; 100 m uses a 3 × 3 window over settlement land so city edges are not diluted, settlement-only hole filling/smoothing; 1 km is the original rule set), and summarised per neighborhood/district/city in `Urbanisation` (L1/L2 class, population per class, urban area, rate = CAGR of the urban area between stored CrossTwin years, mirrored to `City.urbanizationRate`). The built-up dashboard's card shows it, with the population dock as an in-memory what-if (`urbanisation.dashboard` / `whatif_unit`).
- **`nature`** — Water bodies, forests, trees and green spaces. `GreenSpaces` holds every green space, parks included: a park is `type = 'park'` (`nature.models.PARK`, `GreenSpaces.objects.parks()`); there is no separate park model (`builtup.Park` was merged into it on 2026-11-11, `nature/0004_move_builtup_parks`). `save()` derives `area`, the neighborhood (point on surface, when not given) and the city. The built-up dashboard's park area per inhabitant and `urban_heat.calculate_green_area` count *park space*: parks plus BGT recreation areas (`type` starting with `recreatie`, `RECREATION_PREFIX`; `GreenSpaces.objects.park_space()`); other types (gardens) do not count. Both merge overlapping polygons before measuring (built-up: `ST_Area(ST_Union(geom))` of the unit's neighborhoods' park space, not clipped; heat: clipped to the unit and unioned with green land cover).
- **`weather`**, **`Energy`** — Additional domain data.

### Indicator Pattern (watersupply, housing, urban_heat, builtup)

Domain dashboards follow a three-layer pattern:
1. **`calculations/indicators.py`** — Pure query functions that aggregate DB data. Each function documents its DAG edges.
2. **`views.py`** — `_get_adminUnit_data()` assembles all calculations into a dict; `_build_indicators()` is a pure function that derives display-ready metrics (supports what-if overrides like `consumption_override` or `interest_rate_override`); view functions render templates or return JSON.
3. **Templates** — HTMX-driven: a main page includes a partial grid that gets swapped on slider/input changes via `hx-get` to a `recalculate_indicators` endpoint.

`MOCK_DATA` dicts provide fallback values when the province doesn't exist in DB, allowing frontend development without a populated database.

Each domain's standalone dashboard (`water_indicators.html`, `heat_indicators.html`, `housing_indicators.html`, `builtup_indicators.html`) and its HTMX side-panel partial (`<app>/partials/indicators_panel.html`) render the **same** slider/gauge markup and are driven by the **same** JS file — do not duplicate slider/gauge logic between the two.

- **`Templates/indicators_base.html`** — shared `<html>/<head>`/htmx-script shell for the standalone pages. Extend it with `{% block slider %}`, `{% block grid %}`, `{% block extra_js %}`, etc.; put only domain-specific markup in the child template.
- **`core/static/js/indicators/<domain>.js`** (e.g. `water.js`, `heat.js`, `housing_panel.js`, `builtup.js`) — the slider/gauge JS for that domain, wrapped in an IIFE. Must re-run safely after every `htmx:afterSwap`, since the panel partial gets swapped back in on every recalculation — expose any function the swap needs to re-invoke (e.g. `window.initGauges`) as a global rather than a closure-local.
- **"?" help buttons:** `{% load indicator_help %}{% info_help "<domain>.<card>" %}` renders a card's help (what it is, how it is measured, friendly equations: `{a | b}` = stacked fraction) from `core/indicator_help.py`. `core/static/js/info_popover.js` (loaded by `mainMap.html` and `indicators_base.html`) shows it in one popover created under `<body>`: inside the side panel, the panel's `backdrop-filter` would offset and clip a `position: fixed` popover. When an equation changes in code, update its entry; `core/test_indicator_help.py` checks every key used in a template has a complete entry.
- **Do not write inline `<script>` blocks in indicator templates.** When adding or changing dashboard behavior, put the JS in `core/static/js/indicators/<domain>.js` and load it via `{% static %}`, following the existing files as the pattern to match.

### Signal-Driven Computations

- **`administrative/signals.py`** — When a Neighborhood is saved/deleted, population, density and urban_area cascade up through District > City > Province using `_recompute_population()` (sums both `currentPopulation` and `urban_area` per level). Uses `update()` (not `save()`) to avoid infinite loops.
- **`physicalEnv/signals.py`** — `landcover_albedo` (`pre_save`): a `LandCoverVector` without a material takes its class's `default_material`, and a geometry change drops a measured `albedo` (the bulk finalizer replays the material part with `albedo.set_default_materials`). `LandCoverVector.percentage` = polygon area / its City's `area_km2` x 100, set by a `pre_save` receiver (`landcover_percentage`; not a `save()` override, the model is bulk-written), set-based by `landcover.refresh_percentages(city_id)` in the bulk finalizer and when a City's area changes (`city_area_saved`); null without a city. When a `LandCoverVector` row is saved/deleted, recomputes the affected City's Neighborhoods' `urban_area` from PostGIS intersection area against qualifying (urban fabric/road/rail/transport) land-cover polygons for the most recent `year`, in **one set-based `UPDATE … RETURNING`** (polygons fully inside a neighborhood skip `ST_Intersection`). It then re-enters `administrative/signals.py`'s cascade (`_recompute_population`) once per district and once for the city and province, since the `UPDATE` does not fire `post_save`. Area is `ST_Area` in the storage CRS's metres (geography cast if the CRS is geodetic).
- **`core/signals.py`** — `post_save` on every RASTER_REGISTRY model auto-exports to COG via `export_raster_to_cog()`; `post_save`/`post_delete` on every VECTOR_REGISTRY model bumps its cache version (`core/cache.py`), which invalidates the map's cached GeoJSON. Code that writes vector rows with `update()`/`bulk_create` must call `bump_layer_version()` itself.
- **Bulk writes** — wrap them in `importer/batching.py::deferred_cascades()` (= `administrative.signals.deferred_population_cascade()` + `physicalEnv.signals.deferred_urban_area()` + `watersupply.signals.deferred_water_refresh()` + `housing.signals.deferred_housing_refresh()` + `builtup.signals.deferred_canyon_refresh()` + `builtup.calculations.urbanisation.deferred_urbanisation_refresh()`; the CBS OData import runs inside it) so the cascades run once per affected parent when the block ends instead of once per row. Both flush even if the block raises (errors during that flush are logged, not raised over the original). Use `physicalEnv.signals.schedule_urban_area_recompute(city_id)` rather than calling the recompute directly, so it respects an enclosing deferral.

### Implementing a DAG Edge (signal/receiver contract)

**Every new or changed indicator that implements an edge of `core/DAG.dot` must follow this contract.** It is how the causal graph becomes executable: there is no central graph engine. Each node computes itself from its inputs, each edge is a receiver that re-runs the target when the source changes, and a change travels Driver → Impact one edge at a time. `watersupply/` is the reference implementation; copy its shape.

1. **Node = model, equation = the node's `save()`.** A stored DAG node is a model. Its derived fields are computed in its own `save()` from its inputs (its incoming edges). The `save()` docstring lists them as `DAG edges: Source -> Target`, using the node names from `DAG.dot` exactly. Never compute a node's value inside a receiver and write it onto the target. The receiver only triggers the target's `save()`.
2. **One equation, two callers: `<app>/calculations/chain.py`.** Any equation that both the stored path (`save()`) and the dashboard (`views._build_indicators`) need lives once, as a pure function in `<app>/calculations/chain.py` (no ORM queries; at most one clearly named DB helper such as `chain.baseline_population`). `save()` calls it with stored inputs; `_build_indicators` calls it with the request's what-if inputs. Never re-type an equation in `views.py`. Add a parity test: with default controls, the dashboard equals the stored value (`DashboardIsADeviationFromTheBaselineTests`).
3. **Edge = receiver in `<app>/signals.py`.** For an edge `A -> B`, add a `@receiver(post_save, sender=A)` (plus `post_delete` when deleting A changes B) whose body re-saves the affected B rows with `_resave(queryset)`. Re-saving B runs B's `save()` and fires B's own `post_save`, so the next edge (`B -> C`) runs automatically. Write that next edge as its own receiver; don't chain several edges inside one receiver. Every receiver:
   - has a unique `dispatch_uid` (`"<app>_<source>_<saved|deleted>"`);
   - returns early on `raw=True` (fixtures, backup restore). Map editing's restore must then trigger the cascade itself (see Map Editing);
   - names its edge(s) in a docstring or comment (`DAG edge: A -> B`);
   - is connected by the app's `apps.py::ready()` importing `signals`.
4. **Failures never block the source save.** Refresh dependents through `_resave()`, which logs `ValidationError` instead of raising it. A missing input in the target keeps its stored value rather than writing zero (e.g. `SupplySecurity.save()` without production).
5. **No loops.** The graph is acyclic (`core/test_dag.py`); a real feedback is drawn as a lagged edge `[lag=1, style=dashed]` (one planning step later, never a receiver; listed in `core/test_dag.py::LAGGED_EDGES`, argued in `docs/DAG_REVISIONS.md`; today only `Network -> New_Units`); keep the code acyclic too. A receiver never writes to a node upstream of its source. Aggregations that would re-trigger themselves (parent sums of children) are written with `queryset.update()`, which fires no signal. After an `update()`:
   - call `bump_layer_version()` for vector models;
   - if another app depends on the aggregated value, send a **custom signal** (`django.dispatch.Signal`, defined in the upstream app, e.g. `administrative.signals.city_population_changed`) and let the downstream app subscribe to it.
6. **Cross-sector edges point one way.** The downstream app imports and subscribes to the upstream app's model or signal. The upstream app never imports the downstream app. A new sector that depends on population, for instance, adds a receiver for `city_population_changed` / `PopulationProjection` in its own `signals.py`; `administrative` stays untouched.
7. **Bulk writes stay O(parents).** Each app's "refresh city X" helper must check a thread-local deferral and queue the id instead of working (pattern: `watersupply.signals.deferred_water_refresh` / `_refresh_city_water`). Register the context manager in `importer/batching.py::deferred_cascades()` (mind the `ExitStack` order: whatever is fed by another cascade must exit after it, i.e. be entered first). Run importer loops inside `deferred_cascades()`. `bulk_create` skips signals entirely, so a model written by `BulkWriter` needs its receivers replayed by its finalizer.
8. **What-ifs never write.** Sliders and switches run the `chain.py` functions per request with override values. They must not save models or fire signals. The stored database holds the baseline; a what-if is a deviation from it. Geometric what-ifs (map editing) are real saves and go through rule 3 like any import.
9. **Year semantics.** Stored records with a `year` use the baseline population of *that* year (`watersupply.calculations.chain.baseline_population(city, year)`: CBS median forecast, no extra growth, current population as fallback), not `City.currentPopulation`. Records without a year refresh only the latest dependent record (see the OPEX/SupplySecurity note under watersupply).
10. **Tests and docs, per edge.** For each new edge add:
    - a test that saving (and deleting, if handled) the source updates the target;
    - a deferral test when the source is bulk-imported (count refreshes with `mock.patch.object(signals, '_resave', wraps=...)`).

    Then update `docs/functions_and_equations.tex` (equation, source location, status), the coverage count, gap list and edge → function table in `docs/DAG_COVERAGE.md`. The `/dag-edge` skill is the checklist.

Pure dashboard-only statistics that no other node consumes (e.g. infiltration for a rain event, street density) may stay in `calculations/indicators.py` without a receiver. They still document their `DAG edges:`, and they move to rules 1–3 as soon as a downstream node needs their value stored.

#### Edge → function map (propagated edges)

The table of every propagated edge (target computed in, triggered by which receiver) is in [`docs/DAG_COVERAGE.md`](../docs/DAG_COVERAGE.md#edge--function-map-propagated-edges). Add a row there for each new edge.

### Importer System (`importer/`)

Two import paths:
1. **File upload** (`views.py`) — Upload GeoJSON/Shapefile, map fields to any registered model, preview, then import with savepoints. Uses `MODEL_OVERRIDES` dict for per-model upsert keys.
2. **External data** (`views_external.py`, `external_catalog.py`, `external_data.py`) — Catalog-driven import from PDOK, CBS, Sentinel-2, Google Earth Engine and the KNMI Data Platform. The KNMI source (`KNMIImporter.fetch_latest`, e.g. `knmi_wbgt` → `urban_heat.WetBulbGlobeTemperature`) uses the server-side `KNMI_API_KEY`, needs no bbox, and skips a file whose valid time is already stored. KNMI entries with `format: "wms"` (`knmi_radar_forecast`) instead register a `weather.WMSLayer` row through the shared `register_wms_layer()` (also used by PDOK/Sentinel-2 WMS): `wms_name` fixes the row name (the tile proxy's URL segment), `wms_options` sets model fields such as `has_time_dimension`/`api_key_setting` (ignored when the model lacks them), and an explicit `legend_url` skips the GetCapabilities legend lookup. BAG buildings (`pdok_buildings`) carry no height: after the import `external_data.py::_fill_building_heights` measures empty `height_m` from the DSM (`physicalEnv/calculations/building_heights.py`: P70 of the DSM inside the footprint − median ground, 3DBAG's LoD1.2 roof height; 2–350 m kept), inside `deferred_cascades()` so the canyon refresh reads them. A DSM import does the same for stored buildings under it that still have none (`_heights_after_dsm` → `building_heights.fill_under_dsm`, which also schedules their canyons and bumps the layer cache), so the order of the two imports does not matter. Catalog entries can name an `import_first` dataset (`pdok_buildings` → `pdok_dsm_ahn_raster`): the page shows an *Import first* notice while its model has no rows, asks before starting (add it to the run, or go on without), and `views_external._order_import_first` runs it before the dependent dataset. For districts and neighborhoods the import map picks the area of interest from cities and districts respectively (`bbox_from` in the catalog). The planned land use ATOM feed (`pdok_landcover_kadaster`, `_import_atom_gml_features`) streams PDOK's ~29 GB national GML and imports each `plu:ZoningElement` inside the bbox as a `ZoningArea`: `hilucslanduseHref` (its `plu:hilucsLandUse` href) → `zone_type` via an `__fk_lookup__` with `"parser": "hilucs_href"`, and title/plan type/valid-from from its `SpatialPlan` (plans come first in the file and are cached). `__fk_lookup__` resolution is shared by the GeoJSON and GML paths (`_resolve_fk_lookups`); parsers live in `_FK_LOOKUP_PARSERS`. The BIJ12 source (`bij12_nnn`, the provinces' Natuurnetwerk Nederland from the Informatiekaart Natuur WFS `IMNa_IKN:natuur_netwerk_nederland`, no key; routed to `PDOKImporter.fetch_wfs`) imports `nature.ProtectedArea` of type NNN, upserting on the feature id; the neighbourhood generator's site check keeps buildings out of it. The OpenStreetMap source (`OSMImporter.fetch`, `format: "overpass"`) runs each entry's `osm_query` statements on the Overpass API (`OVERPASS_URL` in `.env` overrides the public instance; on 429/502/503/504 or a connection error `OSMImporter._post` tries the next of `OVERPASS_MIRRORS`, comma-separated, default private.coffee and kumi.systems), with `out center` for point models and `out geom` otherwise. It converts the elements to GeoJSON (multipolygon relations are rebuilt from their member ways with shapely `polygonize`) and imports them through `_import_geojson_features`. Entries: `osm_parks` → `nature.GreenSpaces` (`__static__` `type = 'park'`), `osm_water_bodies` → `nature.WaterBodies`, `osm_amenities` → `builtup.Facility` (OSM tags mapped onto the six `Facility.type` values via `osm_classes`; the raw value goes to `subtype`), `osm_trees` → `nature.Tree` (the bulk finalizer `_fill_tree_heights` fills an empty `height_m` from the DSM, `physicalEnv/calculations/tree_heights.py`: highest DSM cell within 2 m outside building footprints − DEM/estimated ground, kept only between 2.5 and 50 m; it scales the 3D tree model of `mainMap/styles/treeStyles.py`; `manage.py fill_tree_heights [--city]` backfills trees imported earlier). All upsert on `osm:<type>/<id>` (`sourceID`/`localId`). The Klimaateffectatlas source (`source: "kea"`, 21 `kea_*` entries built by `_kea_entry`, `KEA_WFS_URL`; routed to `PDOKImporter.fetch_wfs`) imports climate-effect layers. Which layers go where, and why the other 47 are not imported, is in `docs/KEA_WFS_MAPPING.md` (with a mapping graph). Per-buurt layers (`_kea_neighborhood`) upsert one row per neighborhood on `neighborhood_id`. Per-pand layers (`_kea_building`) enrich existing BAG buildings. Generic GeoJSON-path directives added for it (`external_data.py`):
- `_prepare_features`: `@id` (the GeoJSON feature id as a property), `__nodata__`, `__value_maps__`, `__value_scales__`, and `__split__` (one feature per comma-listed value, with `zfill`).
- `_keep_existing`: `__require_existing__` (skip features whose key is not a stored row; prevents deferred-FK failures at COMMIT).
- `_enrich_rows`: `__enrich__` (update-only via `update()`, never creates, never writes the geometry, bumps the cache of every registry model on the table, including the `Energy` proxy).
- `_import_geojson_features(..., notes)` collects skipped-feature lines for the result message.

**Batching (`importer/batching.py`):**
- `SpatialParentIndex` resolves `__spatial_fk__` parents with prepared geometries + a bbox pre-check, probing each feature's `point_on_surface` (not its centroid). Parents are loaded with `.only("pk", "geom", <attrs read off them>)`.
- `BulkWriter` writes models listed in `BULK_IMPORT_MODELS` (LandCoverVector, Street, the nature layers) with `bulk_create`, 500 rows at a time, `ON CONFLICT DO UPDATE` for upserts on a unique field. Rows are grouped by their set of mapped fields so a missing property never blanks a stored value, and a failing batch is retried row by row. `bulk_create` skips `save()` and signals: a model belongs in the registry only if it has no `save()` override (`BulkImportRegistryTests` checks this) and its receivers are replayed by its finalizer. Add a `post_save` receiver to one of these models → add it to the finalizer or remove the model from the registry.
- `_import_geojson_features` and `_generic_import` run inside `deferred_cascades()`.
- `_generic_import` (file upload) maps every concrete field (attributes, FKs by name or id, geometry). `_fit_geometry_type` wraps/unwraps single vs multi geometries to the target field (e.g. a one-part MultiPoint into `ExtractionWater`'s `PointField`). Fields listed in `importer/views.py::FIELD_UNITS` get a unit select beside their column in the mapping form (e.g. `ExtractionWater` pump flows: m³/s, m³/h, m³/day); `_generic_import(..., units=)` converts to the stored unit. Models without an upsert key in `MODEL_OVERRIDES` or a unique field always create rows, so re-uploading duplicates them.

### Raster Pipeline (`core/rasterOperations.py`)

1. PostGIS raster → `ST_AsGDALRaster` → temp GeoTIFF
2. Reproject to `COG_CRS` (EPSG:3857, the map's tile grid, so TiTiler reads tiles without warping; COGs written before 2026-11-12 are EPSG:4326 and still work, readers use the file's CRS) via rasterio
3. Convert to Cloud-Optimized GeoTIFF (COG) via `rio-cogeo`
4. COG stored on disk under `cogs/<app_label>/`, named `<index or ClassName>_<source>_<date>_<id>.tif` (`_cog_filename`; the class name keeps models of one app with the same source, date and id apart)
5. TiTiler serves tiles from the COG path. `core/views.py` adds `v=<COG mtime>` to tile URLs and `tiler.py` then sends `Cache-Control: immutable`, so browsers keep tiles until the COG is rewritten; `/info` is cached per file version (`_titiler_info`, WGS84 bbox from `info.geojson`). Keep `TITILER_BASE_URL` on `127.0.0.1`: TiTiler listens on IPv4 only and Windows resolves `localhost` to `::1` first (~2 s per request)

### Map Frontend (`mainMap/`)

- `map_view` renders `mainMap.html` with Mapbox token
- `available_layers` returns the full layer catalog (vector + WMS + raster) as JSON
- `model_geojson` builds one raw SQL statement per request (`_geojson_sql`): `ST_AsGeoJSON(ST_Transform(..., 4326), 6)`, FK display names via `LEFT JOIN` (not per-row sub-SELECTs; extra columns of the FK target for the popup are listed in `POPUP_RELATED_FIELDS` and arrive as `<fk>__<field>`, e.g. the soil type's name/group/infiltration rates on `SoilArea`), optional `?bbox=minLng,minLat,maxLng,maxLat` (`&&` on the GiST index) and `?zoom=z` (`ST_SimplifyPreserveTopology` to ~1 px below zoom 14; points never simplified). It returns PostgreSQL's JSON text as-is (`HttpResponse`, not `JsonResponse`) with an `X-Cache: HIT|MISS` header.
- GeoJSON responses are cached in the `geojson` cache alias (`CACHES` in settings: local memory, 64 entries, bodies ≤ 8 MB, 2 min) under a per-model version from `core/cache.py` (`layer_version` / `bump_layer_version`). The version only changes on writes made through Django, so edits from QGIS/psql/other scripts show up only when the entry expires — hence the short TTL (`GEOJSON_CACHE_TTL`). Local memory is per process: with several workers, point `CACHES` at Redis so invalidation reaches all of them.
- Map styles live in the `mainMap/styles/` package: `layerStyles.py` (`LAYER_STYLES` per registry key: catalog `color`, Mapbox `layers`, optional `legend`; `FALLBACK_COLORS`; building type colours), `soilStyles.py` and `landCoverStyles.py` (style + legend built per request in `available_layers` from the classes present in the DB), `rasterStyles.py` (raster colormaps/value ranges, used by `core/views.py`). Add a new layer's style to `LAYER_STYLES`; a data-driven one gets its own module there.
- `layer_bounds` returns WGS84 `[[west, south], [east, north]]`, using `ST_EstimatedExtent` only for tables with ≥ `ESTIMATED_EXTENT_MIN_ROWS` (100 000) rows. The estimate is as old as the last `ANALYZE`, so smaller tables get an exact `ST_Extent`.
- `Layers.js`: vector layers with ≥ `VIEWPORT_LOAD_MIN_FEATURES` (5 000, in `Config.js`) features load by viewport and reload on `moveend` (debounced, superseded requests aborted); `zoomToLayer` uses `/bounds/` for them. Administrative layers always load whole — their click handlers and the admin-unit panels need every unit.
- Floating map overlays (toolbar, layers panel, side panel, population dock, legends, WMS scrubber, tour card) share `--overlay-bg`/`--overlay-blur`/`--overlay-shadow` tokens in `mainMap.css` and are draggable by their header via `core/static/js/Draggable.js::makeDraggable(el, handleSelector)` (delegated, so handles added later work; double-click the handle to reset; disabled below 768 px). Wiring is in `Events.js::initializeUI`.
- WMS tiles (`addWmsLayer`, `wmsTileUrlForTime`, the groundwater source) use `WMS_TILE_SIZE` (512, `Config.js`) for both `tileSize` and the `width`/`height` params — keep the two equal. Remote WMS cost is per request (~0.5–3 s each at KNMI), so bigger tiles = fewer requests. Time-dimension WMS sources (the radar) stop at `WMS_TIME_MAX_ZOOM` (8; the radar grid is ~1 km, Mapbox overzooms with nearest resampling), and `Layers.js::prefetchWmsFrames` warms the visible tiles of the other frames one request at a time (nearest frames first, restarted on `moveend`/frame refresh; URLs built like Mapbox's `getTileBBox` + `roundBboxInUrl` so they hit the browser cache). `weather/views.py::wms_tile_proxy` caches tiles in `CACHES["wms_tiles"]` (24 h for `TIME=` frames, 5 min otherwise), sends matching `Cache-Control`, and reports `upstream;dur` / `cache;desc` in `Server-Timing`. Upstream calls go through the module-level `_session` (keep-alive); mock `weather.views._session.get` or `_fetch_with_retry` in tests, and clear `get_cache("wms_tiles")` in `setUp`.
- The map fills the whole `.app-shell` (there is no side column). Upload Data, Retrieve Data from APIs, the *Calculate for this view* tools (one two-column grid, `.actions-menu-grid`) and the year selector live in the **Actions menu** (`#actions-menu`), a drop-up opened from the bottom bar's `#actions-menu-btn`, which shows the active year while collapsed. The menu is a sibling of `.bottom-bar`, not a child: the bar is a stacking context at `z-index: 9`, below the side panel and population dock, so `mainMap.js::positionActionsMenu()` anchors it to the button instead. It closes on an outside click or Escape.
- Mapbox's own extruded buildings (the `3d-buildings` layer from `Map_init.js::add3DBuildings`) are hidden while any `builtup` layer is shown (loaded and checked), and only then: `Layers.js::sync3DBuildings()` runs after every vector layer load, every `toggleLayerVisibility()` and every `add3DBuildings()` (a basemap switch re-creates the layer). Likewise the basemap's own 3D trees are hidden while the *Green and Blue Space* tool (`data-tool="green"`, `TOOLS_WITHOUT_BASEMAP_TREES`) is active, so only the stored `nature.Tree` models show: `Map_init.js::syncBasemapTrees()` sets `show3dTrees` on Mapbox Standard imports that have it and hides classic `model` layers whose id/source layer contains "tree"; it runs on every tool click and `style.load`.
- All legends live in `#legend-stack`; `Layers.js::repositionDynamicLegends()` moves the stack so it clears the side panel and the population dock (re-run by observers in `Events.js`), unless the user has dragged it. Append new legends to `#legend-stack`, not `.map-wrapper`.
- Templates live in `Templates/` (capital T, configured in settings)
- **Landing page** (`/welcome/`, `mainMap.views.landing_view`, `mainMap/templates/mainMap/landing.html`, `core/static/css/landing.css`, `core/static/js/landing/`): a scroll-driven Three.js city. `stages.js` is pure: every camera and layer value derives from `u`, the scroll position in stage coordinates, so there is no clock or stored state to keep in step (only the hero's idle rotation uses time, and it decays by `u = 0.62`). `plan.js` is the seeded layout (no Three.js; also feeds `tools/landing_fallback_svg.mjs`, which writes the no-WebGL sketch: rerun it when the plan changes), `city.js` builds one group per system, `scene.js` draws on demand and lowers quality when frames are slow, `main.js` wires scroll, rail and fallbacks. `graph.js` holds the drawn part of the DAG; a test checks its edges against `core/DAG.dot`, and its `computed` flags plus the "just over half" sentence in the template must follow the coverage count in `docs/DAG_COVERAGE.md`. The city is an illustration; a real extract can replace `buildPlan()`'s output. Three.js and GSAP are vendored in `core/static/vendor/` (see its README).
- **Map settings** (`#settings-card`, staff only, header's *Map settings* button; `core/static/js/MapSettings.js`, `mainMap/settings_views.py`, partials `map_settings.html`/`settings_editable_row.html`/`settings_style_form.html`): tab *Editable layers* (above) and tab *Styles*. Styles are `mainMap.LayerStyleOverride` rows on top of the code defaults in `mainMap/styles/`, storing only what differs (Reset deletes the row). `styles/overrides.py::vector_style(key)` resolves a vector layer's catalog colour, style layers and legend (default + override; `available_layers` uses it with one `vector_overrides()` query per request): scalar paint properties per style-layer index, and the colours of a colour `match` expression by category (legend entries carry `value`; `'__other__'` = the match fallback). Raster overrides are keyed by `rasterStyles.raster_style_key()` (the `INDEX_STYLES` key, else the `MODEL_STYLES` key) and applied in `resolve_raster_style` (colormap, rescale; `null` = from the data). Saves answer with `HX-Trigger` `style-changed` / `editable-changed`; `MapSettings.js` re-adds the layer (`addLayer(config, {fit: false})`) or updates the catalog entry's `editable` flag, and paint inputs preview live with `setPaintProperty`. Overrides are global (all visitors) and read per request, so several workers stay consistent.
- **LST tool** (`#lst-card`, `core/static/js/LstTool.js`, opened from the Actions menu's *Calculate for this view* section): lists the Landsat scenes over the current view and computes LST for it (`urban_heat/lst/views.py` → `pipeline.calculate_lst(bbox_wgs84=...)`). The grid is the view clipped to the NDVI layers' coverage; overlapping NDVI layers are merged newest first; areas over ~48 MB of Earth Engine download (~40×40 km at 30 m) are refused. A recalculation with the same scene replaces the LST rows whose extent it covers (with their COG files); the frontend drops them with `Layers.js::removeLayer()` and adds the new row's catalog entry (`mainMap.views.raster_layer_entry`). Synchronous request, ~10–60 s. Calculating is staff only; listing scenes is open.
- **Degree of Urbanisation tool** (`#degurba-card`, `core/static/js/DegurbaTool.js`, Actions menu → *Calculate for this view* → Degree of Urbanisation; `lst-*` classes, closes the LST/SVF/thermal cards and vice versa): shows the stored grid (`/builtup/degurba/info/` → `builtup/calculations/urbanisation.py::status`), a 100 m / 1 km switch that shows the `builtup.UrbanisationCellLocal` / `UrbanisationCellOriginal` layer, the cities' class and rate; *Build / Recalculate* (staff) POSTs `builtup/views_degurba.py::degurba_calculate` → `urbanisation.rebuild()`. After that the receivers keep it current; the card re-reads after `feature-saved` / `backup-restored`. GHSL GHS-SMOD / GHS-POP are importer catalog entries (`gee_ghsl_smod`, `gee_ghsl_pop`, index `GHSL_SMOD` painted with the same class colours through `rasterStyles.DISCRETE_COLORMAPS` → TiTiler `colormap=`), reference only.
- **Neighbourhood generator** (`#generator-card`, `core/static/js/GeneratorTool.js`, Actions menu → *Calculate for this view* → Neighbourhood generator; `lst-*` classes, closes the other tool cards and vice versa): draw an outline with its own Mapbox Draw instance (not `Editing.js`'s) or pick a `housing.HousingProject`, choose a style (`generative.STYLES`: plain, Vinex, garden city, urban block, modernist), street pattern (grid/curved/radial), variation 0–100 % (default 50 % for every style) + seed (*Shuffle*; stored, so layouts repeat), typology, dwellings per building (auto: houses up to 2 floors, flats above; single; stacked) and sizes (empty = the style default, shown as placeholder). Each preview also returns the **site check** (`builtup/calculations/site.py::site_constraints`: Natura 2000 / NNN `ProtectedArea` cut out of the buildable area and hatched red on the map, other protected areas, non-residential zoning and existing BAG buildings as amber warnings; nothing buildable blocks Store, and `generator_commit` re-checks server side and stores the summary in `generator_params["site_check"]`) and indicative **Bbl checks** (`builtup/calculations/regulations.py`: minimum dwelling size 18 m² living space / 55 % / NEN 2580 → ≈ 41 m² gross, refused in `resolve_params`; 5 m fire-spread gaps; 45° daylight between facing slabs/towers; the omgevingsplan is not checked). Every change POSTs `builtup/views_generator.py::generator_preview` → `site_constraints` → `generative.generate(buildable=…)` → `regulations.check` and draws blocks, plots, streets, extruded buildings and the excluded/warning areas in the `generator-preview` source with Spacematrix metrics (FSI, GSI, dwellings/ha and per building vs the target). *Store* (staff) saves the project as completed with `generator_params` (resolved parameters + `GENERATOR_VERSION`); `housing/signals.py` then materialises it (see the edge table) and the card fires `feature-saved`. *Set back to planned* removes the rows. Both are journalled, so the backup bar's Restore undoes them. Outlines above 4 km² are refused.
- **SVF tool** (`#svf-card`, `core/static/js/SvfTool.js`, Actions menu → *Calculate for this view* → Sky View Factor; reuses the LST card's `lst-*` classes and closes it on open, and vice versa): on open and after each map move it asks `/physicalEnv/svf/info/` which DSM covers the view and how big the grid is, and labels the button *Recalculate* when a stored SVF of that DSM already covers the view. Radius (25–200 m) and cell (DSM's own, 1/2/5 m) selects. Calculate POSTs `physicalEnv/views.py::svf_calculate` → `svf.calculate_svf(bbox_wgs84=...)`; the frontend removes the replaced layers and adds the new one. Staff only to calculate.
- **Thermal Comfort tool** (`#solweig-card`, `core/static/js/SolweigTool.js`, Actions menu → *Calculate for this view* → Thermal Comfort (SOLWEIG); reuses the `lst-*` classes, and the LST/SVF/thermal cards close each other): date + hour (local time at the view centre), cell size, weather source (Manual / Nearest KNMI station / ERA5, *Fetch* fills the editable inputs). `info` shows the DSM, grid, sun position and device; *Calculate* POSTs a background run and polls `/urban_heat/solweig/runs/<id>/`, then adds the UTCI layer and lists Tmrt/PET. Staff only to calculate. The same file owns the **stale mark**: after `feature-saved`, `backup-restored` and map moves it asks `/urban_heat/solweig/stale/?bbox=` and shows `.stale-dot`s on `#actions-menu-btn` and the SVF / Thermal Comfort rows.
- **Homes without water supply** (`core/static/js/UnservedWater.js`): while the Water Supply tool (`data-tool="water"`) is active, every home with residents that no pipe reaches (no `PipeNetwork` within its city's service buffer, `users.service_buffer_m`; the complement of `UsersLocation.populationServed`) shows a floating water drop with a prohibited sign (canvas-drawn icon, clustered source, `icon-translate` bobbing off with `prefers-reduced-motion`, legend in `#legend-stack`). Data: `/watersupply/unserved/?bbox=` → `watersupply/calculations/users.py::unserved_properties` (one SQL, `UNSERVED_MAX_FEATURES`); reloads on `moveend` (zoom ≥ 10), `feature-saved`, `backup-restored`.
- **Weather pill** (`#weather-pill`, top centre, `core/static/js/WeatherPill.js`): current weather at the map centre from `/weather/live/` (`weather/views.py::live_weather` → `weather/live.py::current_weather`, Open-Meteo `current=`, no key; cached in the default cache per `GRID_DEG` 0.02° cell for 10 min; `LIVE_WEATHER=false` turns it off, `OPEN_METEO_URL` overrides the endpoint; `settings_test` sets it off, so tests mock `requests.get`). Reloads after `moveend` (only when the centre changes cell) and every 10 min. A click opens the Urban Heat panel (`[data-tool="temperature"]`). The panel's weather sliders (`urban_heat/partials/whatif_controls.html`, shared with the standalone dashboard; `ta_c`, `rh_pct`, `wind_ms`, `kdown_wm2`) start at the live weather of the unit (`views._baseline_weather`: Open-Meteo at the unit's point on surface, else the latest station reading; `get_latest_meteorology` reads only `Meteorology.period = 'hour'` rows, never the KNMI daily 24 h means, which would understate radiation and heat stress) and are a what-if: `_build_indicators(data, weather_override)` → `urban_heat/calculations/chain.py::weather_heat_stress` (Steadman apparent temperature shade/sun, BoM approximate WBGT), never stored. `heat.js` sends only the sliders the user moved (a range input snaps to its step), and after every swap publishes `#heat-weather-state` as a `crosstwin:heat-weather` window event, which the pill shows with a *What-if* badge until Reset, the panel closes or another panel replaces it. The map loader sits below the pill (`top: 52px`). Precipitation: the pill sits in `#weather-pill-wrap`, and the live `weather_code`/`precip_mm` switch on Mapbox's `map.setRain`/`setSnow` particle effect (experimental, screen-wide, fades in between zoom 11 and 13; re-applied on every `style.load`, off with `prefers-reduced-motion`; never from the what-if). Mapbox has no rain radar outside Japan, so while it rains a sibling `#weather-pill-radar` button toggles the KNMI radar WMS layer (the time-dimension WMS whose key contains `radar`) through `toggleLayerVisibility`.
- **Scenarios panel** (bottom bar's `#btn-scenarios` → `Panels.js::showScenarios` → `/weather/climate/panel/?climate=`, `weather/views.py::climate_panel`, partial `weather/partials/climate_panel.html`): the KNMI'23 climate scenarios (`weather/calculations/climate.py`: Table 1 of KNMI Publication 23-03, national averages vs 1991-2020, per season; the Klimaateffectatlas presets current / 2050 high / 2100 high, "high" = Hd, plus all of Ld/Ln/Hd/Hn × 2050/2100; heat mode `climate_heat` = `average` (Table 1 daily max/min, understates heat waves) or `warmest` = heat-wave day: the warmest-day change at the nearest of KNMI's five key-figure stations, `climate.STATION_EXTREMES`, from klimaatscenarios-data.knmi.nl, nearest to the unit's point on surface, day and night, with the summer humidity/wind/radiation changes; the panel lists the stations' heat key figures). The chosen key goes to `window.CLIMATE_SCENARIO` (badge on the button), the heat mode to `window.CLIMATE_HEAT`, and `mainMap.js::climateParam()` adds `climate=&climate_heat=` to the heat and water panel URLs. Heat: `urban_heat/views.py::_climate_weather` moves the live/station weather by the season's change (`apply_to_weather`: Tx by day, Tn by night, RH, wind, radiation scaled by the seasonal mean), the sliders start (and Reset returns) there, the pill shows the scenario as its badge. Water: the Rain Event default × the summer 1-day 10-year rain change (`design_rain_mm`), recharge with seasonal daily rain (`apply_to_daily_rain`, needs `daily_months` from `yearly_water_balance`) and yearly Makkink ET changes. A what-if: nothing stored, SOLWEIG/LST keep observed weather.
- **Console feed under the loader** (`core/console.py`, `core/static/js/ConsoleFeed.js`, `GET /api/console/?after=<seq>`, DEBUG or staff only): `CoreConfig.ready()` tees `sys.stdout` and `LOGGING` sends the project loggers (INFO, listed in `settings._APP_LOGGERS`) and other libraries' WARNINGs to `console.FeedHandler`, into a 500-line in-memory buffer (per process; TiTiler not captured). While any `fetch()`/HTMX request of the map page is pending, `ConsoleFeed.js` polls the feed and shows the newest 6 lines under `#map-loader` (inside `#map-loader-wrap`), fading 4 s after the work ends. Report progress of long work with `print()` or a project logger and it appears there; the polling is kept out of the runserver access log (`SkipFeedRequests`) and the query-stats log.
- `core/static/js/mainMap.js` holds `mainMap.html`'s page-level wiring (map init, the Actions menu, guided tour, the admin-unit-driven panel registry). It depends on `Config.js`/`map_init.js` and on `window.MAPBOX_ACCESS_TOKEN` being set inline by `mainMap.html` before it loads. As with the indicator dashboards, keep new map-page behavior in this file rather than adding inline `<script>` blocks to `mainMap.html`.

### Map Editing (`core/editing.py`, `core/static/js/Editing.js`)

Staff users (`is_staff`; **Log in** at the top right of every page, `django.contrib.auth.urls` under `/accounts/`, template `Templates/registration/login.html`) can create, reshape, edit and delete objects of the layers switched on in the map's **Map settings** panel (stored as `mainMap.EditableLayer`, one row per editable layer; migration 0002 seeded the five built-up layers). The form rules per layer (`exclude`/`optional`) stay in `core/editable_layers.toml` (`core.editing.FIELD_RULES`, read at startup), since they follow from each model's `save()`. Design and decisions: `docs/MAP_EDITING.md`; equations: `docs/functions_and_equations.tex`.
- The form is a `modelform_factory` ModelForm swapped into `#panel-body`; the geometry travels as WGS84 GeoJSON in a hidden field and the GIS form field checks its type and reprojects it. Saving goes through `obj.save()`, so derived fields, signals and cache invalidation apply. User-created objects of a model with a non-auto pk (`Building`, BAG ids) get negative ids (`_next_negative_pk`).
- **To make a layer editable:** switch it on in Map settings → Editable layers. `core.editing.enable_blocker()` refuses layers whose model overrides `save()` and has no table in `core/editable_layers.toml`, and `watersupply` layers (`RAW_SKIPPING_APPS`, receivers skip raw saves so Restore would leave cascades stale). For those, first add a `["app_label.ClassName"]` table with `exclude` (fields its `save()` derives) and `optional` (fields `save()` fills in) and restart the server. `load_editable_layers()` rejects a malformed file at startup; `mainMap/test_editing.py` checks every key is a vector layer and every field exists. If its app has receivers that skip `raw=True` saves (e.g. `watersupply/signals.py`), backup restore must trigger those cascades itself.
- **Backup / restore:** one restore point at a time (`EditBackup`). After it is created, `journal()` stores each object's original row (first pre-image wins) before the editor changes it. `restore_backup()` reverts only those rows in one transaction (raw saves, then deletes of objects created since), rolling everything back if a reference blocks it. Changes made outside the editor (importer, admin, psql) are not journalled. A side effect another app makes for an edit can be journalled through a custom signal that `mainMap/signals.py` subscribes to: the urban-fabric buffer of a new building (`physicalEnv.calculations.landcover.landcover_rewriting`/`landcover_created`, layer key `physicalEnv.LandCoverVector`) is undone by Restore this way.
- `feature_form`/`feature_delete` save and delete inside `core.editing.editor_change()`; receivers that must react to a user's edit but not to imports check `is_editor_change()` (physicalEnv's `Buildings -> DSM` patch). The backup bar counts only journalled rows of map layers (`VECTOR_REGISTRY`), not bookkeeping rows such as `UrbanFabricCut` or `DSMBuildingPatch`.
- FK constraints are `DEFERRABLE INITIALLY DEFERRED`; `_check_constraints()` forces the check inside the atomic block so delete/restore conflicts surface as messages instead of failing at commit.
- While editing (`isEditing()`), feature popups, admin-unit clicks and `refreshActivePanel()` are suspended; a `MutationObserver` on `#panel-body` attaches/detaches Mapbox GL Draw. The `feature-saved` / `backup-restored` HTMX events reload layers via `Layers.js::reloadLayer()`.

### API Routes

| Path | Purpose |
|---|---|
| `/` | Main map view |
| `/welcome/` | Landing page (static, no queries) |
| `/api/layers/` | Layer catalog JSON |
| `/api/layers/<app>/<model>/geojson/` | GeoJSON for vector model (`?bbox=` WGS84, `?zoom=`; cached) |
| `/api/layers/<app>/<model>/bounds/` | Bounding box extent in WGS84 |
| `/api/layers/<app>/<model>/features/new/`, `.../features/<pk>/`, `.../features/<pk>/delete/` | Map editing form / delete (staff, layers switched on in Map settings only) |
| `/api/settings/`, `/api/settings/editable/`, `/api/settings/style/` | Map settings panel: editable layers on/off, style form (`?target=vector:<key>|raster:<style key>`; POST saves, `action=reset` deletes) (staff) |
| `/accounts/login/`, `/accounts/logout/` | Header login / logout (POST) |
| `/api/editing/backup/` (+ `restore/`, `discard/`) | What-if backup bar: status, create, restore, discard (staff) |
| `/api/raster/<app>/<model>/tiles/` | TiTiler tile URL for raster |
| `/api/raster/<app>/<model>/info/` | Raster metadata |
| `/importer/` | File upload import |
| `/watersupply/` | Water supply indicators dashboard |
| `/urban_heat/` | Urban heat views |
| `/urban_heat/lst/scenes/`, `/urban_heat/lst/calculate/` | Map LST tool: Landsat scenes over `?bbox=` (ranked by clear share of the view); compute + store LST for the view (POST, staff) |
| `/urban_heat/solweig/info/`, `.../met/`, `.../calculate/`, `.../runs/<id>/`, `.../stale/` | Map Thermal Comfort tool: inputs + sun for `?bbox=&datetime=`; KNMI/ERA5 met prefill; start a background SOLWEIG run (POST, staff); run status + layers; results made stale by building edits |
| `/physicalEnv/dsm/edited/status/` | Whether map edits are still being written into the edited DSM COG (`{"busy": bool}`) |
| `/physicalEnv/svf/info/`, `/physicalEnv/svf/calculate/` | Map SVF tool: DSM, grid and existing SVF for `?bbox=`; compute + store SVF for the view (POST, staff) |
| `/weather/live/` | Map weather pill: current weather at `?lat=&lng=` (Open-Meteo, cached per ~2 km cell) |
| `/watersupply/unserved/` | Homes no pipe reaches, as WGS84 GeoJSON points (`?bbox=`) |
| `/housing/` | Housing indicators dashboard |
| `/builtup/` | Built-up fabric indicators dashboard |
| `/builtup/degurba/info/`, `/builtup/degurba/calculate/` | Map Degree of Urbanisation card: stored grid status; rebuild for the current population year (POST, staff) |
| `/builtup/generator/projects/`, `.../preview/`, `.../commit/`, `.../remove/` | Map Neighbourhood generator: housing projects; layout of an outline as GeoJSON + metrics (POST, what-if, writes nothing); store on a project as completed / set back to planned (POST, staff) |

### App Layout: `calculations/` and `tests/` folders

Every app keeps its computation code and its tests in two packages, so a value can be traced to one place and debugged there:

- **`<app>/calculations/`** — one module per topic, no views, no receivers:
  - `indicators.py` — the dashboard's query functions (formerly `<app>/calculations.py`);
  - `chain.py` — the pure equations shared by `save()` and `_build_indicators` (see the DAG contract);
  - topic modules: `administrative/calculations/population.py`; `physicalEnv/calculations/{albedo,building_heights,dsm_edited,dsm_patches,landcover,soil,svf,tree_heights}.py`; `weather/calculations/water_balance.py`; `builtup/calculations/{canyon,degurba,generative,materialise,regulations,site,urbanisation}.py`.
  - Stay outside: `models.py`, `signals.py` (receivers only trigger saves), `views*.py`, `admin.py`, data fetchers (`weather/knmi.py`, `weather/live.py`, the importer) and lookups (`physicalEnv/hilucs.py`, `administrative/admin_units.py`). The self-contained pipelines `urban_heat/lst/` and `urban_heat/solweig/` keep their own packages.
  - `__init__.py` stays empty (no re-exports): import the module by its full path (`from watersupply.calculations import chain`, `from watersupply.calculations.indicators import calculate_nrw`) and patch it there in tests (`mock.patch("physicalEnv.calculations.svf.load_dsm")`).
- **`<app>/tests/`** — `test_<topic>.py` files (the former `tests.py` is `test_<app>.py`) plus shared helpers such as `watersupply/tests/factories.py`. Tests use absolute imports (`from housing.models import ...`). Run one module with `manage.py test housing.tests.test_housing ...`.

New calculation code goes in `calculations/`, new tests in `tests/`; never back into the app root.

### Reproducibility

CrossTwin results are cited in research, so **every stored or displayed number must be reproducible later** from the code, the data sources and the recorded parameters. When adding or changing a calculation:

- **Deterministic code.** Equations are pure functions in `calculations/` (no hidden state, clock or random draws; seed anything stochastic and store the seed). The same inputs must give the same output on any machine.
- **List the source.** A new external source or cited rule goes into `importer/external_catalog.py` or `core/data_sources.py`; rerun `tools/data_sources.py` so `docs/DATA_SOURCES.md` lists it.
- **Record the inputs with the result.** Store the source and version of the input data (dataset/catalog key, scene or file id, station, year, CBS table), the parameters used (radius, cell size, thresholds, scenario) and the method in the result row (`source`, `measurement_method` or a dedicated field), as LST (`measurement_method` = water-vapour source), SVF (`source` = `DSM <id>: ...`) and SOLWEIG runs (`ThermalComfortRun`) already do. A result without its inputs cannot be recomputed.
- **Pin the environment.** Dependencies come from the committed `uv.lock` (`uv sync`, never unpinned installs); bump versions deliberately and note them in the commit. External data that changes over time (Earth Engine collections, KNMI, CBS, PDOK, OSM) must be identified by date/version in the stored row, and example data is packaged with `tools/example_db.py dump`.
- **Name constants and cite them.** Thresholds and coefficients are named module constants with their reference (paper, table, standard), not literals inside an expression; changes to them are argued in the docstring or `docs/`.
- **Document the equation.** Each equation has its entry in `docs/functions_and_equations.tex` (equation, `<app>/calculations/<module>.py::function`, status) and, for DAG edges, the coverage list in `docs/DAG_COVERAGE.md`.
- **Test it.** A test in `<app>/tests/` pins the result for a known input (and the dashboard/stored parity for `chain.py`), so a later change that alters a number fails loudly instead of silently.

### Testing

Tests use `PostGISTestRunner` (`DigitalTwin/test_runner.py`) which creates the test DB, installs PostGIS extensions, and patches Django's `prepare_database` to avoid superuser requirement. Always use `--settings=DigitalTwin.settings_test --keepdb` (see Common Commands). Tests that hit the GeoJSON endpoint should clear the `geojson` cache in `setUp` (`core.cache.get_cache('geojson').clear()`): `TestCase` rolls back the DB but not the cache. Pin query counts with `assertNumQueries` on hot endpoints (`ModelGeoJsonTests` keeps `model_geojson` at one query).

## Key Patterns to Follow

- **All app content is in English**: templates, JS strings, labels, legends, help text (`core/indicator_help.py`), messages and docs. Translate Dutch source terms (e.g. KNMI'23 "hoog/laag, droog/nat" → "high/low, dry/wet"); Dutch stays only as data values or official names (dataset titles, codes, place names, CBS table ids)
- All spatial models use `srid=settings.COORDINATE_SYSTEM` (EPSG:28992), not hardcoded SRIDs
- Models with computed fields implement logic in `save()` — check existing patterns before adding new ones
- A DAG edge with a stored target = the target's `save()` (equation, via `<app>/calculations/chain.py` when the dashboard needs it too) + a receiver on the source in `<app>/signals.py` that `_resave()`s the target; what-ifs call the same `chain.py` functions and never write — see [Implementing a DAG Edge](#implementing-a-dag-edge-signalreceiver-contract)
- Use `models.DO_NOTHING` for FK on_delete in spatial/reference models (project convention)
- Population cascading uses `update()` not `save()` to prevent signal recursion
- Raster models need a `cog_path` field to participate in the COG auto-export pipeline
- The GeoJSON API transforms to EPSG:4326 at query time via `ST_Transform`
- No top-level imports of heavy libraries (numpy, scipy, pandas, geopandas, rasterio, rio-cogeo, rio-tiler, openeo, ee) in modules loaded at startup or by the URLconf — models, signals, `apps.py`, views, `mainMap/styles/rasterStyles.py`, `importer/utils.py`. Import them inside the function that uses them. At module level they cost 0.4–1.6 s each at every process start and on the first request after each `runserver` reload. When a test mocks such a function, patch it where it's defined (e.g. `core.rasterOperations.export_raster_to_cog`), not where it's used.
- Performance work is tracked in `docs/PERFORMANCE.md`: §0–§3 are implemented (measurement, GeoJSON endpoint, land-cover signal, importer batching); §4–§12 are still proposals
- Frontend CSS uses Tailwind with crispy-tailwind for forms
- Frontend JS lives in `core/static/js/` (page-level files like `mainMap.js`, domain files under `indicators/`), not in inline `<script>` blocks in templates — see [Indicator Pattern](#indicator-pattern-watersupply-housing-urban_heat-builtup) and [Map Frontend](#map-frontend-mainmap)

## TODOs

Collected from inline `#TODO` comments across the codebase:


### physicalEnv
- Add Vegetation Coverage and Builtup Coverage as additional fields on `LandCoverVector` (`physicalEnv/models.py`)

### builtup
- Define connectivity index and calculation method for `Building.connectivity` (`builtup/models.py`)
- Define green visibility index and calculation method for `Property.greenVisibility` (`builtup/models.py`)

### watersupply
- `UsersLocation.neighborhood` FK — decide whether this should be City-level or per-point (`watersupply/models.py`)
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

