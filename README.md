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
| `DigitalTwin/` | `settings.py`, `urls.py`, `test_runner.py` | Django project config, env loading, custom PostGIS test runner |
| `core/` | `utils.py`, `signals.py`, `rasterOperations.py`, `DAG.dot`, `static/js/` | Model registry, raster→COG export pipeline, DPSIR causal graph, shared frontend JS |
| `mainMap/` | `views.py`, `urls.py`, `charts.py` | Interactive map view, layer catalog API, population dock charts |
| `importer/` | `views.py`, `views_external.py`, `external_catalog.py`, `external_data.py` | File-upload import + external catalog import (PDOK, CBS, Sentinel-2, GEE, KNMI) |
| `administrative/` | `models.py`, `population.py`, `signals.py` | Province > City > District > Neighborhood hierarchy, population projection |
| `watersupply/` | `models.py`, `calculations.py`, `views.py`, `signals.py` | Water infrastructure, indicator dashboard |
| `urban_heat/` | `models.py`, `calculations.py`, `views.py` | Thermal comfort rasters (UTCI, PET, MRT, LST, SVF), NBS |
| `housing/` | `models.py`, `calculations.py`, `views.py` | Supply/demand, mortgages, rentals, affordability |
| `builtup/` | `models.py` | Streets, parks, facilities, buildings, properties |
| `physicalEnv/`, `nature/`, `weather/`, `Energy/` | `models.py` | Land cover, DEM/DSM, weather, energy domain data |
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
- `core/signals.py` — `post_save` on every `RASTER_REGISTRY` model auto-exports it to a COG (see [Raster pipeline](#🛰️-raster-pipeline)).
- `watersupply/signals.py` — cascades population → `ConsumptionCapita` → `TotalWaterDemand` → `SupplySecurity`, and re-derives `OPEX`/`CoverageWaterSupply`/NRW indicators from their upstream inputs.

### Map frontend (`mainMap/`)

- `map_view` renders `Templates/mainMap.html` with the Mapbox token; `available_layers` returns the full layer catalog as JSON; `model_geojson` serves any registered vector model via raw SQL (`ST_AsGeoJSON(ST_Transform(..., 4326))`).
- `core/static/js/mainMap.js` holds page-level wiring (map init, right panel, year selector, guided tour). New map-page behavior belongs there, not in inline `<script>` blocks.

### Indicator dashboards (watersupply, housing, urban_heat)

Each follows the same three-layer pattern:

1. **`calculations.py`** — pure query functions, each documenting the DPSIR/DAG edges it implements.
2. **`views.py`** — `_get_province_data()` assembles calculations into a dict; `_build_indicators()` derives display-ready metrics with what-if overrides (`consumption_override`, `interest_rate_override`, …).
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

**Of the 102 edges in the graph, only 28 are backed by real derivation logic** (a `save()` or `calculations.py` function that reads the source field — not just a docstring claiming the edge). See [`TODO.md`](TODO.md) for the full per-app gap analysis and checklist before extending any dashboard's calculations.

## 📥 Importer System

Two paths, both under `/importer/`:

1. **File upload** — upload GeoJSON or a zipped Shapefile, map source fields to any registered model, preview, then import inside DB savepoints.
2. **External catalog** — catalog-driven import:

| Source | Provides | Auth |
|---|---|---|
| PDOK | Admin boundaries, BAG buildings, roads, water, elevation | None |
| RIVM | Per-building energy labels → `builtup.Building` (import BAG buildings first) | None |
| CBS | National statistics via OData, incl. population forecasts | None |
| Sentinel-2 | Land cover + NDVI/NDWI/moisture/true-color via openEO | `SENTINEL_CLIENT_ID`/`SECRET`, else UI prompt |
| KNMI Data Platform | Weather observations (e.g. WBGT) | Server-side `KNMI_API_KEY` |
| Google Earth Engine | Arbitrary GEE assets, exported as GeoTIFF | Service-account JSON pasted per import |

For districts/neighborhoods, the import map picks the area of interest from the parent city/district (`bbox_from` in the catalog).

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
| `/api/layers/<app>/<model>/geojson/` | GeoJSON for a vector model |
| `/api/layers/<app>/<model>/bounds/` | Bounding box extent |
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
python manage.py test --settings=DigitalTwin.settings_test
python manage.py test importer --settings=DigitalTwin.settings_test   # single app
```

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
| Sentinel-2 (openEO) import fails / asks for credentials | `SENTINEL_CLIENT_ID`/`SECRET` set + server restarted; CDSE OAuth client still valid at [shapps.dataspace.copernicus.eu/dashboard](https://shapps.dataspace.copernicus.eu/dashboard); otherwise paste a personal client ID/secret into the UI panel (used once, not saved) |
