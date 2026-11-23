<!-- Moved verbatim from .claude/CLAUDE.md on 2026-11-23. CLAUDE.md points here. -->

# Commands and tools

Less frequent commands (the everyday ones stay in `.claude/CLAUDE.md`).

```bash
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
