# 🌍 CrossTwin

[![Version](https://img.shields.io/badge/version-0.7.15-blue)](CITATION.cff)
[![License: CC BY-NC-SA 4.0](https://img.shields.io/badge/license-CC%20BY--NC--SA%204.0-lightgrey)](LICENSE)
[![Cite this software](https://img.shields.io/badge/cite-CITATION.cff-orange)](CITATION.cff)
[![ORCID](https://img.shields.io/badge/ORCID-0009--0005--0245--633X-A6CE39?logo=orcid&logoColor=white)](https://orcid.org/0009-0005-0245-633X)
[![Last commit](https://img.shields.io/github/last-commit/ivan-cardenas/CrossTwin)](https://github.com/ivan-cardenas/CrossTwin/commits/main)

[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Django 5.2](https://img.shields.io/badge/django-5.2-092E20?logo=django&logoColor=white)](https://www.djangoproject.com/)
[![PostgreSQL + PostGIS](https://img.shields.io/badge/PostgreSQL-PostGIS-4169E1?logo=postgresql&logoColor=white)](https://postgis.net/)
[![GDAL 3.11+](https://img.shields.io/badge/GDAL-3.11%2B-5CAE58?logo=osgeo&logoColor=white)](https://gdal.org/)
[![TiTiler / FastAPI](https://img.shields.io/badge/TiTiler-FastAPI-009688?logo=fastapi&logoColor=white)](https://developmentseed.org/titiler/)
[![Mapbox GL JS](https://img.shields.io/badge/Mapbox%20GL%20JS-000000?logo=mapbox&logoColor=white)](https://docs.mapbox.com/mapbox-gl-js/)
[![HTMX 1.9](https://img.shields.io/badge/htmx-1.9-3366CC?logo=htmx&logoColor=white)](https://htmx.org/)
[![Google Earth Engine](https://img.shields.io/badge/Google%20Earth%20Engine-4285F4?logo=googleearth&logoColor=white)](https://earthengine.google.com/)
[![CRS EPSG:28992](https://img.shields.io/badge/CRS-EPSG%3A28992%20RD%20New-red)](https://epsg.io/28992)
[![DPSIR](https://img.shields.io/badge/framework-DPSIR-8A2BE2)](core/DAG.dot)

A **Django-based digital twin platform** for Dutch geospatial urban data — water supply, urban heat, energy, housing, and nature. PostgreSQL/PostGIS handles spatial storage, Mapbox GL JS renders the map, and a separate TiTiler (FastAPI) service serves raster (COG) tiles.

The project follows the **DPSIR framework** (Driver → Pressure → State → Impact → Response) to model causal relationships between urban systems — see [`core/DAG.dot`](core/DAG.dot).

## 📌 Project Information

- **Domain**: Urban digital twin — water supply, urban heat, housing, energy, nature
- **Default CRS**: EPSG:28992 (Amersfoort / RD New), set via `COORDINATE_SYSTEM` in `.env`
- **Stack**: Django 5 · PostgreSQL/PostGIS · GDAL/GeoPandas · Mapbox GL JS · TiTiler (FastAPI) · HTMX + Tailwind

## 🔧 Requirements

- Python 3.12 or newer, on Windows, macOS or Linux
- GDAL/GEOS: on Windows they come with the `gdal` wheel that `uv sync` installs; on macOS and Linux install them from the system package manager (see below)
- PostgreSQL 16 or 17 with the `postgis` and `postgis_raster` extensions
- A Mapbox access token

Optional, only needed for specific External Data Import sources:
- `SENTINEL_CLIENT_ID` / `SENTINEL_CLIENT_SECRET` — Copernicus Data Space (openEO), for Sentinel-2 imports
- `KNMI_API_KEY` — KNMI Data Platform, for weather/WBGT imports
- `OVERPASS_URL` — another Overpass API instance for OpenStreetMap imports (default: the public overpass-api.de)
- `GEE_PROJECT_ID` — a Google Cloud project registered for Earth Engine, for GEE imports and the LST tool

## 📦 Installation

```bash
git clone https://github.com/ivan-cardenas/CrossTwin.git
cd CrossTwin

# Recommended: uv (https://docs.astral.sh/uv/)
uv sync                       # creates .venv and installs pyproject.toml + uv.lock
```

Run every command below through `uv run` (e.g. `uv run python manage.py migrate`): it uses the project's `.venv` without activating it, from any folder of the project, and first syncs it with `uv.lock`, so after a `git pull` that changed dependencies you never run against a stale environment. Activating `.venv` (`.venv\Scripts\Activate`, `source .venv/bin/activate`) and typing plain `python` still works, as long as you run `uv sync` after pulling.

Dependencies are declared in `pyproject.toml` and pinned in `uv.lock`. `uv sync` uses the Python version uv finds; pick another with `uv sync --python 3.13`. Add `--no-dev` to skip the Jupyter kernel (`ipykernel`).

<details>
<summary><b>🧰 GDAL, and installing without uv</b></summary>

**GDAL.** GeoDjango needs the GDAL and GEOS C libraries:

- **Windows**: nothing to install. `uv sync` installs [Christoph Gohlke's GDAL wheel](https://github.com/cgohlke/geospatial-wheels) for your Python version (3.12–3.15) and CPU (x64 or ARM64), which bundles the GDAL, GEOS and PROJ DLLs; `DigitalTwin/settings.py` finds them in the venv's `osgeo` folder. PyPI has no Windows wheel for GDAL, so `pyproject.toml` points uv straight at the GitHub release files (`[tool.uv.sources]`). 32-bit Python and Python 3.16+ have no wheel there and fall back to building GDAL from source.
- **macOS**: `brew install gdal`
- **Linux (Debian/Ubuntu)**: `sudo apt install gdal-bin libgdal-dev`

  On macOS and Linux the `gdal` Python package is not installed: Django loads the system library, and rasterio, pyogrio and pyproj bundle their own GDAL/PROJ in their wheels.

**Without uv.** Without uv, `python -m venv .venv` and `pip install -r requirements.txt` still work (activate `.venv` and drop the `uv run` prefix from the commands), with `requirements.txt` (`uv export --format requirements-txt --no-hashes` of `uv.lock`; its markers pick the GDAL wheel per Python version and CPU on Windows).

</details>

### 1. Install PostgreSQL + PostGIS

CrossTwin needs PostgreSQL (16 or 17) with the PostGIS extensions `postgis` and `postgis_raster`. Nothing in the code uses `postgis_topology`, `postgis_sfcgal` or pgRouting; `tools/check_postgres.py` only lists them as optional.

<details>
<summary><b>🪟 Windows</b></summary>

1. Install PostgreSQL with the EDB installer from [postgresql.org/download/windows](https://www.postgresql.org/download/windows/), or with winget:
   ```powershell
   winget install --id PostgreSQL.PostgreSQL.17 -e
   ```
   Note the password you set for the `postgres` superuser and keep the default port `5432`.
2. PostGIS is not on winget. At the end of the installer, launch **Stack Builder** (or later from the Start menu), pick your PostgreSQL server, and install **Spatial Extensions → PostGIS 3.x Bundle**. Alternatively, use the [OSGeo installer](https://download.osgeo.org/postgis/windows/).
3. Make sure the service is running: `net start postgresql-x64-17` (or Services → `postgresql-x64-17` → Start).
4. `psql` lives in `C:\Program Files\PostgreSQL\17\bin`; add it to `PATH` or use **SQL Shell (psql)** / pgAdmin from the Start menu.

</details>

<details>
<summary><b>🍎 macOS</b></summary>

- [Postgres.app](https://postgresapp.com/) (bundles PostGIS), or Homebrew:
  ```bash
  brew install postgresql@17 postgis
  brew services start postgresql@17
  ```

</details>

<details>
<summary><b>🐧 Linux (Debian/Ubuntu)</b></summary>

```bash
sudo apt install postgresql postgresql-17-postgis-3   # match your PostgreSQL major version
sudo systemctl enable --now postgresql
sudo -u postgres psql        # opens psql as the superuser
```

</details>

### 2–3. Create the database and the `.env` file

**Windows: double-click `setup_db.bat`** in the project folder. It does steps 2 and 3 for you (and optionally step 5), so you don't have to open psql or pgAdmin. It asks:

| Prompt | Default | Notes |
|---|---|---|
| PostgreSQL host / port | `localhost` / `5432` | |
| Admin (superuser) name + password | `postgres` | The password you set in the PostgreSQL installer; only used during setup, never saved |
| Database name | `crosstwin` | Lowercase letters, digits, `_` |
| Database user name + password | `crosstwin_user` | Password typed twice (hidden); goes into `.env` |
| Privileges | `1` Full | `1` Full (owner, can migrate) · `2` Read/write · `3` Read-only |
| Allow creating databases | Yes for Full | Needed to run the test suite |
| Mapbox token | *(blank)* | Optional; add it to `.env` later if you don't have one yet |

It then creates the user and database, creates the `postgis` and `postgis_raster` extensions, grants the privileges, and writes `.env` from `.env_template` with a generated `SECRET_KEY`. With Full privileges and an existing `.venv` (run `uv sync` first), it ends by offering step 5: an **empty** database (`migrate`) or the **example data** (`tools/example_db.py load`, then `migrate`).

<details>
<summary><b>⚙️ More about <code>setup_db.bat</code></b></summary>

- **Where is psql?** The script looks on `PATH`, then under `C:\Program Files\PostgreSQL\<version>\bin` (newest version first), and asks for the path if neither works.
- **Privilege levels:**
  - **1 Full**: the user owns the database and the `public` schema, so it can run migrations, imports and `tools/example_db.py load`. Use this for local development.
  - **2 Read/write**: can read and change data but not the schema; migrations must be run by an admin.
  - **3 Read-only**: `SELECT` only, e.g. for a viewer or dashboard account.
- **Running it again is safe:** an existing user or database is reused (you're asked first), and an existing `.env` is copied to `.env.backup-<timestamp>` before it is replaced.
- **Special characters in passwords** (`& | ^ % ! ' " \ $`) are fine: the `.bat` file only launches the PowerShell script embedded in the same file.

</details>

<details>
<summary><b>🐧 Manual: create the database and <code>.env</code> by hand (macOS / Linux, or without the script)</b></summary>

**Database.** Run this in `psql` (or pgAdmin's Query Tool) **as the `postgres` superuser** — `CREATE EXTENSION` for PostGIS needs superuser rights. Pick your own user name and password; they go into `.env` in the next step.

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
CREATE EXTENSION postgis_raster;
```

**`.env` file.** Copy the template to `.env` in the project root (next to `manage.py`) and fill in your values. `.env` is git-ignored, so your keys never get committed.

```bash
cp .env_template .env        # Windows: copy .env_template .env
```

The template contains:

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
GEE_PROJECT_ID=your-google-cloud-project-id
SENTINEL_CLIENT_ID=your-cdse-client-id
SENTINEL_CLIENT_SECRET=your-cdse-client-secret
KNMI_API_KEY=your-knmi-api-key
# OVERPASS_URL=https://overpass-api.de/api/interpreter  # OpenStreetMap imports

# Optional — performance measurement (see docs/PERFORMANCE.md §0)
# QUERY_STATS=True          # per-request query count + DB time (default: same as DEBUG)
# QUERY_STATS_SLOW_MS=500   # log requests slower than this as warnings
# SQL_LOG=False             # print every SQL statement (needs DEBUG=True)
```

</details>

<details>
<summary><b>🔑 Where each <code>.env</code> value comes from (Mapbox token, API keys, …)</b></summary>

| Variable | Required | How to get it |
|---|---|---|
| `SECRET_KEY` | yes | Any long random string. Generate one: `uv run python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"` |
| `DEBUG` | yes | `True` for local development, `False` in production |
| `DATABASE_NAME`, `DATABASE_USER`, `DATABASE_PASSWORD` | yes | The database, user and password you created in step 2 |
| `DATABASE_HOST`, `DATABASE_PORT` | yes | `localhost` / `5432` for a local install (the port you chose in the PostgreSQL installer) |
| `MAPBOX_ACCESS_TOKEN` | yes | Sign up at [mapbox.com](https://account.mapbox.com/auth/signup/), then **Account → Tokens**. The *Default public token* (`pk.…`) works; the free tier is enough for development |
| `TITILER_BASE_URL` | yes | `http://localhost:8001` — the port you start `uv run uvicorn tiler:app` on |
| `COORDINATE_SYSTEM` | yes | `28992` (Amersfoort / RD New) for Dutch data. Set it **before** the first `migrate`: geometry columns are created in this CRS |
| `GEE_PROJECT_ID` | for Earth Engine imports and the LST tool | Create a Google Cloud project and register it for Earth Engine at [code.earthengine.google.com/register](https://code.earthengine.google.com/register) (free for non-commercial/research use); use the project's ID. The first Earth Engine call opens a browser for Google sign-in and caches the token per machine (or run `earthengine authenticate` once) |
| `SENTINEL_CLIENT_ID`, `SENTINEL_CLIENT_SECRET` | for Sentinel-2 imports | Register at [dataspace.copernicus.eu](https://dataspace.copernicus.eu/), open the [Sentinel Hub dashboard](https://shapps.dataspace.copernicus.eu/dashboard/) → **User settings → OAuth clients → Create**. The secret is shown only once |
| `KNMI_API_KEY` | for KNMI weather/WBGT/radar imports | Register at the [KNMI Developer Portal](https://developer.dataplatform.knmi.nl/) and request an Open Data API key (KNMI also publishes a time-limited anonymous key there for testing) |
| `OVERPASS_URL` | no | Only to use another Overpass instance for OpenStreetMap imports; leave out to use the public overpass-api.de |
| `QUERY_STATS`, `QUERY_STATS_SLOW_MS`, `SQL_LOG` | no | Performance measurement flags, see `docs/PERFORMANCE.md` §0 |

</details>

### 4. Check the database connection

```bash
uv run python tools/check_postgres.py
```

It connects with the `DATABASE_*` values from `.env`, checks that PostGIS is installed and enabled, and tells you what to fix if not (the common cases are listed under **Running the Project** below).

### 5. Fill the database: empty, or with the example data

**Option A: empty database.** Create the tables, then import your own data through the importer (`/importer/`):

```bash
uv run python manage.py migrate
```

**Option B: example data.** The repository ships an example database in `example/crosstwin_example_data.zip`. Load it into the empty database of step 2 (instead of Option A's `migrate`):

```bash
uv run python tools/example_db.py load   # = example/crosstwin_example_data.zip
uv run python manage.py migrate          # applies migrations newer than the package, if any
```

It restores the tables and data, copies the raster COG files into `cogs/` and points each raster row at them. The database must be empty and already have the `postgis`/`postgis_raster` extensions. If a load fails halfway, drop and re-create the database before trying again.

**Then create a superuser** (users are not part of the example data). The superuser can log in at `/admin/` and is staff, so it can also edit layers on the map and run the LST/SVF tools.

```bash
uv run python manage.py createsuperuser
```

## ▶️ Running the Project

CrossTwin runs as **two servers**, in separate terminals:

```bash
uv run python manage.py runserver 8000
uv run uvicorn tiler:app --port 8001 --reload
```

Or run `start.bat` on Windows, which starts both. Visit `http://localhost:8000`.

`start.bat` first runs `uv run python tools/check_postgres.py` (you can run it on any OS). It connects with the `DATABASE_*` settings of `.env` and checks for the `postgis` and `postgis_raster` extensions. If something is missing it says what and how to fix it, and `start.bat` stops:

- **PostgreSQL not installed**: `winget install --id PostgreSQL.PostgreSQL.17 -e` on Windows (Homebrew / apt on macOS / Linux).
- **PostgreSQL installed but not running**: the `net start postgresql-x64-<version>` command for the service it finds.
- **PostGIS not installed**: PostGIS is not on winget; install the PostGIS bundle with Stack Builder (included with the PostgreSQL installer) or the [OSGeo installer](https://download.osgeo.org/postgis/windows/).
- **Extensions not created, wrong credentials, missing database**: the SQL or `.env` setting to fix.

## 📚 Reference

*Click a topic to expand it.*

<details>
<summary><b>📂 Project Structure</b></summary>

| 📁 Folder | 📝 Contains | Description |
|---|---|---|
| `DigitalTwin/` | `settings.py`, `urls.py`, `test_runner.py` | Django project config, env loading, caches, custom PostGIS test runner |
| `core/` | `utils.py`, `signals.py`, `cache.py`, `middleware.py`, `rasterOperations.py`, `DAG.dot`, `static/js/` | Model registry, layer-cache versions, query-stats middleware, raster→COG export pipeline, DPSIR causal graph, shared frontend JS |
| `mainMap/` | `views.py`, `urls.py`, `charts.py`, `styles/` | Interactive map view, layer catalog + GeoJSON API, map editing (code in `core/editing.py`, layers switched on in the Map settings panel, form rules in `core/editable_layers.toml`), Map settings panel (`settings_views.py`: editable layers, style overrides on top of `styles/`, `styles/overrides.py`), population dock charts; `styles/` holds every map style: vector layer styles (`layerStyles.py`), soil map colours (`soilStyles.py`), land-cover legend (`landCoverStyles.py`), raster colormaps (`rasterStyles.py`) |
| `importer/` | `views.py`, `views_external.py`, `external_catalog.py`, `external_data.py`, `batching.py` | File-upload import + external catalog import (PDOK, CBS, BIS Nederland, OpenStreetMap, Sentinel-2, GEE, KNMI, RIVM, Klimaateffectatlas); bulk writes and deferred cascades |
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

</details>

<details>
<summary><b>🏗️ Architecture</b></summary>

### Model registry (`core/utils.py`)

`build_model_registry()` scans a hardcoded list of domain apps and builds four registries:

- **`MODEL_REGISTRY`** — every model from the allowed apps
- **`VECTOR_REGISTRY`** — models with a `GeometryField` (no `RasterField`)
- **`RASTER_REGISTRY`** — models with a `RasterField`
- **`WMS_REGISTRY`** — models whose registry key contains `"WMS"`

These drive the generic layer API, the map's layer catalog, and the importer's field-mapping UI. **Adding a domain app** means adding it to `allowed_apps` in `core/utils.py` *and* `INSTALLED_APPS` in `DigitalTwin/settings.py`.

### Signal-driven computation

- `administrative/signals.py` — cascades population/density Neighborhood → District → City → Province via `_recompute_population()`, using `update()` (not `save()`) to avoid signal recursion.
- `physicalEnv/signals.py` — when land cover changes, recomputes every neighborhood's `urban_area` in the city with one set-based SQL `UPDATE`, then cascades each parent once. A building drawn in the map editor (negative id) turns a 10 m buffer around it into urban fabric (`physicalEnv/landcover.py::urbanize_around`, DAG edge `New_Units -> LandCover`): the buffer is cut out of the overlapping land-cover polygons and inserted as one new polygon. The cut pieces are kept (`UrbanFabricCut`), so moving or deleting that building gives the land back (`release_ring`), and the editor's backup journals all those rows so Restore brings the original land cover back. The housing dashboard reports the pipeline's land take (greenfield vs infill hectares, `housing/calculations.py::calculate_pipeline_land_take`).
- `core/signals.py` — `post_save` on every `RASTER_REGISTRY` model auto-exports it to a COG (see *Raster Pipeline* below); `post_save`/`post_delete` on every vector model invalidates that layer's cached GeoJSON.
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

</details>

<details>
<summary><b>🧩 Domain Apps</b></summary>

| App | Covers |
|---|---|
| `administrative` | Province > City > District > Neighborhood; population projection |
| `physicalEnv` | Land cover (vector + raster), DEM, DSM, satellite imagery, surface materials |
| `watersupply` | Extraction, treatment, pipe networks, coverage, NRW, OPEX |
| `urban_heat` | UTCI, PET, MRT, LST, SVF, SUHII rasters; Nature-Based Solutions; per-neighborhood heat and shade (`NeighborhoodHeat`, Klimaateffectatlas) |
| `housing` | Supply/demand, mortgages, rentals, HPI, affordability stress; per-neighborhood social profile (`NeighborhoodSocialProfile`, Klimaateffectatlas) |
| `builtup` | Zoning, streets, parks, facilities, buildings (incl. canopy, facade shade and cloudburst depth from the Klimaateffectatlas), properties; per-neighborhood foundation and flood risk (`NeighborhoodClimateRisk`) |
| `nature`, `weather`, `Energy` | Additional domain data |
| `importer` | File-upload and external-catalog import pipelines |
| `mainMap` | Interactive map view and layer catalog API |
| `core` | Model registry, generic layer API, raster export pipeline, signals |

</details>

<details>
<summary><b>🔗 DPSIR Causal Network</b></summary>

The full causal graph lives in [`core/DAG.dot`](core/DAG.dot) (Graphviz). Each domain's `calculations.py` documents which edges its functions implement:

```python
# DAG edges: Central_Bank -> Mortgage
```

**Of the 103 edges in the graph, only 31 are backed by real derivation logic** (a `save()` or `calculations.py` function that reads the source field — not just a docstring claiming the edge). See [`TODO.md`](TODO.md) for the full per-app gap analysis and checklist before extending any dashboard's calculations.

</details>

<details>
<summary><b>📥 Importer System</b></summary>

Two paths, both under `/importer/`:

1. **File upload** — upload GeoJSON or a zipped Shapefile, map source fields to any registered model, preview, then import inside DB savepoints. *Known gap: only geometry and upsert-key columns are imported today; other mapped attribute columns are ignored.*
2. **External catalog** — catalog-driven import:

| Source | Provides | Auth |
|---|---|---|
| PDOK | Admin boundaries, BAG buildings, roads, water, elevation, land cover, zoning plans (each zoning element with its HILUCS land use) | None |
| RIVM | Per-building energy labels → `builtup.Building` (import BAG buildings first) | None |
| Klimaateffectatlas (WFS) | 21 of its 68 climate-effect layers: foundation and flood risk, heat and shade, social vulnerability per neighborhood; canopy, facade shade and cloudburst depth onto existing BAG buildings; water boards, drought-sensitive nature, climate buffers. Mapping, graph and the 47 layers not imported: [`docs/KEA_WFS_MAPPING.md`](docs/KEA_WFS_MAPPING.md) | None |
| CBS | National statistics via OData, incl. population forecasts | None |
| BIS Nederland (bodemdata.nl) | Soil map 1:50 000 (WFS) → `SoilType`/`SoilArea` with SCS soil group, drawn in the colours of the BRO Bodemkaart legend; groundwater depth GHG/GLG (WCS, 50 m) → `GroundwaterDepth` | None |
| OpenStreetMap (Overpass API) | Parks → `builtup.Park`, water bodies → `nature.WaterBodies`, amenities (nodes only) → `builtup.Facility`, trees → `nature.Tree` | None (`OVERPASS_URL` optional) |
| Sentinel-2 | Land cover + NDVI/NDWI/moisture/true-color via openEO | `SENTINEL_CLIENT_ID`/`SECRET`, else UI prompt |
| KNMI Data Platform | Weather observations (e.g. WBGT), precipitation radar forecast (WMS) | Server-side `KNMI_API_KEY` |
| Google Earth Engine | Arbitrary GEE assets, exported as GeoTIFF | Service-account JSON pasted per import |

For districts/neighborhoods, the import map picks the area of interest from the parent city/district (`bbox_from` in the catalog).

Large imports are batched (`importer/batching.py`): spatial parents (the city a polygon lies in, …) are found with prepared geometries, and models without their own `save()` logic — land cover, streets, facilities, soil polygons, the nature layers and trees — are written 500 rows at a time with `bulk_create` / `INSERT … ON CONFLICT`. Models with `save()` logic (buildings, the administrative hierarchy) are still saved row by row.

</details>

<details>
<summary><b>🛰️ Raster Pipeline</b></summary>

Every `RASTER_REGISTRY` model auto-exports to a tile-servable COG on save:

1. PostGIS raster → `ST_AsGDALRaster` → temp GeoTIFF
2. Reproject to EPSG:4326 via `rasterio`
3. Convert to COG via `rio-cogeo`
4. Store under `cogs/<app_label>/`
5. TiTiler serves tiles from that path

Raster models need a `cog_path` field to participate. Bulk-export with:

```bash
uv run python manage.py export_cogs
```

</details>

<details>
<summary><b>🔌 API Routes</b></summary>

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

</details>

<details>
<summary><b>✅ Testing</b></summary>

Tests use `PostGISTestRunner` (`DigitalTwin/test_runner.py`), which creates the test DB, installs PostGIS extensions, and patches Django's `prepare_database` to skip the superuser requirement.

```bash
uv run python manage.py test --settings=DigitalTwin.settings_test --keepdb --noinput
uv run python manage.py test importer --settings=DigitalTwin.settings_test --keepdb --noinput   # single app
```

Always pass `--keepdb`: without it Django drops the test database the runner prepared and recreates it without PostGIS, and migrations fail with `type "geometry" does not exist`.

</details>

<!-- <details>
<summary><b>📊 Performance</b></summary>

[`docs/PERFORMANCE.md`](docs/PERFORMANCE.md) is the performance review and tracks what is done: §0–§3 (measurement, the GeoJSON endpoint, the land-cover signal, importer batching) are implemented; the rest are proposals.

- With `QUERY_STATS=True`, every response carries a `Server-Timing` header — open DevTools → Network → Timing to see DB time and query count per API call.
- `uv run python manage.py db_stats` lists the slowest statements from `pg_stat_statements` (it explains how to enable the extension if it's missing).
- The caches are in local process memory. With several worker processes, switch `CACHES` in `settings.py` to Redis so a data change invalidates every worker's copy.

</details> -->

<details>
<summary><b>📐 Key Conventions</b></summary>

- Spatial models always use `srid=settings.COORDINATE_SYSTEM`, never a hardcoded SRID.
- Computed fields are derived in `save()` — check existing patterns (`administrative/models.py`, `watersupply/signals.py`) first.
- FK `on_delete` on spatial/reference models uses `models.DO_NOTHING`.
- Population cascading uses `update()`, not `save()`, to avoid signal recursion.
- The GeoJSON API transforms to EPSG:4326 at query time — storage stays in RD New.
- Frontend JS lives in `core/static/js/` — never inline `<script>` blocks in templates.

</details>

<details>
<summary><b>🐛 Troubleshooting</b></summary>

| Symptom | Check |
|---|---|
| `setup_db.bat`: *psql.exe was not found* | PostgreSQL isn't installed, or is in a custom folder: enter the path to its `bin` folder when asked |
| `setup_db.bat`: *PostGIS is not installed on this server* | Install **Spatial Extensions → PostGIS 3.x Bundle** with Stack Builder (Start menu → PostgreSQL), then run the script again |
| `setup_db.bat`: *Could not connect* | PostgreSQL service running (`net start postgresql-x64-17`)? Correct admin password and port? |
| Django: `password authentication failed` | `DATABASE_*` in `.env` match the database user; re-run `setup_db.bat` and choose to set a new password |
| PROJ version mismatch on import | `uv run python -c "import pyproj; print(pyproj.proj_version_str)"` vs `psql -c "SELECT PostGIS_PROJ_Version();"` — prefer `ST_AsGeoJSON` over GDAL reprojection if they diverge |
| Import fails despite a valid file | File encoding (UTF-8), geometry validity (`ST_IsValid`), SRID, required field mappings |
| Mapbox map is blank | `MAPBOX_ACCESS_TOKEN` set/valid; browser console + network tab for failed requests |
| Imported layer missing from map | Model's app is in `allowed_apps` (`core/utils.py`) and `INSTALLED_APPS`; `/api/layers/<app>/<model>/geojson/` returns valid GeoJSON |
| Map shows old data after a direct DB edit | Rows changed outside Django (SQL, `psql`) don't invalidate the GeoJSON cache — restart the server, or wait for the 2-minute expiry |
| Large layer shows only part of the city | Expected: layers with ≥ 5 000 features load by viewport; pan or zoom out to load more |
| Tests fail with `type "geometry" does not exist` | Rerun with `--keepdb` |
| `Could not find the GDAL library` at startup | macOS/Linux: install the system GDAL (`brew install gdal`, `apt install gdal-bin libgdal-dev`). Windows: `uv sync` did not install `gdal` (check `.venv\Lib\site-packages\osgeo\gdal.dll`); usually a 32-bit or unsupported Python version |
| Sentinel-2 (openEO) import fails / asks for credentials | `SENTINEL_CLIENT_ID`/`SECRET` set + server restarted; CDSE OAuth client still valid at [shapps.dataspace.copernicus.eu/dashboard](https://shapps.dataspace.copernicus.eu/dashboard); otherwise paste a personal client ID/secret into the UI panel (used once, not saved) |

</details>
