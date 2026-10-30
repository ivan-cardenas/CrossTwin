
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

# Database migrations
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

# Slowest SQL statements from pg_stat_statements (--order mean|calls|rows, --reset)
uv run python manage.py db_stats

# Profile GET requests (run 1 = cold process, run 2 = warm); --save x.prof for snakeviz
uv run python tools/profile_requests.py "/api/admin-unit/?lng=6.895&lat=52.219" --runs 2

# Architecture diagrams: check the palette (contrast + colour-blind separation), build SVGs, export PNG/PDF
uv run python tools/palette_check.py && uv run python tools/arch_diagrams.py && uv run python tools/arch_export.py

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

The project follows the **DPSIR framework** (Driver → Pressure → State → Impact → Response) to model causal relationships between urban systems. The full causal graph is defined in `core/DAG.dot` (Graphviz format). Each domain app's `calculations.py` documents which DAG edges its functions implement via comments like `# DAG edges: Central_Bank -> Mortgage`.

When adding new calculations, trace the relevant DAG edges and document them in the function docstring to maintain traceability between the causal model and code. Edges whose target is stored must follow the signal/receiver contract in [Implementing a DAG Edge](#implementing-a-dag-edge-signalreceiver-contract).

#### DAG Edge Coverage Gaps

`core/DAG.dot` has 105 distinct edges (106 edge lines: `Total_Water_Prod -> OPEX` is listed twice; the invisible legend chain `L_D -> … -> L_R` is not counted). 45 (43 %; + `Total_Population -> Housing_Demand`, `Household_Size -> Housing_Demand`, `Household_Size -> Property`, added with the housing household-size chain) are backed by real derivation logic (a `save()` method or a `calculations.py` function that actually reads the source field, not just a docstring claiming the edge), 6 are partial (`Infiltration -> Available_FW`, `Total_Water_Prod -> Energy_Consumption`, `Green_Area -> Vegetation_Coverage`, `Buildings/Streets -> Canyon_Aspect`, `New_Units -> Housing_Supply`) and 54 are gaps (recount 2026-10-27: + `Buildings -> DSM` and the 7 SOLWEIG edges). Borderline counted as implemented: `CityArea -> Coverage_WS_Area` (city geometry only scopes pipes/households) and `Total_Extraction -> Energy_Consumption/CO2_Emission` (pump energy x hours, not extracted volume). The rest are either flat stored fields with no computation, or `calculations.py` functions whose docstring claims a DAG edge the code doesn't actually implement (e.g. `calculate_drought_area` for `Total_Extraction -> Area_Drought` only sums stored areas). Verified gaps, by app:

**administrative** — `Population_Growth -> Total_Population` is implemented at city level: CBS 85173NED forecasts are imported into `PopulationProjection` (per City, year and variant `prognose|low|high`; catalog entry `CBS_PopulationForecast`), and `administrative/population.py::get_population()` derives any unit's projected population (District/Neighborhood = city projection x their share of the city, Province = sum of its cities, plus an optional `growth_adjust_pct` what-if). The water and housing dashboards use it via `?pop_scenario=&pop_growth=`. The what-if controls and a Photoshop-Curves-style forecast graph (smooth curve, square handles, shaded 67% interval band; geometry in `mainMap/charts.py`) live in the map's bottom **Population dock** (Population pill, `/api/population/panel/`), independent of the side panel so an indicator panel can stay open beside it. Still open: `City.popGrowthRate`/`urbanizationRate` remain flat fields never used for projection, housing supply/demand and urban heat do not depend on the projected population (housing shows it but its demand still comes from stored `HousingSupplyDemand` rows), and no `Urbanization` model exists, so `Urbanization -> CityArea/Buildings/Streets/LandCover` has nowhere to live.

**physicalEnv** — `RS_Imagery -> LandCover` — raster models are plain imports with no ingestion/derivation code (`RS_Imagery/LandCover -> LST` is implemented, see urban_heat). `LandCover/Soil_Type -> Infiltration` is implemented as a dashboard indicator (SCS Curve Number, `physicalEnv/soil.py`, see below), and `Infiltration -> Available_FW` is partial: `AvailableFreshWater.save()` derives `yield_Mm3_year` = `infiltrationDepth_cm` (cm/yr) / 100 x polygon area / 1e6 (`watersupply/chain.py::recharge_Mm3_yr`; a supplied yield is kept only without a depth), but the depth itself and `infiltrationRate_cm_h` (a capacity during rain, unused) are still flat inputs (see existing TODO). `New_Units -> LandCover` is implemented. Stored, for buildings drawn in the map editor (negative id): `physicalEnv.signals.building_created` → `physicalEnv/landcover.py::urbanize_around` cuts a 10 m buffer (clipped to the city) out of the city's latest-year `LandCoverVector` polygons and inserts it as one "urban fabric" polygon tagged `source_building`; each cut piece is kept as an `UrbanFabricCut` (with the source polygon's id and attributes; `registry_hidden = True` keeps it out of the model registries). Moving (footprint changed; `pre_save` stashes the stored one) or deleting (`building_deleted`, skipped while `core.editing.is_restoring()`) the building runs `release_ring`: pieces go back to their polygons (only what the ring still holds; swallowed polygons are recreated with their id), cuts that later rings took from this ring are re-targeted to its targets, then the ring and its cuts are deleted. BAG imports never trigger it; rings from before `source_building` existed can't be released. `Buildings -> DSM` is implemented as an overlay (`physicalEnv/dsm_patches.py`): a building the map editor creates, reshapes, re-heights or deletes (`core.editing.is_editor_change()`; imports never) gets one `DSMBuildingPatch` (original footprint, current footprint, height = `height_m`, else 3 m per floor), applied by `svf.load_dsm` to every DSM window read for analysis (original footprint → ground, current footprint → median ground + height; ground = DEM on the same grid, else a 40 m minimum filter of the DSM). The DSM COG is never rewritten. Patches are journalled (`dsm_patch_rewriting`/`dsm_patch_created`, `mainMap/signals.py`) so Restore reverts them; every patch change, Restore included, appends a `DSMEdit` (area + time), and SVF rasters / SOLWEIG runs older than an overlapping edit are reported as stale (`urban_heat/solweig/pipeline.py::stale_results`). Dashboard, for the housing pipeline: `housing/calculations.py::calculate_pipeline_land_take` intersects pipeline project footprints with the latest land cover (greenfield vs infill ha) and writes nothing.

**urban_heat** — `RS_Imagery -> LST` and `LandCover -> LST` are implemented on demand by `urban_heat/lst/` (the map's LST tool, or `manage.py calculate_lst`): a Python port of Ermida et al.'s Statistical Mono-Window Earth Engine modules (`users/sofiaermida/landsat_smw_lst`) where Earth Engine only serves the inputs (Landsat 8/9 B10 TOA brightness temperature + L2 `QA_PIXEL`, ASTER GED, NCEP TPW) on a 30 m EPSG:28992 grid snapped to CrossTwin's NDVI layer (`LandCoverRaster`, `index=NDVI`), the equations run in numpy (`smw.py`), and the NDVI layer drives FVC → emissivity. Output is a `LandSurfaceTemperature` raster in °C. No receiver (a post_save must not start an Earth Engine download). Water vapour (`gee.TPW_SOURCES`, first source with a field on the scene's day): NCEP (`NCEP_RE/surface_wv`, what the original uses) stopped updating on 2026-03-18, so later scenes use ERA5 hourly (`total_column_water_vapour`, ~5 days behind real time; `smw.interpolate_tpw(step_ms=...)` takes each source's field spacing). The source is stored in `measurement_method`. A scene with no source for its day fails before the download with a clear message. `DSM -> SVF` is implemented on demand by `physicalEnv/svf.py::calculate_svf(bbox=|bbox_wgs84=, radius_m=...)` (the map's SVF tool or a shell call): RVT horizon search in numpy, heights divided by the cell size; it reads only the view plus a halo of one search radius (a window of `dsm_raster`, or of the DSM's COG warped back to the storage CRS at the COG's own cell size), crops the halo off and writes one `urban_heat.SkyViewFactor` row over the view (`source` = `DSM <id>: ...`). Windows above `MAX_CELLS` (16 M) are refused; a recalculation replaces that DSM's SVF rows inside the new view. No receiver. `DSM -> SVF -> Tmrt/PET`, `Meteorology -> Tmrt/PET/UTCI` and `Tmrt -> PET/UTCI` are implemented on demand by `urban_heat/solweig/` (the map's Thermal Comfort tool; `docs/THERMAL_COMFORT.md`): the view + `HALO_M` (50 m) read from the DSM with the editor's building patches, split into SOLWEIG's `Building_DSM`/`DEM`/`Trees`/`Landcover` (`inputs.py`), one hour of meteorology (manual, nearest KNMI station, ERA5; `met.py`) written as a two-row UMEP met file, `solweig-gpu` (PyTorch, CUDA when available) for walls, SVF (cached per input hash in `cogs/solweig_work/`), Tmrt and UTCI, then PET with the `pet-adjusted` package on the whole window before the halo is cropped (`pipeline.urban_pet` → `urban_pet_from_rasters`: Koopmans et al. 2020 urban heat island on the air temperature from the day's Tmax/Tmin/Kdown/wind — `Met` day fields, filled by the KNMI/ERA5 fetch — and 1.2 m wind from building/tree frontal areas; without day values or outside April–September no UHI; building cells nodata). It runs as a `ThermalComfortRun` in a background thread and stores one `MeanRadiantTemperature`, `UTCI` and `PET` row. No receiver. `Buildings -> DSM` is stored: see physicalEnv. Still open: `LST -> PET`, `Canyon_Aspect -> DSM`, `Vegetation_Coverage -> DSM`, `Streets -> Canyon_Aspect`; meteorology is uniform over the view for Tmrt/UTCI (PET has the UHI and 1.2 m wind, but its source areas are truncated at the 50 m halo); `calculate_urban_morphology()`/`get_thermal_indices()` only compute *statistics over* existing rasters. `PET -> NBS` — `calculate_nbs_coverage()` counts NBS geometries but never reads PET values.

**builtup / housing** — Implemented (housing demand follows population): `housing.HouseholdSize` (per City and year) holds CBS households (86291NED, catalog `CBS_Households`) and the 1 January population (03759NED, `CBS_PopulationJan`); each import fills its own column and `save()` derives `average_size` = population / households (whole-gemeente figures, so it is right even when only some neighborhoods are imported). `HousingSupplyDemand.demand_units` is now derived in `save()` (`housing/chain.py::demand_units`: baseline population / persons per home; supply stays the CBS stock, the permits column `VergundeNieuwbouw_2` is no longer imported as demand). The baseline population (`housing/chain.py::baseline_population`) prefers the CBS population stored with the year's `HouseholdSize`, then the CBS median forecast, and only then `City.currentPopulation` (the sum of the imported neighborhoods, which understates the city). `builtup.Property.residents` (dwellings only: BAG *Residential function*) is written by `housing/signals.py` with the city's latest `average_size`, one `update()` per city (a saved single dwelling updates only itself; `Property` and the `ResidentialProperty` proxy are both connected). The dashboard's slider is persons per home (default = CBS value of the unit, `calculate_household_size`); `chain.what_if_demand` scales the stored demand by the population and size deviation, so default controls equal the stored value. Still open: `Urbanization -> Housing_Demand` (no `Urbanization` model), `Housing_Demand -> Zoning_Status/House_Price_Index`, and households are not split by tenure or size class. No `Accessibility` model exists anywhere, so `Facilities/Streets/Green_Area -> Accessibility -> Property` has no implementation (`Building.connectivity` is the closest analog, still under its own TODO). `Zoning_Status -> Property`, `Property -> House_Price_Index/Mortgage` — none of `Property`/`Mortgage`/`HousePriceIndex` have `save()` logic; the `calculations.py` functions only average pre-existing stored values. `HousingAffordability.save()` computes `affordabilityIndex` only from its own stored fields — it never pulls from `Mortgage`, `Rentals`, or watersupply tariff data, so `Rent/Mortgage/Water_Tariff_Afford -> Income_Expenses -> Affordability_Stress` and `Credit_Supply -> Mortgage` are unimplemented. `NumberUsers -> Water_Tariff_Afford` — no `NumberUsers` model; `MeteredResidential.userAffordability_PCT` is a flat input.

**watersupply** — Implemented via `save()` + `watersupply/signals.py` (population cascade → `ConsumptionCapita` → `TotalWaterDemand` → `SupplySecurity`; `ExtractionWater`/`ImportedWater` → `TotalWaterProduction`, `OPEX`, `SupplySecurity`; `WaterTreatment`/`MeteredResidential`/`PipeNetwork` → `OPEX`; `PipeNetwork`/`UsersLocation` → `CoverageWaterSupply`; `NonRevenueWater` → same-year ILI): `Supply_Security -> Service_Time` (same formula as `views._build_indicators`), `Imported_Water/WT_Cost/Network -> OPEX` (`OPEX.save()` sums extraction `opex_EUR_m3 * current_extraction_Mm3_yr`, imported water, mean treatment `UnitaryOPEX_EUR_m3` of the year x volume, and pipe maintenance; `TotalWaterProduction` is deliberately not added, its energy cost is already inside `opex_EUR_m3`). `TotalWaterDemand`/`TotalWaterProduction` are stored in Mm³/day; `calculate_supply_security()` converts to m³/day. The population → consumption → demand → supply security → service time equations live once in `watersupply/chain.py`, used by both the models' `save()` and `views._build_indicators`: stored records use `chain.baseline_population(city, year)` (CBS median forecast of the record's year, no extra growth; current population without projections), saving/deleting a median `PopulationProjection` refreshes the city's chain via signal, and the population dock's what-if runs the same functions per request without writing, so the dashboard with default controls equals the stored chain. Consumption per capita of a year without its own record comes from `ConsumptionCapita.for_year(city, year)` (latest earlier year, else earliest later), used by `TotalWaterDemand.save()` and the dashboard (`_get_consumption_capita`, which shows e.g. "(2015 data)" next to the slider until it is moved); saving or deleting a record re-saves every `TotalWaterDemand` of its city. Extraction is allocated by watershed, not by well location: `calculate_total_extraction(unit)` gives each unit its population share (of each well's `ExtractionWater.volume_m3_d()`: measured yearly extraction, else flow x operation hours, else flow x 24 h; `TotalWaterProduction` uses the same expression) (neighborhoods assigned by point on surface; area share as fallback) of every watershed's active extraction, the watershed being the well's `source.watershed` or the `Watershed` containing it (wells with neither keep the old in-unit rule). So `SupplySecurity` of a city is refreshed when a well anywhere in its watershed changes, when a `Watershed`/`AvailableFreshWater` changes (all cities), and when another city of the same watershed changes population (`_refresh_watershed_neighbours`, deferred inside `deferred_water_refresh`). `Network -> Real_Losses`: each real `NonRevenueWater` record points via `pipe` (FK, `related_name='losses'`) to the `PipeNetwork` where the leakage is presumed — `clean()` requires it for real losses (`specificLoss` in `REAL_CHOICES`) and forbids it for apparent ones; the column stays nullable for older rows — and `calculate_nrw(year, adminBund)` adds `real_losses_by_pipe` (m³/day and m³/km/day, worst first). Per admin unit, each real loss counts in proportion to the share of its pipe's length inside the unit (`Length(Intersection(...))`, like the dashboard's network length — pipes run well → users location and can cross many units, so a leak is split, never duplicated; pipe-less legacy rows only appear network-wide), apparent losses are split by the unit's share of `UsersLocation.usersTotal` (`apparent_share`, None without user counts), and ILI is recomputed as CARL/UARL over the unit's real losses. Still unimplemented: `calculate_collection_ratio()` ignores `userAffordability_PCT` and acceptance rate despite its docstring; `calculate_opex_recovery()` computes directly from stored totals rather than calling `calculate_collection_ratio()` or referencing NRW; `calculate_water_quality()`'s `acceptance_rate` is `Avg('acceptanceRate')`, unrelated to computed compliance — so `Samples_WQ -> User_Acceptance_WS` is unimplemented; `WaterTreatment` has no `save()`, so `WT_Efficiency -> WT_Cost` is unimplemented; `NonRevenueWater` ILI is only defined for real losses, so `Apparent_Losses -> ILI` is unimplemented; `UsersLocation.usersTotal/populationServed` and `SupplySecurity` for non-latest years are not refreshed by signals (OPEX/ExtractionWater/MeteredResidential/ImportedWater carry no year, so only the latest OPEX/SupplySecurity record is refreshed).

### Domain Apps

Each domain app contains spatial models related to a topic:

- **`administrative`** — Administrative hierarchy: Province > City > District > Neighborhood. Population and urban area cascade upward via signals.
- **`physicalEnv`** — LandCover (vector + raster), DEM, DSM, satellite imagery, surface/wall material properties, environmental costs. `HILUCSLandUse` is the INSPIRE HILUCS codelist (code `6.3.2`, label, description; all 98 values loaded by migration 0003), referenced by FK (`builtup.ZoningArea.zone_type`). `physicalEnv/hilucs.py` parses a HILUCS URI into its code — always look up by code, PDOK misspells some URIs — and `hilucs_q(field, codes)` filters a code and everything below it (housing's zoning groups use it). `SoilType` (code + name of the BIS Nederland soil map 1:50 000, unique together) derives in `save()` the SCS hydrologic soil group A–D from the name's Dutch texture words (`physicalEnv/soil.py::classify_soil_group`; most restrictive layer wins, all 171 names of the 2025 map classify) and the group's final infiltration rate range; `SoilArea` polygons point to it (catalog `bodemdata_soil_map`, bulk-written). `SoilType.unitCode`/`unitName` hold the main legend unit (`first_soilcode`/`first_soilname`, filled by the lookup's `defaults_from`, which also updates existing rows); the map colours polygons by it with the BRO Bodemkaart legend colours in `mainMap/styles/soilStyles.py` (305 units; layer styles otherwise live in `mainMap/styles/layerStyles.py`). `soil.py` also holds the TR-55 curve numbers per CORINE land-cover class (keywords match at word starts) and the SCS equations; `soil_landcover_composition(geom)` is the one DB query (soil x latest land-cover year, clipped to the unit). The water dashboard's Infiltration card applies them for the Rain Event slider (`rain_mm`, default 25 mm) in the pure `_build_indicators`, weighting runoff per piece rather than averaging CN. `GroundwaterDepth` (raster, one row per `statistic` GHG/GLG/GVG; catalog `bodemdata_ghg`/`bodemdata_glg`, BIS Nederland WCS, 50 m, cm below ground, 254 = 254 cm or deeper, 255 nodata) stays in Postgres: the composition query reclassifies the season's statistic (`SEASONS`: wet = GHG, dry = GLG; dashboard switch `season`) below `SHALLOW_GROUNDWATER_CM` (60, NEH 630) to polygons and reports those pieces as group D, except on drained land covers (`DRAINED_LAND_COVER`: built-up and paved classes keep their texture group, the drained letter of NEH 630's dual group). BIS has no groundwater values for most built-up cells (85 % in Enschede) or water; nodata counts as not shallow, and water/wetland curve numbers are 100/98 for every group. WCS entries can set `wcs_axis_labels` (BIS needs `X`/`Y`, PDOK takes the default `x`/`y`), and `load_raster_into_target_model` adds a catalog `statistic` to the upsert key.
- **`watersupply`** — Water infrastructure: extraction, treatment, pipe networks, coverage, NRW (non-revenue water), OPEX. Has `calculations.py` (pure query functions) + `views.py` (indicator assembly + HTMX recalculation).
- **`urban_heat`** — Thermal comfort rasters (UTCI, PET, MRT, LST, SVF, SUHII) and Nature-Based Solutions. `urban_heat/lst/` computes LST from Landsat 9 (or 8) with the SMW algorithm and CrossTwin's NDVI layer: `coefficients.py` (SMW table), `smw.py` (pure numpy equations), `grid.py`, `gee.py` (Earth Engine inputs), `pipeline.py::calculate_lst()`. `urban_heat/solweig/` computes Tmrt, UTCI and PET for a map view and hour with SOLWEIG-GPU (`inputs.py`, `met.py`, `pipeline.py`, `views.py`; runs are `ThermalComfortRun` rows; `docs/THERMAL_COMFORT.md`). `NeighborhoodHeat` (one row per neighborhood, KEA): PET means 2012/2022, RIVM class, cooling indoors/outdoors, canopy and shade shares.
- **`housing`** — Supply/demand, household size (persons per home, from CBS), mortgages, rentals, HPI, affordability stress. Has `calculations.py` + `views.py` following the same pattern as watersupply, plus `chain.py` (pure equations) and `signals.py` (population / household size → demand and dwelling residents). `NeighborhoodSocialProfile` (one row per neighborhood, KEA): rental share, socio-economic status, frail health, loneliness, neighborhood type.
- **`builtup`** — Physical urban fabric: ZoningArea, Street, Park, Facility, Building, Property. `Building` carries KEA enrichment fields (`canopyCover_pct`, `meetsCanopy30Rule`, `facadeShadeScore`, `floodDepth_p99_m`, `floodDepthClass`), and `NeighborhoodClimateRisk` (one row per neighborhood, KEA) holds pile-rot and settlement risk per scenario and dry floors. These KEA values are stored inputs, no DAG edge reads them yet. Has `calculations.py` + `views.py` (building stock/coverage/FAR, type mix, construction period, street density clipped to the unit, park area and facilities per inhabitant; what-if `green_added_ha`).
- **`nature`**, **`weather`**, **`Energy`** — Additional domain data.

### Indicator Pattern (watersupply, housing, urban_heat, builtup)

Domain dashboards follow a three-layer pattern:
1. **`calculations.py`** — Pure query functions that aggregate DB data. Each function documents its DAG edges.
2. **`views.py`** — `_get_adminUnit_data()` assembles all calculations into a dict; `_build_indicators()` is a pure function that derives display-ready metrics (supports what-if overrides like `consumption_override` or `interest_rate_override`); view functions render templates or return JSON.
3. **Templates** — HTMX-driven: a main page includes a partial grid that gets swapped on slider/input changes via `hx-get` to a `recalculate_indicators` endpoint.

`MOCK_DATA` dicts provide fallback values when the province doesn't exist in DB, allowing frontend development without a populated database.

Each domain's standalone dashboard (`water_indicators.html`, `heat_indicators.html`, `housing_indicators.html`, `builtup_indicators.html`) and its HTMX side-panel partial (`<app>/partials/indicators_panel.html`) render the **same** slider/gauge markup and are driven by the **same** JS file — do not duplicate slider/gauge logic between the two.

- **`Templates/indicators_base.html`** — shared `<html>/<head>`/htmx-script shell for the standalone pages. Extend it with `{% block slider %}`, `{% block grid %}`, `{% block extra_js %}`, etc.; put only domain-specific markup in the child template.
- **`core/static/js/indicators/<domain>.js`** (e.g. `water.js`, `heat.js`, `housing_panel.js`, `builtup.js`) — the slider/gauge JS for that domain, wrapped in an IIFE. Must re-run safely after every `htmx:afterSwap`, since the panel partial gets swapped back in on every recalculation — expose any function the swap needs to re-invoke (e.g. `window.initGauges`) as a global rather than a closure-local.
- **Do not write inline `<script>` blocks in indicator templates.** When adding or changing dashboard behavior, put the JS in `core/static/js/indicators/<domain>.js` and load it via `{% static %}`, following the existing files as the pattern to match.

### Signal-Driven Computations

- **`administrative/signals.py`** — When a Neighborhood is saved/deleted, population, density and urban_area cascade up through District > City > Province using `_recompute_population()` (sums both `currentPopulation` and `urban_area` per level). Uses `update()` (not `save()`) to avoid infinite loops.
- **`physicalEnv/signals.py`** — When a `LandCoverVector` row is saved/deleted, recomputes the affected City's Neighborhoods' `urban_area` from PostGIS intersection area against qualifying (urban fabric/road/rail/transport) land-cover polygons for the most recent `year`, in **one set-based `UPDATE … RETURNING`** (polygons fully inside a neighborhood skip `ST_Intersection`). It then re-enters `administrative/signals.py`'s cascade (`_recompute_population`) once per district and once for the city and province, since the `UPDATE` does not fire `post_save`. Area is `ST_Area` in the storage CRS's metres (geography cast if the CRS is geodetic).
- **`core/signals.py`** — `post_save` on every RASTER_REGISTRY model auto-exports to COG via `export_raster_to_cog()`; `post_save`/`post_delete` on every VECTOR_REGISTRY model bumps its cache version (`core/cache.py`), which invalidates the map's cached GeoJSON. Code that writes vector rows with `update()`/`bulk_create` must call `bump_layer_version()` itself.
- **Bulk writes** — wrap them in `importer/batching.py::deferred_cascades()` (= `administrative.signals.deferred_population_cascade()` + `physicalEnv.signals.deferred_urban_area()` + `watersupply.signals.deferred_water_refresh()`; the CBS OData import runs inside it) so the cascades run once per affected parent when the block ends instead of once per row. Both flush even if the block raises (errors during that flush are logged, not raised over the original). Use `physicalEnv.signals.schedule_urban_area_recompute(city_id)` rather than calling the recompute directly, so it respects an enclosing deferral.

### Implementing a DAG Edge (signal/receiver contract)

**Every new or changed indicator that implements an edge of `core/DAG.dot` must follow this contract.** It is how the causal graph becomes executable: there is no central graph engine. Each node computes itself from its inputs, each edge is a receiver that re-runs the target when the source changes, and a change travels Driver → Impact one edge at a time. `watersupply/` is the reference implementation; copy its shape.

1. **Node = model, equation = the node's `save()`.** A stored DAG node is a model. Its derived fields are computed in its own `save()` from its inputs (its incoming edges). The `save()` docstring lists them as `DAG edges: Source -> Target`, using the node names from `DAG.dot` exactly. Never compute a node's value inside a receiver and write it onto the target. The receiver only triggers the target's `save()`.
2. **One equation, two callers: `<app>/chain.py`.** Any equation that both the stored path (`save()`) and the dashboard (`views._build_indicators`) need lives once, as a pure function in `<app>/chain.py` (no ORM queries; at most one clearly named DB helper such as `chain.baseline_population`). `save()` calls it with stored inputs; `_build_indicators` calls it with the request's what-if inputs. Never re-type an equation in `views.py`. Add a parity test: with default controls, the dashboard equals the stored value (`DashboardIsADeviationFromTheBaselineTests`).
3. **Edge = receiver in `<app>/signals.py`.** For an edge `A -> B`, add a `@receiver(post_save, sender=A)` (plus `post_delete` when deleting A changes B) whose body re-saves the affected B rows with `_resave(queryset)`. Re-saving B runs B's `save()` and fires B's own `post_save`, so the next edge (`B -> C`) runs automatically. Write that next edge as its own receiver; don't chain several edges inside one receiver. Every receiver:
   - has a unique `dispatch_uid` (`"<app>_<source>_<saved|deleted>"`);
   - returns early on `raw=True` (fixtures, backup restore). Map editing's restore must then trigger the cascade itself (see Map Editing);
   - names its edge(s) in a docstring or comment (`DAG edge: A -> B`);
   - is connected by the app's `apps.py::ready()` importing `signals`.
4. **Failures never block the source save.** Refresh dependents through `_resave()`, which logs `ValidationError` instead of raising it. A missing input in the target keeps its stored value rather than writing zero (e.g. `SupplySecurity.save()` without production).
5. **No loops.** The graph is acyclic; keep the code acyclic too. A receiver never writes to a node upstream of its source. Aggregations that would re-trigger themselves (parent sums of children) are written with `queryset.update()`, which fires no signal. After an `update()`:
   - call `bump_layer_version()` for vector models;
   - if another app depends on the aggregated value, send a **custom signal** (`django.dispatch.Signal`, defined in the upstream app, e.g. `administrative.signals.city_population_changed`) and let the downstream app subscribe to it.
6. **Cross-sector edges point one way.** The downstream app imports and subscribes to the upstream app's model or signal. The upstream app never imports the downstream app. A new sector that depends on population, for instance, adds a receiver for `city_population_changed` / `PopulationProjection` in its own `signals.py`; `administrative` stays untouched.
7. **Bulk writes stay O(parents).** Each app's "refresh city X" helper must check a thread-local deferral and queue the id instead of working (pattern: `watersupply.signals.deferred_water_refresh` / `_refresh_city_water`). Register the context manager in `importer/batching.py::deferred_cascades()` (mind the `ExitStack` order: whatever is fed by another cascade must exit after it, i.e. be entered first). Run importer loops inside `deferred_cascades()`. `bulk_create` skips signals entirely, so a model written by `BulkWriter` needs its receivers replayed by its finalizer.
8. **What-ifs never write.** Sliders and switches run the `chain.py` functions per request with override values. They must not save models or fire signals. The stored database holds the baseline; a what-if is a deviation from it. Geometric what-ifs (map editing) are real saves and go through rule 3 like any import.
9. **Year semantics.** Stored records with a `year` use the baseline population of *that* year (`watersupply.chain.baseline_population(city, year)`: CBS median forecast, no extra growth, current population as fallback), not `City.currentPopulation`. Records without a year refresh only the latest dependent record (see the OPEX/SupplySecurity note under watersupply).
10. **Tests and docs, per edge.** For each new edge add:
    - a test that saving (and deleting, if handled) the source updates the target;
    - a deferral test when the source is bulk-imported (count refreshes with `mock.patch.object(signals, '_resave', wraps=...)`).

    Then update `docs/functions_and_equations.tex` (equation, source location, status), the coverage count and gap list under **DAG Edge Coverage Gaps**, and the table below.

Pure dashboard-only statistics that no other node consumes (e.g. infiltration for a rain event, street density) may stay in `calculations.py` without a receiver. They still document their `DAG edges:`, and they move to rules 1–3 as soon as a downstream node needs their value stored.

#### Edge → function map (propagated edges)

| DAG edge(s) | Target computed in | Triggered by (receiver → source) |
|---|---|---|
| Neighborhood population / urban area → District → City → Province (`Total_Population` aggregation) | `administrative/signals.py::_recompute_population` (`update()`) | `neighborhood_changed`, `district_changed`, `city_changed` (`post_save`/`post_delete`); sends `city_population_changed` |
| neighborhood `urban_area` from land cover (derived field feeding `CityArea`; no explicit DAG edge) | `physicalEnv/signals.py::_recompute_neighborhood_urban_area` (set-based `UPDATE`) | `landcover_changed` ← `LandCoverVector`; re-enters the population cascade |
| `Population_Growth -> Total_Population` | `PopulationProjection` rows; `watersupply/chain.py::baseline_population` (stored), `administrative/population.py::get_population` (what-if); `City.save()` → `popGrowthRate` | CBS import (`CBS_PopulationForecast`) |
| `Total_Population, ConsumptionCapita -> Total_Water_Demand` (intermediate: yearly consumption, not a DAG node) | `ConsumptionCapita.save()` → `chain.consumption_m3_yr` | `city_saved` ← `City`; `city_population_cascaded` ← `city_population_changed`; `projection_changed` ← `PopulationProjection` (median only) |
| `Total_Population, ConsumptionCapita -> Total_Water_Demand` | `TotalWaterDemand.save()` → `chain.demand_m3_d` | `consumption_saved` ← `ConsumptionCapita` (also refreshes `MeteredResidential`) |
| `Total_Water_Demand / Total_Water_Prod -> Supply_Security -> Service_Time` (production = population share of each watershed's extraction) | `SupplySecurity.save()` → `calculate_total_production_day` → `calculate_total_extraction`; `chain.supply_security_pct`, `chain.service_time_hours` | `demand_saved` ← `TotalWaterDemand`; `extraction_changed` (cities of the well's watershed), `imported_changed`, `watershed_changed` ← `Watershed`/`AvailableFreshWater`, `city_population_cascaded`/`city_saved` (other cities of the watershed) (latest year) |
| `Total_Population, Household_Size -> Housing_Demand` (homes needed = baseline population / persons per home) | `HousingSupplyDemand.save()` → `housing/chain.py::baseline_population`, `demand_units` | `city_saved`/`city_population_cascaded` ← `City`/`city_population_changed`; `projection_changed` ← `PopulationProjection` (median only); `household_size_changed` ← `HouseholdSize` (all in `housing/signals.py`, deferred by `deferred_housing_refresh`) |
| `Household_Size -> Property` (each dwelling holds the average persons per home) | `housing/signals.py::_set_city_residents` (one `update()` of `builtup.Property.residents` per city; `property_saved` for a single dwelling) | `household_size_changed` ← `HouseholdSize`; `property_saved` ← `Property`/`ResidentialProperty` |
| `Available_FW -> Total_Extraction` | `ExtractionWater.save()` (source, emissions, costs) | direct save |
| `Total_Extraction -> Total_Water_Prod` | `TotalWaterProduction.save()` | `extraction_changed` ← `ExtractionWater`; `imported_changed` ← `ImportedWater`; `production_links_changed` (M2M) |
| `Total_Water_Prod / Imported_Water / WT_Cost / Network -> OPEX` (metered billing also refreshes it; no DAG edge) | `OPEX.save()` | `extraction_changed`, `imported_changed`, `metered_changed`, `treatment_changed`, `pipe_changed` (latest OPEX) |
| `Network, NumberUsers -> Coverage_WS` | `CoverageWaterSupply.save()` | `pipe_changed` ← `PipeNetwork`; `users_changed` ← `UsersLocation` |
| `Real_Losses -> ILI` | `NonRevenueWater.save()` (own row) + sibling `update()` | `nrw_changed` ← `NonRevenueWater` |
| `New_Units -> LandCover` (10 m urban-fabric buffer around a building drawn in the map editor) | `physicalEnv/landcover.py::urbanize_around` / `release_ring` (raw `UPDATE`/`DELETE` + `create()`; cut pieces in `UrbanFabricCut`; sends `landcover_rewriting`/`landcover_created` with the model as sender, journalled by `mainMap/signals.py`) | `building_created` ← `builtup.Building` (`post_save`, negative pk: created → urbanize; footprint changed → release + urbanize); `building_deleted` ← `post_delete` (release) |
| `Buildings -> DSM` (editor building changes as a DSM overlay) | `physicalEnv/dsm_patches.py::record_change` (`DSMBuildingPatch`), applied in `svf.load_dsm` → `apply_patches`; `DSMEdit` log for staleness | `building_dsm_saved`/`building_dsm_deleted` ← `builtup.Building` (editor changes only); `dsm_patch_changed` ← `DSMBuildingPatch` (raw included) |
| `DSM -> SVF -> Tmrt/PET`, `Meteorology -> Tmrt/PET/UTCI`, `Tmrt -> PET/UTCI` (SOLWEIG) | `urban_heat/solweig/pipeline.py::calculate` → `inputs.build`, `run_solweig` (solweig-gpu), `urban_pet` (pet-adjusted) | none: on demand, the map's Thermal Comfort tool (`/urban_heat/solweig/calculate/`, background `ThermalComfortRun`) |
| `RS_Imagery, LandCover -> LST` (Landsat B10 + NDVI layer → emissivity → SMW) | `urban_heat/lst/pipeline.py::calculate_lst` → `smw.land_surface_temperature` | none: on demand, the map's LST tool (`/urban_heat/lst/calculate/`) or `manage.py calculate_lst` |
| `DSM -> SVF` (horizon search, SVF = mean of 1 − sin(horizon angle) over the azimuths) | `physicalEnv/svf.py::calculate_svf` → `sky_view_factor` | none: on demand, the map's SVF tool (`/physicalEnv/svf/calculate/`) or `calculate_svf()` |
| (non-causal) raster → COG; vector → map cache | `core/signals.py` | `auto_export_cog`, `invalidate_layer_cache` on every registry model |

### Importer System (`importer/`)

Two import paths:
1. **File upload** (`views.py`) — Upload GeoJSON/Shapefile, map fields to any registered model, preview, then import with savepoints. Uses `MODEL_OVERRIDES` dict for per-model upsert keys.
2. **External data** (`views_external.py`, `external_catalog.py`, `external_data.py`) — Catalog-driven import from PDOK, CBS, Sentinel-2, Google Earth Engine and the KNMI Data Platform. The KNMI source (`KNMIImporter.fetch_latest`, e.g. `knmi_wbgt` → `urban_heat.WetBulbGlobeTemperature`) uses the server-side `KNMI_API_KEY`, needs no bbox, and skips a file whose valid time is already stored. KNMI entries with `format: "wms"` (`knmi_radar_forecast`) instead register a `weather.WMSLayer` row through the shared `register_wms_layer()` (also used by PDOK/Sentinel-2 WMS): `wms_name` fixes the row name (the tile proxy's URL segment), `wms_options` sets model fields such as `has_time_dimension`/`api_key_setting` (ignored when the model lacks them), and an explicit `legend_url` skips the GetCapabilities legend lookup. For districts and neighborhoods the import map picks the area of interest from cities and districts respectively (`bbox_from` in the catalog). The planned land use ATOM feed (`pdok_landcover_kadaster`, `_import_atom_gml_features`) streams PDOK's ~29 GB national GML and imports each `plu:ZoningElement` inside the bbox as a `ZoningArea`: `hilucslanduseHref` (its `plu:hilucsLandUse` href) → `zone_type` via an `__fk_lookup__` with `"parser": "hilucs_href"`, and title/plan type/valid-from from its `SpatialPlan` (plans come first in the file and are cached). `__fk_lookup__` resolution is shared by the GeoJSON and GML paths (`_resolve_fk_lookups`); parsers live in `_FK_LOOKUP_PARSERS`. The OpenStreetMap source (`OSMImporter.fetch`, `format: "overpass"`) runs each entry's `osm_query` statements on the Overpass API (`OVERPASS_URL` in `.env` overrides the public instance), with `out center` for point models and `out geom` otherwise. It converts the elements to GeoJSON (multipolygon relations are rebuilt from their member ways with shapely `polygonize`) and imports them through `_import_geojson_features`. Entries: `osm_parks` → `builtup.Park`, `osm_water_bodies` → `nature.WaterBodies`, `osm_amenities` → `builtup.Facility` (OSM tags mapped onto the six `Facility.type` values via `osm_classes`; the raw value goes to `subtype`), `osm_trees` → `nature.Tree`. All upsert on `osm:<type>/<id>` (`sourceID`/`localId`). The Klimaateffectatlas source (`source: "kea"`, 21 `kea_*` entries built by `_kea_entry`, `KEA_WFS_URL`; routed to `PDOKImporter.fetch_wfs`) imports climate-effect layers. Which layers go where, and why the other 47 are not imported, is in `docs/KEA_WFS_MAPPING.md` (with a mapping graph). Per-buurt layers (`_kea_neighborhood`) upsert one row per neighborhood on `neighborhood_id`. Per-pand layers (`_kea_building`) enrich existing BAG buildings. Generic GeoJSON-path directives added for it (`external_data.py`):
- `_prepare_features`: `@id` (the GeoJSON feature id as a property), `__nodata__`, `__value_maps__`, `__value_scales__`, and `__split__` (one feature per comma-listed value, with `zfill`).
- `_keep_existing`: `__require_existing__` (skip features whose key is not a stored row; prevents deferred-FK failures at COMMIT).
- `_enrich_rows`: `__enrich__` (update-only via `update()`, never creates, never writes the geometry, bumps the cache of every registry model on the table, including the `Energy` proxy).
- `_import_geojson_features(..., notes)` collects skipped-feature lines for the result message.

**Batching (`importer/batching.py`):**
- `SpatialParentIndex` resolves `__spatial_fk__` parents with prepared geometries + a bbox pre-check, probing each feature's `point_on_surface` (not its centroid). Parents are loaded with `.only("pk", "geom", <attrs read off them>)`.
- `BulkWriter` writes models listed in `BULK_IMPORT_MODELS` (LandCoverVector, Street, the nature layers) with `bulk_create`, 500 rows at a time, `ON CONFLICT DO UPDATE` for upserts on a unique field. Rows are grouped by their set of mapped fields so a missing property never blanks a stored value, and a failing batch is retried row by row. `bulk_create` skips `save()` and signals: a model belongs in the registry only if it has no `save()` override (`BulkImportRegistryTests` checks this) and its receivers are replayed by its finalizer. Add a `post_save` receiver to one of these models → add it to the finalizer or remove the model from the registry.
- `_import_geojson_features` and `_generic_import` run inside `deferred_cascades()`.
- `_generic_import` (file upload) maps every concrete field (attributes, FKs by name or id, geometry). `_fit_geometry_type` wraps/unwraps single vs multi geometries to the target field (e.g. a one-part MultiPoint into `ExtractionWater`'s `PointField`). Models without an upsert key in `MODEL_OVERRIDES` or a unique field always create rows, so re-uploading duplicates them.

### Raster Pipeline (`core/rasterOperations.py`)

1. PostGIS raster → `ST_AsGDALRaster` → temp GeoTIFF
2. Reproject to EPSG:4326 via rasterio
3. Convert to Cloud-Optimized GeoTIFF (COG) via `rio-cogeo`
4. COG stored on disk under `cogs/<app_label>/`, named `<index or ClassName>_<source>_<date>_<id>.tif` (`_cog_filename`; the class name keeps models of one app with the same source, date and id apart)
5. TiTiler serves tiles from the COG path

### Map Frontend (`mainMap/`)

- `map_view` renders `mainMap.html` with Mapbox token
- `available_layers` returns the full layer catalog (vector + WMS + raster) as JSON
- `model_geojson` builds one raw SQL statement per request (`_geojson_sql`): `ST_AsGeoJSON(ST_Transform(..., 4326), 6)`, FK display names via `LEFT JOIN` (not per-row sub-SELECTs; extra columns of the FK target for the popup are listed in `POPUP_RELATED_FIELDS` and arrive as `<fk>__<field>`, e.g. the soil type's name/group/infiltration rates on `SoilArea`), optional `?bbox=minLng,minLat,maxLng,maxLat` (`&&` on the GiST index) and `?zoom=z` (`ST_SimplifyPreserveTopology` to ~1 px below zoom 14; points never simplified). It returns PostgreSQL's JSON text as-is (`HttpResponse`, not `JsonResponse`) with an `X-Cache: HIT|MISS` header.
- GeoJSON responses are cached in the `geojson` cache alias (`CACHES` in settings: local memory, 64 entries, bodies ≤ 8 MB, 2 min) under a per-model version from `core/cache.py` (`layer_version` / `bump_layer_version`). The version only changes on writes made through Django, so edits from QGIS/psql/other scripts show up only when the entry expires — hence the short TTL (`GEOJSON_CACHE_TTL`). Local memory is per process: with several workers, point `CACHES` at Redis so invalidation reaches all of them.
- Map styles live in the `mainMap/styles/` package: `layerStyles.py` (`LAYER_STYLES` per registry key: catalog `color`, Mapbox `layers`, optional `legend`; `FALLBACK_COLORS`; building type colours), `soilStyles.py` and `landCoverStyles.py` (style + legend built per request in `available_layers` from the classes present in the DB), `rasterStyles.py` (raster colormaps/value ranges, used by `core/views.py`). Add a new layer's style to `LAYER_STYLES`; a data-driven one gets its own module there.
- `layer_bounds` returns WGS84 `[[west, south], [east, north]]`, using `ST_EstimatedExtent` only for tables with ≥ `ESTIMATED_EXTENT_MIN_ROWS` (100 000) rows. The estimate is as old as the last `ANALYZE`, so smaller tables get an exact `ST_Extent`.
- `Layers.js`: vector layers with ≥ `VIEWPORT_LOAD_MIN_FEATURES` (5 000, in `Config.js`) features load by viewport and reload on `moveend` (debounced, superseded requests aborted); `zoomToLayer` uses `/bounds/` for them. Administrative layers always load whole — their click handlers and the admin-unit panels need every unit.
- Floating map overlays (toolbar, layers panel, side panel, population dock, legends, WMS scrubber, tour card) share `--overlay-bg`/`--overlay-blur`/`--overlay-shadow` tokens in `mainMap.css` and are draggable by their header via `core/static/js/Draggable.js::makeDraggable(el, handleSelector)` (delegated, so handles added later work; double-click the handle to reset; disabled below 768 px). Wiring is in `Events.js::initializeUI`.
- WMS tiles (`addWmsLayer`, `wmsTileUrlForTime`, the groundwater source) use `WMS_TILE_SIZE` (512, `Config.js`) for both `tileSize` and the `width`/`height` params — keep the two equal. Remote WMS cost is per request (~0.5–3 s each at KNMI), so bigger tiles = fewer requests. `weather/views.py::wms_tile_proxy` caches tiles in `CACHES["wms_tiles"]` (24 h for `TIME=` frames, 5 min otherwise), sends matching `Cache-Control`, and reports `upstream;dur` / `cache;desc` in `Server-Timing`. Upstream calls go through the module-level `_session` (keep-alive); mock `weather.views._session.get` or `_fetch_with_retry` in tests, and clear `get_cache("wms_tiles")` in `setUp`.
- The map fills the whole `.app-shell` (there is no side column). Upload Data, Retrieve Data from APIs and the year selector live in the **Actions menu** (`#actions-menu`), a drop-up opened from the bottom bar's `#actions-menu-btn`, which shows the active year while collapsed. The menu is a sibling of `.bottom-bar`, not a child: the bar is a stacking context at `z-index: 9`, below the side panel and population dock, so `mainMap.js::positionActionsMenu()` anchors it to the button instead. It closes on an outside click or Escape.
- Mapbox's own extruded buildings (the `3d-buildings` layer from `Map_init.js::add3DBuildings`) are hidden while any `builtup` layer is shown (loaded and checked), and only then: `Layers.js::sync3DBuildings()` runs after every vector layer load, every `toggleLayerVisibility()` and every `add3DBuildings()` (a basemap switch re-creates the layer).
- All legends live in `#legend-stack`; `Layers.js::repositionDynamicLegends()` moves the stack so it clears the side panel and the population dock (re-run by observers in `Events.js`), unless the user has dragged it. Append new legends to `#legend-stack`, not `.map-wrapper`.
- Templates live in `Templates/` (capital T, configured in settings)
- **Map settings** (`#settings-card`, staff only, header's *Map settings* button; `core/static/js/MapSettings.js`, `mainMap/settings_views.py`, partials `map_settings.html`/`settings_editable_row.html`/`settings_style_form.html`): tab *Editable layers* (above) and tab *Styles*. Styles are `mainMap.LayerStyleOverride` rows on top of the code defaults in `mainMap/styles/`, storing only what differs (Reset deletes the row). `styles/overrides.py::vector_style(key)` resolves a vector layer's catalog colour, style layers and legend (default + override; `available_layers` uses it with one `vector_overrides()` query per request): scalar paint properties per style-layer index, and the colours of a colour `match` expression by category (legend entries carry `value`; `'__other__'` = the match fallback). Raster overrides are keyed by `rasterStyles.raster_style_key()` (the `INDEX_STYLES` key, else the `MODEL_STYLES` key) and applied in `resolve_raster_style` (colormap, rescale; `null` = from the data). Saves answer with `HX-Trigger` `style-changed` / `editable-changed`; `MapSettings.js` re-adds the layer (`addLayer(config, {fit: false})`) or updates the catalog entry's `editable` flag, and paint inputs preview live with `setPaintProperty`. Overrides are global (all visitors) and read per request, so several workers stay consistent.
- **LST tool** (`#lst-card`, `core/static/js/LstTool.js`, opened from the Actions menu's *Calculate for this view* section): lists the Landsat scenes over the current view and computes LST for it (`urban_heat/lst/views.py` → `pipeline.calculate_lst(bbox_wgs84=...)`). The grid is the view clipped to the NDVI layers' coverage; overlapping NDVI layers are merged newest first; areas over ~48 MB of Earth Engine download (~40×40 km at 30 m) are refused. A recalculation with the same scene replaces the LST rows whose extent it covers (with their COG files); the frontend drops them with `Layers.js::removeLayer()` and adds the new row's catalog entry (`mainMap.views.raster_layer_entry`). Synchronous request, ~10–60 s. Calculating is staff only; listing scenes is open.
- **SVF tool** (`#svf-card`, `core/static/js/SvfTool.js`, Actions menu → *Calculate for this view* → Sky View Factor; reuses the LST card's `lst-*` classes and closes it on open, and vice versa): on open and after each map move it asks `/physicalEnv/svf/info/` which DSM covers the view and how big the grid is, and labels the button *Recalculate* when a stored SVF of that DSM already covers the view. Radius (25–200 m) and cell (DSM's own, 1/2/5 m) selects. Calculate POSTs `physicalEnv/views.py::svf_calculate` → `svf.calculate_svf(bbox_wgs84=...)`; the frontend removes the replaced layers and adds the new one. Staff only to calculate.
- **Thermal Comfort tool** (`#solweig-card`, `core/static/js/SolweigTool.js`, Actions menu → *Calculate for this view* → Thermal Comfort (SOLWEIG); reuses the `lst-*` classes, and the LST/SVF/thermal cards close each other): date + hour (local time at the view centre), cell size, weather source (Manual / Nearest KNMI station / ERA5, *Fetch* fills the editable inputs). `info` shows the DSM, grid, sun position and device; *Calculate* POSTs a background run and polls `/urban_heat/solweig/runs/<id>/`, then adds the UTCI layer and lists Tmrt/PET. Staff only to calculate. The same file owns the **stale mark**: after `feature-saved`, `backup-restored` and map moves it asks `/urban_heat/solweig/stale/?bbox=` and shows `.stale-dot`s on `#actions-menu-btn` and the SVF / Thermal Comfort rows.
- `core/static/js/mainMap.js` holds `mainMap.html`'s page-level wiring (map init, the Actions menu, guided tour, the admin-unit-driven panel registry). It depends on `Config.js`/`map_init.js` and on `window.MAPBOX_ACCESS_TOKEN` being set inline by `mainMap.html` before it loads. As with the indicator dashboards, keep new map-page behavior in this file rather than adding inline `<script>` blocks to `mainMap.html`.

### Map Editing (`core/editing.py`, `core/static/js/Editing.js`)

Staff users (`is_staff`; **Log in** at the top right of every page, `django.contrib.auth.urls` under `/accounts/`, template `Templates/registration/login.html`) can create, reshape, edit and delete objects of the layers switched on in the map's **Map settings** panel (stored as `mainMap.EditableLayer`, one row per editable layer; migration 0002 seeded the five built-up layers). The form rules per layer (`exclude`/`optional`) stay in `core/editable_layers.toml` (`core.editing.FIELD_RULES`, read at startup), since they follow from each model's `save()`. Design and decisions: `docs/MAP_EDITING.md`; equations: `docs/functions_and_equations.tex`.
- The form is a `modelform_factory` ModelForm swapped into `#panel-body`; the geometry travels as WGS84 GeoJSON in a hidden field and the GIS form field checks its type and reprojects it. Saving goes through `obj.save()`, so derived fields, signals and cache invalidation apply. User-created objects of a model with a non-auto pk (`Building`, BAG ids) get negative ids (`_next_negative_pk`).
- **To make a layer editable:** switch it on in Map settings → Editable layers. `core.editing.enable_blocker()` refuses layers whose model overrides `save()` and has no table in `core/editable_layers.toml`, and `watersupply` layers (`RAW_SKIPPING_APPS`, receivers skip raw saves so Restore would leave cascades stale). For those, first add a `["app_label.ClassName"]` table with `exclude` (fields its `save()` derives) and `optional` (fields `save()` fills in) and restart the server. `load_editable_layers()` rejects a malformed file at startup; `mainMap/test_editing.py` checks every key is a vector layer and every field exists. If its app has receivers that skip `raw=True` saves (e.g. `watersupply/signals.py`), backup restore must trigger those cascades itself.
- **Backup / restore:** one restore point at a time (`EditBackup`). After it is created, `journal()` stores each object's original row (first pre-image wins) before the editor changes it. `restore_backup()` reverts only those rows in one transaction (raw saves, then deletes of objects created since), rolling everything back if a reference blocks it. Changes made outside the editor (importer, admin, psql) are not journalled. A side effect another app makes for an edit can be journalled through a custom signal that `mainMap/signals.py` subscribes to: the urban-fabric buffer of a new building (`physicalEnv.landcover.landcover_rewriting`/`landcover_created`, layer key `physicalEnv.LandCoverVector`) is undone by Restore this way.
- `feature_form`/`feature_delete` save and delete inside `core.editing.editor_change()`; receivers that must react to a user's edit but not to imports check `is_editor_change()` (physicalEnv's `Buildings -> DSM` patch). The backup bar counts only journalled rows of map layers (`VECTOR_REGISTRY`), not bookkeeping rows such as `UrbanFabricCut` or `DSMBuildingPatch`.
- FK constraints are `DEFERRABLE INITIALLY DEFERRED`; `_check_constraints()` forces the check inside the atomic block so delete/restore conflicts surface as messages instead of failing at commit.
- While editing (`isEditing()`), feature popups, admin-unit clicks and `refreshActivePanel()` are suspended; a `MutationObserver` on `#panel-body` attaches/detaches Mapbox GL Draw. The `feature-saved` / `backup-restored` HTMX events reload layers via `Layers.js::reloadLayer()`.

### API Routes

| Path | Purpose |
|---|---|
| `/` | Main map view |
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
| `/physicalEnv/svf/info/`, `/physicalEnv/svf/calculate/` | Map SVF tool: DSM, grid and existing SVF for `?bbox=`; compute + store SVF for the view (POST, staff) |
| `/housing/` | Housing indicators dashboard |
| `/builtup/` | Built-up fabric indicators dashboard |

### Testing

Tests use `PostGISTestRunner` (`DigitalTwin/test_runner.py`) which creates the test DB, installs PostGIS extensions, and patches Django's `prepare_database` to avoid superuser requirement. Always use `--settings=DigitalTwin.settings_test --keepdb` (see Common Commands). Tests that hit the GeoJSON endpoint should clear the `geojson` cache in `setUp` (`core.cache.get_cache('geojson').clear()`): `TestCase` rolls back the DB but not the cache. Pin query counts with `assertNumQueries` on hot endpoints (`ModelGeoJsonTests` keeps `model_geojson` at one query).

## Key Patterns to Follow

- All spatial models use `srid=settings.COORDINATE_SYSTEM` (EPSG:28992), not hardcoded SRIDs
- Models with computed fields implement logic in `save()` — check existing patterns before adding new ones
- A DAG edge with a stored target = the target's `save()` (equation, via `<app>/chain.py` when the dashboard needs it too) + a receiver on the source in `<app>/signals.py` that `_resave()`s the target; what-ifs call the same `chain.py` functions and never write — see [Implementing a DAG Edge](#implementing-a-dag-edge-signalreceiver-contract)
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

