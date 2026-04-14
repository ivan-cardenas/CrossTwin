# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CrossTwin is a Django-based **digital twin mapping platform** for geospatial urban data visualization. It uses PostGIS for spatial storage, Mapbox GL JS for interactive maps, and TiTiler (a separate FastAPI service) for raster tile serving.

**Stack**: Django 5.2 · PostGIS · Mapbox GL JS · HTMX · Tailwind CSS (CDN) · TiTiler/FastAPI

## Commands

### Running the Application

```bash
# Start both servers (Windows batch script — recommended)
./start.bat

# Or start individually:
python manage.py runserver          # Django on :8000
uvicorn tiler:app --port 8001 --reload  # TiTiler on :8001
```

### Database

```bash
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser
```

### Testing

```bash
python manage.py test               # All tests
python manage.py test importer      # Single app
coverage run --source='.' manage.py test && coverage report
```

## Architecture

### The Model Registry (core/utils.py)

This is the central pattern. On startup, `core/utils.py` auto-discovers all spatial models from allowed apps and populates three registries:

- `MODEL_REGISTRY` — all models (used by the importer)
- `VECTOR_REGISTRY` — models with vector geometry fields (served as GeoJSON)
- `RASTER_REGISTRY` — models with raster fields (served via TiTiler)

**Consequence**: any new model in an allowed app automatically appears in `/importer/upload/`, `/map/api/layers/`, and the raster tile API — no manual registration needed. To expose a new app's models, add it to the `allowed_apps` list in `core/utils.py`.

### Data Flow

```
File Upload → importer/views.py → Field Mapping → SRID Transform → PostGIS
                                                                        ↓
Mapbox GL JS ← GeoJSON (mainMap/views.py) ← model_geojson() ← ST_AsGeoJSON()
                   ↑
             TiTiler tiles (core/views.py proxies to :8001 for raster layers)
```

### Sector Apps

Each urban domain is a standalone Django app with the same structure:

```
urban_heat/   watersupply/   weather/   Energy/   housing/   builtup/   nature/
├── models.py       # Geometry-enabled models (raster or vector)
├── views.py        # HTMX indicator panel endpoints
├── calculations.py # Domain-specific computations
└── templates/      # Partial HTML for hx-get responses
```

`common/` holds the base geographic hierarchy: `Province → City → District → Neighborhood`, plus shared `LandCoverVector`, `LandCoverRaster`, `DigitalElevationModel`, `DigitalSurfaceModel`.

### Coordinate System

All geometry fields use **EPSG:28992** (Dutch RD New) by default (`srid=28992`). This is configurable via `.env` → `COORDINATE_SYSTEM`. The importer handles reprojection automatically on import.

### Frontend

No build step — Tailwind CSS runs as a CDN browser script. JS files in `common/static/js/` are loaded directly:

| File | Responsibility |
|------|---------------|
| `Config.js` | API endpoint constants, Mapbox token |
| `Map_init.js` | Mapbox map setup |
| `Layers.js` | Layer toggling and source management |
| `MapUI.js` | Toolbar and panel rendering |
| `Events.js` | User interaction delegation |

HTMX (`hx-get`, `hx-target`, `hx-swap`) is used for dynamically loading indicator panels from sector app views without full page reloads.

## Environment

Requires a `.env` file (not committed):

```env
SECRET_KEY=...
DEBUG=True
DATABASE_NAME=digitaltwin
DATABASE_USER=geodjango
DATABASE_PASSWORD=DTwin
DATABASE_HOST=localhost
DATABASE_PORT=5432
MAPBOX_ACCESS_TOKEN=pk...        # Required for map rendering
TITILER_BASE_URL=http://localhost:8001
COORDINATE_SYSTEM=28992
```

### Windows GDAL Setup

`DigitalTwin/settings.py` auto-configures GDAL/PROJ DLL paths for Windows by detecting the active venv's `osgeo` package. If spatial queries fail, check that GDAL version matches PostGIS (`SELECT PostGIS_PROJ_Version();`).

### Required PostGIS Extensions

```sql
CREATE EXTENSION postgis;
CREATE EXTENSION postgis_topology;
CREATE EXTENSION postgis_raster;
```

## Adding a New Sector

1. `python manage.py startapp my_sector`
2. Define models with geometry fields in `my_sector/models.py`
3. Add to `INSTALLED_APPS` in `DigitalTwin/settings.py`
4. Add to `allowed_apps` in `core/utils.py` to expose in registry
5. Run migrations — models auto-appear in importer and map layer list
