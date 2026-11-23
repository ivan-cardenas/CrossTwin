
# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CrossTwin is a Django-based digital twin platform for geospatial urban data (water supply, urban heat, energy, housing, nature). It uses PostgreSQL/PostGIS for spatial storage, Mapbox GL JS for map rendering, and TiTiler (FastAPI) for raster tile serving.

The project focuses on **Dutch geospatial data** — the default CRS is EPSG:28992 (Amersfoort / RD New), configured via `COORDINATE_SYSTEM` in `.env`.

## Read before working on…

| Area | File |
|---|---|
| A domain app's models (`administrative`, `physicalEnv`, `watersupply`, `urban_heat`, `housing`, `builtup`, `nature`) | [docs/claude/domain-apps.md](../docs/claude/domain-apps.md) |
| Any DAG edge, `save()` equation, receiver or `chain.py` | [docs/claude/dag-contract.md](../docs/claude/dag-contract.md) (full contract) + [docs/DAG_COVERAGE.md](../docs/DAG_COVERAGE.md); `/dag-edge` skill |
| Signals, cascades, bulk writes | [docs/claude/signals.md](../docs/claude/signals.md) |
| Importer, external catalog, `BulkWriter` | [docs/claude/importer.md](../docs/claude/importer.md) |
| Map page, JS tools/cards, rasters/COGs, TiTiler | [docs/claude/map-frontend.md](../docs/claude/map-frontend.md) |
| Map editing, backup/restore | [docs/claude/map-editing.md](../docs/claude/map-editing.md) |
| URLs / endpoints | [docs/claude/api-routes.md](../docs/claude/api-routes.md) |
| `pyproject.toml`, GDAL wheels, solweig extra | [docs/claude/dependencies.md](../docs/claude/dependencies.md) |
| Other management commands and `tools/` scripts | [docs/claude/tools.md](../docs/claude/tools.md) |
| Open TODOs | [docs/claude/todos.md](../docs/claude/todos.md) |

## Common Commands

```bash
uv sync                      # install/update .venv from uv.lock (--extra solweig for thermal comfort)
uv add <pkg>                 # add a dependency (updates pyproject.toml and uv.lock)
setup_db.bat                 # first-time PostGIS DB + .env setup (Windows)

# Run everything through `uv run`
uv run python tools/check_postgres.py
uv run python manage.py runserver 8000
uv run uvicorn tiler:app --port 8001 --reload     # or start.bat for both

# Migrations: always generate with makemigrations, never hand-write a schema migration.
# For a data step: `makemigrations <app> --empty -n <name>` and add only the RunPython.
uv run python manage.py makemigrations
uv run python manage.py migrate

# Tests: always --keepdb (without it the test DB is recreated without PostGIS:
# "type geometry does not exist") and --noinput.
uv run python manage.py test --settings=DigitalTwin.settings_test --keepdb --noinput
uv run python manage.py test importer --settings=DigitalTwin.settings_test --keepdb --noinput
```

## Architecture (essentials)

- **Two servers**: Django project in `DigitalTwin/` (settings from `.env`); `tiler.py` is a separate FastAPI TiTiler app on port 8001, proxied via `TITILER_BASE_URL` (keep it on `127.0.0.1`, not `localhost`).
- **Model registry** (`core/utils.py::build_model_registry()`): scans the allowed apps (`administrative`, `physicalEnv`, `urbanHeat`, `watersupply`, `weather`, `builtup`, `Energy`, `housing`, `nature`) into `MODEL_REGISTRY`, `VECTOR_REGISTRY` (GeometryField), `RASTER_REGISTRY` (RasterField), `WMS_REGISTRY`. These power the generic API, layer catalog and importer. A new domain app goes into `allowed_apps` in `core/utils.py` **and** `INSTALLED_APPS`.
- **DPSIR DAG** (`core/DAG.dot`): calculations document the edges they implement (`# DAG edges: A -> B`, node names exactly as in `DAG.dot`). Check `docs/DAG_COVERAGE.md` before claiming an edge is (not) implemented, and update it with every edge change.
- **Signals**: raster `post_save` auto-exports COGs; vector writes bump the GeoJSON cache version — code writing vector rows with `update()`/`bulk_create` must call `bump_layer_version()` itself. Wrap bulk writes in `importer/batching.py::deferred_cascades()`.

### DAG edge contract (summary — full rules in docs/claude/dag-contract.md)

1. A stored node is a model; its derived fields are computed in its own `save()`, docstring lists `DAG edges: Source -> Target`.
2. Equations needed by both `save()` and the dashboard live once, as pure functions in `<app>/calculations/chain.py`; add a dashboard/stored parity test.
3. Edge `A -> B` = a receiver in `<app>/signals.py` on A that `_resave()`s the B rows (unique `dispatch_uid`, returns on `raw=True`, names its edge, connected in `apps.py::ready()`). One edge per receiver.
4. Failures never block the source save; missing inputs keep the stored value.
5. No loops; parent aggregations use `update()` (+ `bump_layer_version()` / a custom signal).
6. Cross-sector edges point one way: downstream imports upstream, never the reverse.
7. Bulk writes stay O(parents): refresh helpers honour a thread-local deferral registered in `deferred_cascades()`.
8. What-ifs never write: sliders call `chain.py` with overrides.
9. Records with a `year` use that year's baseline population.
10. Each edge gets tests + updates to `docs/functions_and_equations.tex` and `docs/DAG_COVERAGE.md`.

### Indicator Pattern (watersupply, housing, urban_heat, builtup)

1. **`calculations/indicators.py`** — pure query functions; each documents its DAG edges.
2. **`views.py`** — `_get_adminUnit_data()` assembles the data; `_build_indicators()` is pure and applies what-if overrides; views render templates or return JSON.
3. **Templates** — HTMX: a partial grid swapped on slider changes via `hx-get` to `recalculate_indicators`.

- `MOCK_DATA` dicts are fallbacks when the province isn't in the DB.
- The standalone dashboard and its side-panel partial (`<app>/partials/indicators_panel.html`) share the **same** markup and the **same** JS file (`core/static/js/indicators/<domain>.js`, an IIFE that must re-run safely after every `htmx:afterSwap`; expose re-invoked functions as globals). Standalone pages extend `Templates/indicators_base.html`.
- "?" help: `{% info_help "<domain>.<card>" %}` from `core/indicator_help.py`; update the entry when an equation changes.
- **No inline `<script>` blocks** in indicator templates or `mainMap.html`; JS goes in `core/static/js/`.

### App Layout

- Computation code in `<app>/calculations/` (`indicators.py`, `chain.py`, topic modules; no views or receivers), tests in `<app>/tests/test_<topic>.py`. Never back into the app root.
- `calculations/__init__.py` stays empty: import by full path (`from watersupply.calculations import chain`) and patch there in tests.

## Reproducibility

Results are cited in research, so every stored or displayed number must be reproducible:

- Deterministic pure functions; seed and store anything stochastic.
- New external sources / cited rules go in `importer/external_catalog.py` or `core/data_sources.py`; rerun `uv run python tools/data_sources.py`.
- Store the input source/version, parameters and method with the result row (`source`, `measurement_method`, or a dedicated field).
- Dependencies only via the committed `uv.lock`; identify time-varying external data by date/version.
- Thresholds/coefficients are named, cited module constants.
- Each equation has its entry in `docs/functions_and_equations.tex`; a test pins its result for a known input.

## Testing

`PostGISTestRunner` (`DigitalTwin/test_runner.py`) creates the test DB with PostGIS. Always `--settings=DigitalTwin.settings_test --keepdb`. Tests hitting the GeoJSON endpoint clear `core.cache.get_cache('geojson')` in `setUp`. Pin query counts with `assertNumQueries` on hot endpoints.

## Key Patterns to Follow

- **All app content is in English** (templates, JS strings, labels, legends, help text, messages, docs). Dutch only as data values or official names.
- All spatial models use `srid=settings.COORDINATE_SYSTEM` (EPSG:28992), not hardcoded SRIDs.
- Models with computed fields implement logic in `save()` — check existing patterns first.
- Use `models.DO_NOTHING` for FK `on_delete` in spatial/reference models.
- Population cascading uses `update()` not `save()` to prevent signal recursion.
- Raster models need a `cog_path` field for the COG auto-export pipeline.
- The GeoJSON API transforms to EPSG:4326 at query time via `ST_Transform`.
- No top-level imports of heavy libraries (numpy, scipy, pandas, geopandas, rasterio, rio-cogeo, rio-tiler, openeo, ee) in modules loaded at startup or by the URLconf; import inside the function. When mocking, patch where defined.
- Code must not `import osgeo` outside the Windows block in `settings.py`.
- Performance work is tracked in `docs/PERFORMANCE.md`.
- Frontend CSS uses Tailwind with crispy-tailwind for forms.
- Templates live in `Templates/` (capital T).

## graphify
- **graphify** (`.claude/skills/graphify/SKILL.md`) - any input to knowledge graph. Trigger: `/graphify`
When the user types `/graphify`, use the installed graphify skill or instructions before doing anything else.

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

Rules:
- For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
