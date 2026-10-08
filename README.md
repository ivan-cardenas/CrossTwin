# 🌍 CrossTwin

A **Django-based digital twin platform** for Dutch geospatial urban data — water supply, urban heat, energy, housing, and nature. PostgreSQL/PostGIS handles spatial storage, Mapbox GL JS renders the map, and a separate TiTiler (FastAPI) service serves raster (COG) tiles.

The project follows the **DPSIR framework** (Driver → Pressure → State → Impact → Response) to model causal relationships between urban systems — see [`core/DAG.dot`](core/DAG.dot).

## 📌 Project Information

- **Domain**: Urban digital twin — water supply, urban heat, housing, energy, nature
- **Default CRS**: EPSG:28992 (Amersfoort / RD New), set via `COORDINATE_SYSTEM` in `.env`
- **Stack**: Django 5 · PostgreSQL/PostGIS · GDAL/GeoPandas · Mapbox GL JS · TiTiler (FastAPI) · HTMX + Tailwind

## 📂 Project Structure

| 📁 Folder | 📝 Contains | Description |
|---|---|---|
| `DigitalTwin/` | `settings.py`, `urls.py`, `test_runner.py` | Django project config, env loading, caches, custom PostGIS test runner |
| `core/` | `utils.py`, `signals.py`, `cache.py`, `middleware.py`, `rasterOperations.py`, `DAG.dot`, `static/js/` | Model registry, layer-cache versions, query-stats middleware, raster→COG export pipeline, DPSIR causal graph, shared frontend JS |
| `mainMap/` | `views.py`, `urls.py`, `charts.py`, `editing.py`, `styles/` | Interactive map view, layer catalog + GeoJSON API, map editing, population dock charts; `styles/` holds every map style: vector layer styles (`layerStyles.py`), soil map colours (`soilStyles.py`), land-cover legend (`landCoverStyles.py`), raster colormaps (`rasterStyles.py`) |
| `importer/` | `views.py`, `views_external.py`, `external_catalog.py`, `external_data.py`, `batching.py` | File-upload import + external catalog import (PDOK, CBS, BIS Nederland, OpenStreetMap, Sentinel-2, GEE, KNMI, RIVM); bulk writes and deferred cascades |
| `docs/` | `PERFORMANCE.md`, … | Performance review and implementation status |
| `administrative/` | `models.py`, `population.py`, `signals.py` | Province > City > District > Neighborhood hierarchy, population projection |
| `watersupply/` | `models.py`, `calculations.py`, `views.py`, `signals.py` | Water infrastructure, indicator dashboard (incl. SCS infiltration with rain-event and groundwater-season what-ifs) |
| `urban_heat/` | `models.py`, `calculations.py`, `views.py` | Thermal comfort rasters (UTCI, PET, MRT, LST, SVF), NBS |
| `housing/` | `models.py`, `calculations.py`, `views.py` | Supply/demand, mortgages, rentals, affordability |
| `builtup/` | `models.py`, `calculations.py`, `views.py` | Streets, parks, facilities, buildings, properties, zoning (HILUCS land use), indicator dashboard |
| `physicalEnv/` | `models.py`, `soil.py`, `hilucs.py`, `signals.py` | Land cover, DEM/DSM, soil map + hydrologic soil groups, groundwater depth (GHG/GLG), SCS Curve Number method, HILUCS land-use codelist |
| `nature/`, `weather/`, `Energy/` | `models.py` | Water bodies, forests, green space, trees; weather; energy domain data |
| `Templates/` | `mainMap.html`, `indicators_base.html`, `<app>/partials/` | Shared HTML shells + HTMX partials |
| `tiler.py` | — | Standalone FastAPI app serving COG tiles (run as its own process) |

🚀 *Registries in `core/utils.py` auto-discover every model in the domain apps above — no manual layer wiring needed.*

## 🔧 Requirements

- Python 3.11 (the pinned GDAL wheel in `requirements.txt` targets `cp311`)
- PostgreSQL with `postgis`, `postgis_topology`, `postgis_raster`, `postgis_sfcgal`, `pgrouting`
- A Mapbox access token

Optional, only needed for specific External Data Import sources:
- `SENTINEL_CLIENT_ID` / `SENTINEL_CLIENT_SECRET` — Copernicus Data Space (openEO), for Sentinel-2 imports
- `KNMI_API_KEY` — KNMI Data Platform, for weather/WBGT imports
- `OVERPASS_URL` — another Overpass API instance for OpenStreetMap imports (default: the public overpass-api.de)
- A Google Earth Engine service-account JSON (pasted into the UI per import, not stored in `.env`)

## 📦 Installation

```bash
git clone <repo-url>
cd CrossTwin

python -m venv .venv
.venv\Scripts\Activate        # Windows

pip install -r requirements.txt
```

**Database:**

```sql
CREATE DATABASE crosstwin;
CREATE USER your_username WITH PASSWORD 'your_password';
ALTER DATABASE crosstwin OWNER TO your_username;
GRANT ALL PRIVILEGES ON DATABASE crosstwin TO your_username;

\c crosstwin
GRANT ALL ON SCHEMA public TO your_username;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO your_username;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO your_username;

CREATE EXTENSION postgis;
CREATE EXTENSION postgis_topology;
CREATE EXTENSION postgis_raster;
CREATE EXTENSION postgis_sfcgal;
CREATE EXTENSION pgrouting;
```

**`.env` file** (project root):

```env
SECRET_KEY=your-secret-key-here
DEBUG=True

DATABASE_NAME=crosstwin
DATABASE_USER=your_db_user
DATABASE_PASSWORD=your_db_password
DATABASE_HOST=localhost
DATABASE_PORT=5432

MAPBOX_ACCESS_TOKEN=your_mapbox_token
TITILER_BASE_URL=http://localhost:8001

COORDINATE_SYSTEM=28992  # EPSG code for Dutch RD New

# Optional — External Data Import sources
SENTINEL_CLIENT_ID=your-cdse-client-id
SENTINEL_CLIENT_SECRET=your-cdse-client-secret
KNMI_API_KEY=your-knmi-api-key
OVERPASS_URL=https://overpass-api.de/api/interpreter  # OpenStreetMap imports

# Optional — performance measurement (see docs/PERFORMANCE.md §0)
QUERY_STATS=True          # per-request query count + DB time (default: same as DEBUG)
QUERY_STATS_SLOW_MS=500   # log requests slower than this as warnings
SQL_LOG=False             # print every SQL statement (needs DEBUG=True)
```

**Migrate and create a superuser:**

```bash
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser
```

## ▶️ Running the Project

CrossTwin runs as **two servers**, in separate terminals:

```bash
python manage.py runserver 8000
uvicorn tiler:app --port 8001 --reload
```

Or run `start.bat` on Windows, which starts both. Visit `http://localhost:8000`.

`start.bat` first runs `python tools/check_postgres.py` (you can run it on any OS). It connects with the `DATABASE_*` settings of `.env` and checks for the `postgis` and `postgis_raster` extensions. If something is missing it says what and how to fix it, and `start.bat` stops:

- **PostgreSQL not installed**: `winget install --id PostgreSQL.PostgreSQL.17 -e` on Windows (Homebrew / apt on macOS / Linux).
- **PostgreSQL installed but not running**: the `net start postgresql-x64-<version>` command for the service it finds.
- **PostGIS not installed**: PostGIS is not on winget; install the PostGIS bundle with Stack Builder (included with the PostgreSQL installer) or the [OSGeo installer](https://download.osgeo.org/postgis/windows/).
- **Extensions not created, wrong credentials, missing database**: the SQL or `.env` setting to fix.

## 🏗️ Architecture

### Model registry (`core/utils.py`)

`build_model_registry()` scans a hardcoded list of domain apps and builds four registries:

- **`MODEL_REGISTRY`** — every model from the allowed apps
- **`VECTOR_REGISTRY`** — models with a `GeometryField` (no `RasterField`)
- **`RASTER_REGISTRY`** — models with a `RasterField`
- **`WMS_REGISTRY`** — models whose registry key contains `"WMS"`

These drive the generic layer API, the map's layer catalog, and the importer's field-mapping UI. **Adding a domain app** means adding it to `allowed_apps` in `core/utils.py` *and* `INSTALLED_APPS` in `DigitalTwin/settings.py`.

### Signal-driven computation

- `administrative/signals.py` — cascades population/density Neighborhood → District → City → Province via `_recompute_population()`, using `update()` (not `save()`) to avoid signal recursion.
- `physicalEnv/signals.py` — when land cover changes, recomputes every neighborhood's `urban_area` in the city with one set-based SQL `UPDATE`, then cascades each parent once.
- `core/signals.py` — `post_save` on every `RASTER_REGISTRY` model auto-exports it to a COG (see [Raster pipeline](#🛰️-raster-pipeline)); `post_save`/`post_delete` on every vector model invalidates that layer's cached GeoJSON.
- Bulk imports wrap their writes in `importer/batching.py::deferred_cascades()`, so the cascades run **once per affected parent** at the end instead of once per imported row.
- `watersupply/signals.py` — cascades population → `ConsumptionCapita` → `TotalWaterDemand` → `SupplySecurity`, and re-derives `OPEX`/`CoverageWaterSupply`/NRW indicators from their upstream inputs.

### Map frontend (`mainMap/`)

- `map_view` renders `Templates/mainMap.html` with the Mapbox token; `available_layers` returns the full layer catalog as JSON.
- `model_geojson` serves any registered vector model in one SQL statement: coordinates at 6 decimals (~10 cm), FK names via joins, optional viewport filter (`?bbox=`) and zoom-based simplification (`?zoom=`, below zoom 14). Responses are cached per layer and invalidated when its rows change.
- Large layers (≥ 5 000 features, except administrative boundaries) load **only the current viewport** and reload after each pan/zoom.
- **Styles** live in `mainMap/styles/`. `layerStyles.py::LAYER_STYLES` maps a registry key (`app_label.Model`) to its catalog colour, Mapbox style layers and an optional legend; layers without an entry get a fallback colour. Land cover and the soil map build their style and legend per request from the classes actually imported (`landCoverStyles.py`, `soilStyles.py`); raster colormaps and value ranges are in `rasterStyles.py`.
- **Popups** show every property with the label, unit and help text of its model field. Columns of a linked table can be added through `POPUP_RELATED_FIELDS` in `mainMap/views.py`; they arrive as `<fk>__<field>` on the same SQL join (e.g. a soil polygon's soil name, hydrologic group and infiltration rates), and styles can match on them too.
- Floating panels, legends and the toolbar are translucent and **draggable by their header** (double-click the header to reset). Legends are stacked in one container that moves out of the way of the side panel and population dock.
- `core/static/js/mainMap.js` holds page-level wiring (map init, right panel, year selector, guided tour); `Draggable.js`, `Layers.js`, `Events.js` hold dragging, layer loading and UI events. New map-page behavior belongs in these files, not in inline `<script>` blocks.

### Indicator dashboards (watersupply, housing, urban_heat)

Each follows the same three-layer pattern:

1. **`calculations.py`** — pure query functions, each documenting the DPSIR/DAG edges it implements.
2. **`views.py`** — `_get_adminUnit_data()` assembles calculations into a dict; `_build_indicators()` derives display-ready metrics with what-if overrides (`consumption_override`, `interest_rate_override`, …).
3. **Templates** — the standalone dashboard and the map's HTMX side-panel partial render the **same** slider/gauge markup and share the **same** JS file in `core/static/js/indicators/<domain>.js` (wrapped in an IIFE, re-runs safely after every `htmx:afterSwap`).

`MOCK_DATA` dicts provide fallback values when a province has no DB data, so frontend work isn't blocked on a populated database.

## 🧩 Domain Apps

| App | Covers |
|---|---|
| `administrative` | Province > City > District > Neighborhood; population projection |
| `physicalEnv` | Land cover (vector + raster), DEM, DSM, satellite imagery, surface materials |
| `watersupply` | Extraction, treatment, pipe networks, coverage, NRW, OPEX |
| `urban_heat` | UTCI, PET, MRT, LST, SVF, SUHII rasters; Nature-Based Solutions |
| `housing` | Supply/demand, mortgages, rentals, HPI, affordability stress |
| `builtup` | Zoning, streets, parks, facilities, buildings, properties |
| `nature`, `weather`, `Energy` | Additional domain data |
| `importer` | File-upload and external-catalog import pipelines |
| `mainMap` | Interactive map view and layer catalog API |
| `core` | Model registry, generic layer API, raster export pipeline, signals |

## 🔗 DPSIR Causal Network

The full causal graph lives in [`core/DAG.dot`](core/DAG.dot) (Graphviz). Each domain's `calculations.py` documents which edges its functions implement:

```python
# DAG edges: Central_Bank -> Mortgage
```

**Of the 103 edges in the graph, only 30 are backed by real derivation logic** (a `save()` or `calculations.py` function that reads the source field — not just a docstring claiming the edge). See [`TODO.md`](TODO.md) for the full per-app gap analysis and checklist before extending any dashboard's calculations.

## 📥 Importer System

Two paths, both under `/importer/`:

1. **File upload** — upload GeoJSON or a zipped Shapefile, map source fields to any registered model, preview, then import inside DB savepoints. *Known gap: only geometry and upsert-key columns are imported today; other mapped attribute columns are ignored.*
2. **External catalog** — catalog-driven import:

| Source | Provides | Auth |
|---|---|---|
| PDOK | Admin boundaries, BAG buildings, roads, water, elevation, land cover, zoning plans (each zoning element with its HILUCS land use) | None |
| RIVM | Per-building energy labels → `builtup.Building` (import BAG buildings first) | None |
| CBS | National statistics via OData, incl. population forecasts | None |
| BIS Nederland (bodemdata.nl) | Soil map 1:50 000 (WFS) → `SoilType`/`SoilArea` with SCS soil group, drawn in the colours of the BRO Bodemkaart legend; groundwater depth GHG/GLG (WCS, 50 m) → `GroundwaterDepth` | None |
| OpenStreetMap (Overpass API) | Parks → `builtup.Park`, water bodies → `nature.WaterBodies`, amenities (nodes only) → `builtup.Facility`, trees → `nature.Tree` | None (`OVERPASS_URL` optional) |
| Sentinel-2 | Land cover + NDVI/NDWI/moisture/true-color via openEO | `SENTINEL_CLIENT_ID`/`SECRET`, else UI prompt |
| KNMI Data Platform | Weather observations (e.g. WBGT) | Server-side `KNMI_API_KEY` |
| Google Earth Engine | Arbitrary GEE assets, exported as GeoTIFF | Service-account JSON pasted per import |

For districts/neighborhoods, the import map picks the area of interest from the parent city/district (`bbox_from` in the catalog).

Large imports are batched (`importer/batching.py`): spatial parents (the city a polygon lies in, …) are found with prepared geometries, and models without their own `save()` logic — land cover, streets, facilities, soil polygons, the nature layers and trees — are written 500 rows at a time with `bulk_create` / `INSERT … ON CONFLICT`. Models with `save()` logic (buildings, the administrative hierarchy) are still saved row by row.

## 🛰️ Raster Pipeline

Every `RASTER_REGISTRY` model auto-exports to a tile-servable COG on save:

1. PostGIS raster → `ST_AsGDALRaster` → temp GeoTIFF
2. Reproject to EPSG:4326 via `rasterio`
3. Convert to COG via `rio-cogeo`
4. Store under `cogs/<app_label>/`
5. TiTiler serves tiles from that path

Raster models need a `cog_path` field to participate. Bulk-export with:

```bash
python manage.py export_cogs
```

## 🔌 API Routes

| Path | Purpose |
|---|---|
| `/` | Main map view |
| `/api/layers/` | Layer catalog JSON — `?app_labels=administrative,builtup` restricts which apps are queried |
| `/api/layers/<app>/<model>/geojson/` | GeoJSON for a vector model — optional `?bbox=minLng,minLat,maxLng,maxLat` (WGS84) and `?zoom=z` |
| `/api/layers/<app>/<model>/bounds/` | Bounding box as WGS84 `[[west, south], [east, north]]` |
| `/api/raster/<app>/<model>/tiles/` | TiTiler tile URL for a raster model |
| `/api/raster/<app>/<model>/info/` | Raster metadata |
| `/importer/` | File upload import |
| `/importer/external/` | External catalog import |
| `/watersupply/` | Water supply dashboard |
| `/urban_heat/` | Urban heat views |
| `/housing/` | Housing dashboard |
| `/weather/` | Weather data views |

## ✅ Testing

Tests use `PostGISTestRunner` (`DigitalTwin/test_runner.py`), which creates the test DB, installs PostGIS extensions, and patches Django's `prepare_database` to skip the superuser requirement.

```bash
python manage.py test --settings=DigitalTwin.settings_test --keepdb --noinput
python manage.py test importer --settings=DigitalTwin.settings_test --keepdb --noinput   # single app
```

Always pass `--keepdb`: without it Django drops the test database the runner prepared and recreates it without PostGIS, and migrations fail with `type "geometry" does not exist`.

## 📊 Performance

[`docs/PERFORMANCE.md`](docs/PERFORMANCE.md) is the performance review and tracks what is done: §0–§3 (measurement, the GeoJSON endpoint, the land-cover signal, importer batching) are implemented; the rest are proposals.

- With `QUERY_STATS=True`, every response carries a `Server-Timing` header — open DevTools → Network → Timing to see DB time and query count per API call.
- `python manage.py db_stats` lists the slowest statements from `pg_stat_statements` (it explains how to enable the extension if it's missing).
- The caches are in local process memory. With several worker processes, switch `CACHES` in `settings.py` to Redis so a data change invalidates every worker's copy.

## 📐 Key Conventions

- Spatial models always use `srid=settings.COORDINATE_SYSTEM`, never a hardcoded SRID.
- Computed fields are derived in `save()` — check existing patterns (`administrative/models.py`, `watersupply/signals.py`) first.
- FK `on_delete` on spatial/reference models uses `models.DO_NOTHING`.
- Population cascading uses `update()`, not `save()`, to avoid signal recursion.
- The GeoJSON API transforms to EPSG:4326 at query time — storage stays in RD New.
- Frontend JS lives in `core/static/js/` — never inline `<script>` blocks in templates.

## 🐛 Troubleshooting

| Symptom | Check |
|---|---|
| PROJ version mismatch on import | `python -c "import pyproj; print(pyproj.proj_version_str)"` vs `psql -c "SELECT PostGIS_PROJ_Version();"` — prefer `ST_AsGeoJSON` over GDAL reprojection if they diverge |
| Import fails despite a valid file | File encoding (UTF-8), geometry validity (`ST_IsValid`), SRID, required field mappings |
| Mapbox map is blank | `MAPBOX_ACCESS_TOKEN` set/valid; browser console + network tab for failed requests |
| Imported layer missing from map | Model's app is in `allowed_apps` (`core/utils.py`) and `INSTALLED_APPS`; `/api/layers/<app>/<model>/geojson/` returns valid GeoJSON |
| Map shows old data after a direct DB edit | Rows changed outside Django (SQL, `psql`) don't invalidate the GeoJSON cache — restart the server, or wait for the 2-minute expiry |
| Large layer shows only part of the city | Expected: layers with ≥ 5 000 features load by viewport; pan or zoom out to load more |
| Tests fail with `type "geometry" does not exist` | Rerun with `--keepdb` |
| Sentinel-2 (openEO) import fails / asks for credentials | `SENTINEL_CLIENT_ID`/`SECRET` set + server restarted; CDSE OAuth client still valid at [shapps.dataspace.copernicus.eu/dashboard](https://shapps.dataspace.copernicus.eu/dashboard); otherwise paste a personal client ID/secret into the UI panel (used once, not saved) |
