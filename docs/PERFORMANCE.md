# Performance Review: Database & Query Optimization

Status: §0–§3 are implemented (see the *Implemented* note under each). §4–§12 are still analysis only.
The findings come from reading the code. No profiling was done against a populated database, so the
impact ratings are estimates. Run the measurements in [§0](#0-measure-first) before and after each change to confirm them.

## Summary: where the time goes

| # | Area | Problem | Impact | Effort |
|---|------|---------|--------|--------|
| 1 | Map `model_geojson` | Returns the **whole table** every time, at full precision, reprojected per request, with a correlated sub-SELECT per FK per row | 🔴 High | M |
| 2 | Land-cover import | `physicalEnv/signals.py` re-runs an O(neighborhoods × polygons) PostGIS job **for every row saved** | 🔴 High | M |
| 3 | Importer | Row-by-row `update_or_create`, a transaction per feature, and a Python linear scan for the spatial parent | 🔴 High | M |
| 4 | Indicator dashboards | Every slider move re-runs ~25 queries (including several PostGIS intersections). Only the override changed | 🔴 High | S |
| 5 | Admin geometry round-trips | `adminUnit.geom` (a large MultiPolygon) is fetched into Python and then sent back as a query parameter 5–10× per request | 🟠 Med-High | S |
| 6 | Over-fetching geometry | Queries that need only `pk`/`currentPopulation` load full MultiPolygons, and raster rows load the whole raster | 🟠 Med-High | S |
| 7 | `available_layers` | `COUNT(*)` per model, and `objects.all()` on raster models loads the raster bytes | 🟠 Medium | S |
| 8 | Missing B-tree indexes | `year`, `is_active`, `date_time` and the `*Name` lookup columns have no indexes | 🟡 Medium | S |
| 9 | Connection / cache settings | No `CONN_MAX_AGE`, no `CACHES` | 🟡 Medium | XS |
| 10 | Raster stats | `ST_Clip` + `ST_SummaryStats` on untiled PostGIS rasters, with the geometry sent as WKT | 🟡 Medium | M |
| 11 | Population cascade | Redundant aggregates, a full-row load, and repeated City/Province recomputes | 🟢 Low-Med | S |
| 12 | GPU (CUDA) | Not a fix for the query problems above. Speeds up raster derivations (DSM → SVF → Tmrt), bulk zonal statistics and voxel simulations | 🔵 New capability | M–L |

Recommended order: **9 → 8 → 6 → 5 → 4 → 7 → 1 → 2/3 → 10 → 11.** The first five are small and low-risk. Items 1–3 give the biggest gains.

---

## 0. Measure first

```python
# settings.py (dev only) – log every SQL statement with its duration
LOGGING = {
    "version": 1,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "loggers": {"django.db.backends": {"level": "DEBUG", "handlers": ["console"]}},
}
```

- Install **django-debug-toolbar** or **django-silk** to see the query count and duration per view. Check `/watersupply/…`, `/api/layers/` and `/api/layers/<app>/<model>/geojson/` first.
- In PostgreSQL, enable `pg_stat_statements` and look at the top statements by `total_exec_time`.
- For any slow statement, run `EXPLAIN (ANALYZE, BUFFERS)`. A `Seq Scan` on a large table, or a `SubPlan` executed once per row, is the thing to fix.
- In tests, pin the query count with `self.assertNumQueries(n)` so regressions show up.

**Implemented.** `core/middleware.py::QueryStatsMiddleware` (on when `QUERY_STATS=true`, default = `DEBUG`) adds a
`Server-Timing` header (DB time + query count, shown in DevTools → Network → Timing) and `X-DB-Queries` to every
response, and logs each request on `crosstwin.querystats` (WARNING above `QUERY_STATS_SLOW_MS`, default 500).
`SQL_LOG=true` prints every statement (needs `DEBUG=true`). `python manage.py db_stats [--order mean] [--reset]`
lists the top `pg_stat_statements` entries, or explains how to enable the extension. No new dependencies.
`mainMap/tests.py` pins the GeoJSON endpoint at one query.

When `db` is much smaller than `total`, the time is in Python: profile the request with
`python tools/profile_requests.py "<url>" --runs 2` (cumulative and own-time tables; run 1 includes one-off
startup costs, run 2 is the steady state; `--save x.prof` for `snakeviz`). If the tables are full of
`importlib` rows, find the module with `python -X importtime -c "import django; django.setup(); import DigitalTwin.urls"`.
Doing this found 2–3 s of first-request time in top-level imports of scipy/rasterio/rio-cogeo (`weather/models.py`,
`core/signals.py`), pandas/geopandas (`importer/views.py`, `importer/utils.py`) and rio-tiler (`mainMap/styles/rasterStyles.py`),
plus 25 ms per admin-unit lookup spent rebuilding the WGS84 → RD New transformation. All are now imported or built
lazily; `/api/admin-unit/` went from 1963 → 761 ms cold and 33 → 8 ms warm.

**KNMI radar tiles** (`weather/views.py::wms_tile_proxy`). Measured through the proxy against the real
service: each tile costs one KNMI render, ≈0.5–0.6 s at a quiet moment and 2–3.4 s at a busy one, whatever
the tile size (256 px ≈ 550 ms, 512 px ≈ 600 ms), with the database at ~1 ms. So the number of requests is
what matters:
- WMS tiles are requested at 512 px (`WMS_TILE_SIZE` in `Config.js`): a quarter of the requests for the same screen.
- Tiles are cached in `CACHES["wms_tiles"]` (2 000 entries) instead of the default cache, for 24 h when the
  request has `TIME=` (a fixed frame never changes) and 5 min without; a cache hit takes ~4 ms.
- Responses carry `Cache-Control` (`immutable` for fixed frames), so the browser reuses tiles when scrubbing
  back or reloading.
- Upstream calls share one keep-alive `requests.Session` (small gain: the handshake is not the bottleneck) and
  wait for `Retry-After` (≤ 2 s) on a 429 instead of retrying straight into the rate limit.
- `Server-Timing` on each tile shows `cache;desc="hit|miss"` and `upstream;dur=` (the middleware now appends to
  a view's own `Server-Timing` instead of replacing it).

---

## 1. `model_geojson`: the map's main bottleneck

`mainMap/views.py:211-299`

Current behaviour:
- `SELECT … FROM "<table>"` has **no `WHERE`**. Every Building, Street and LandCoverVector row is serialised into a single JSON blob, whatever the viewport.
- `ST_Transform(geom, 4326)` runs on every row of every request.
- `ST_AsGeoJSON` defaults to 9 decimal places. In degrees that is sub-millimetre precision, which only makes the payload bigger.
- Each FK column becomes a correlated `(SELECT name FROM related WHERE pk = …)`, which runs as a SubPlan once per row per FK.
- No geometry simplification at low zoom.

Fixes, from quickest to most complete:

1. **Add a bbox filter.** The frontend already knows the viewport. Pass `?bbox=minx,miny,maxx,maxy` and filter with the index:
   ```sql
   WHERE "geom" && ST_Transform(ST_MakeEnvelope(%s,%s,%s,%s,4326), 28992)
   ```
   `&&` uses the GiST index that Django already creates (`spatial_index=True` is the default).
2. **Reduce precision and simplify:** use `ST_AsGeoJSON(ST_Transform(geom,4326), 6)`, which gives about 10 cm. For zoom levels below ~14, wrap the geometry in `ST_SimplifyPreserveTopology(geom, tolerance)`.
3. **Replace the correlated sub-SELECTs with `LEFT JOIN`s** built from the same `_display_field()` metadata. This lets the planner use a hash join.
4. **Cache the response.** Vector layers change only on import, so cache on `(key, bbox, zoom)` and invalidate from a `post_save`/`post_delete` receiver or an importer hook (see §9).
5. **Best option for large layers: vector tiles (MVT).** Add `/api/layers/<app>/<model>/tiles/{z}/{x}/{y}.pbf` using `ST_AsMVT` + `ST_AsMVTGeom`. Mapbox GL loads these natively, and each request touches only the rows in one tile. The same idea already serves rasters through TiTiler. For vectors, the options are a Django view or a dedicated server such as `pg_tileserv`/`martin`.

Optional: add a stored generated column with the 4326 geometry and its own GiST index, so the transform isn't repeated on every read:
```sql
ALTER TABLE builtup_building ADD COLUMN geom_4326 geometry GENERATED ALWAYS AS (ST_Transform(geom, 4326)) STORED;
CREATE INDEX ON builtup_building USING gist (geom_4326);
```

`layer_bounds` (`mainMap/views.py:685`) runs `Extent()` over the whole table. `ST_EstimatedExtent('<table>','geom')` returns the answer from planner statistics almost instantly and is accurate enough for a zoom-to-layer.

**Implemented** (fixes 1–4; MVT tiles and the generated 4326 column are not done):
- `model_geojson` takes optional `?bbox=minLng,minLat,maxLng,maxLat&zoom=z`, filters with `&&`, emits 6 decimals,
  simplifies lines/polygons to ~1 px below zoom 14, joins FK names with `LEFT JOIN`, and returns PostgreSQL's JSON
  text directly instead of parsing and re-serialising it.
- Responses are cached in the `geojson` cache (`CACHES` in settings, local memory, 64 entries, bodies ≤ 8 MB, 2 min — short because edits made outside Django don't invalidate it)
  under a per-model version from `core/cache.py`. `core/signals.py` bumps the version on every `post_save`/`post_delete`
  of a vector model; the writers that bypass signals (the population cascade, the urban-area `UPDATE`, the importer's
  bulk path) bump it themselves. With several worker processes, move `CACHES` to Redis (§9) so invalidation reaches all of them.
- The map (`Layers.js`) loads layers with ≥ `VIEWPORT_LOAD_MIN_FEATURES` (5 000) features by viewport and reloads them
  after each pan/zoom, aborting superseded requests. Administrative layers still load whole.
- `layer_bounds` now returns WGS84 (it returned RD New metres) and uses `ST_EstimatedExtent` only for tables with
  ≥ 100 000 rows: the estimate is as old as the last `ANALYZE`, and was visibly wrong on smaller, recently changed tables.

---

## 2. Land-cover signal: quadratic cost during imports

`physicalEnv/signals.py:30-97`. The file's own comment at line 87 already notes the problem.

On every `LandCoverVector` save or delete, the signal:
- loops over **all** Neighborhoods of the city in Python (loading each full geometry),
- runs one `Intersection`/`Area` aggregate per neighborhood,
- runs one `UPDATE` per neighborhood,
- then re-runs the City and Province cascade **once per district**, although the city and province are the same each time.

Importing N polygons for a city with M neighborhoods costs about **N × M PostGIS intersections**.

Fixes:
1. **Suspend the receiver during bulk imports** and recompute once per affected city at the end:
   ```python
   # physicalEnv/signals.py
   from contextlib import contextmanager
   _suspended = threading.local()

   @contextmanager
   def deferred_urban_area():
       _suspended.cities = set()
       try:
           yield
       finally:
           cities, _suspended.cities = _suspended.cities, None
           for city_id in cities:
               _recompute_neighborhood_urban_area(city_id)

   def landcover_changed(sender, instance, **kwargs):
       if getattr(_suspended, "cities", None) is not None:
           _suspended.cities.add(instance.city_id); return
       ...
   ```
2. **Replace the per-neighborhood loop with a single set-based `UPDATE`:**
   ```sql
   UPDATE administrative_neighborhood n
   SET urban_area = COALESCE(s.area, 0) / 1e6, last_updated = now()
   FROM administrative_neighborhood n2
   LEFT JOIN LATERAL (
       SELECT SUM(ST_Area(ST_Intersection(l.geom, n2.geom))) AS area
       FROM physicalenv_landcovervector l
       JOIN physicalenv_landcoverclasses c ON c.id = l.land_cover_type_id
       WHERE l.city_id = %(city)s AND l.year = %(year)s
         AND l.geom && n2.geom AND ST_Intersects(l.geom, n2.geom)
         AND (c.class_name ILIKE '%%urban fabric%%' OR c.class_name ILIKE '%%road%%' OR …)
   ) s ON true
   WHERE n.id = n2.id AND n2.district_id IN (SELECT id FROM administrative_district WHERE city_id = %(city)s);
   ```
   After the update, recompute each district once, then the city **once** and the province **once**, instead of once per district.
3. `ST_Intersection` is expensive on large, detailed polygons. When a land-cover polygon is fully inside the neighborhood (`ST_Within`), use `ST_Area(l.geom)` directly and only clip the polygons that cross the boundary:
   `CASE WHEN ST_Within(l.geom, n.geom) THEN ST_Area(l.geom) ELSE ST_Area(ST_Intersection(l.geom, n.geom)) END`.

**Implemented** (all three). `physicalEnv/signals.py` recomputes a city with one `UPDATE … FROM … RETURNING` using the
`ST_Within` shortcut, then cascades each district once and the city and province once. `deferred_urban_area()` and
`schedule_urban_area_recompute()` postpone it to the end of a block; `administrative/signals.py::deferred_population_cascade()`
does the same for the population cascade.

---

## 3. Importer throughput

`importer/external_data.py:580-775` and `importer/views.py:397-733`

Current behaviour:
- A `transaction.atomic()` per feature, plus a nested one around `update_or_create`. That is two savepoints per row.
- `update_or_create` is a `SELECT … FOR UPDATE` followed by an `INSERT` or `UPDATE`, one row at a time, and each row fires `save()` and every `post_save` receiver (population cascade, land-cover recompute, watersupply signals).
- **Spatial FK resolution** (line 711) is `next(p for p in parent_objects if p.geom.contains(centroid))`, a Python linear scan with unprepared GEOS geometries. For 10 000 features against about 350 municipalities, that is up to 3.5 M full point-in-polygon tests.
- `ParentModel.objects.all()` (line 586) loads every column of the parent rows, when only `pk` and `geom` are needed.

Fixes:
1. **Use prepared geometries**, a small change that is often 10–100× faster:
   ```python
   parent_objects = list(ParentModel.objects.only("pk", "geom", *extra_attrs))
   prepared = [(p, p.geom.prepared) for p in parent_objects]
   parent = next((p for p, pg in prepared if pg.contains(centroid)), None)
   ```
   Add a bbox pre-check (`p.geom.extent`), or build a `shapely.STRtree` once per batch.
2. **Batch the writes.** Collect instances and call `Model.objects.bulk_create(objs, batch_size=1000, update_conflicts=True, unique_fields=[…], update_fields=[…])` (Django ≥ 4.1, PostgreSQL `ON CONFLICT`). This skips `save()` and signals. That makes it fast, but any `save()`-computed fields (e.g. `area_km2`) must then be computed before the insert or with a follow-up `UPDATE … SET area_km2 = ST_Area(geom)/1e6`. After the batch, run the cascades **once** (see §2 and §11).
3. **Resolve spatial FKs in SQL after a bulk insert**, which avoids the per-row lookup entirely:
   ```sql
   UPDATE physicalenv_landcovervector l SET city_id = c.id
   FROM administrative_city c
   WHERE l.city_id IS NULL AND ST_Contains(c.geom, ST_PointOnSurface(l.geom));
   ```
   `ST_PointOnSurface` is guaranteed to lie inside the polygon, unlike `centroid`, which also removes the boundary fallback.
4. Use a single transaction for the whole batch, with a savepoint only when you need to skip one bad feature. For very large loads, `COPY` into a staging table and `INSERT … SELECT` is faster again.

**Implemented** in `importer/batching.py` (fixes 1, 2 and 4; SQL-side FK resolution and `COPY` are not done):
- `SpatialParentIndex`: parents loaded with `.only("pk", "geom", <area attr>)`, prepared geometries, bbox pre-check,
  probe point `point_on_surface` instead of the centroid. Used by the WFS/OGC and GML importers.
- `deferred_cascades()` wraps `_import_geojson_features` and `_generic_import`, so both cascades run once per affected parent.
- `BulkWriter` writes the models in `BULK_IMPORT_MODELS` (land cover, streets, the nature layers) 500 rows per
  `bulk_create`, with `ON CONFLICT DO UPDATE` for upserts. Rows are grouped by their set of mapped fields so a missing
  property never blanks a stored value; a failing batch is retried row by row. Models with `save()` logic (Building,
  the administrative hierarchy, GreenSpaces, …) keep the per-row path; a test guards the registry.
- `_generic_import` no longer prints per row, and does one lookup + a `save()` only when a value changed (it used to
  `update_or_create` every row and then count every update as "skipped").

Known gap, not fixed here: `_generic_import` builds `field_by_name` from geometry and raster fields only, so mapped
attribute columns (names, populations, FKs) are ignored by the file-upload importer.

---

## 4. Indicator dashboards: cache the DB layer

`watersupply/views.py:263-272`. `Housing/views.py` and `urban_heat/views.py` follow the same pattern.

`recalculate_indicators` is called on **every slider input** and calls `_get_adminUnit_data()`, which runs about 25 queries, including several `geom__intersects` scans and an `Intersection`/`Length` over `PipeNetwork`. Only `consumption_override` changed. The three-layer design already separates this cleanly: `_build_indicators()` is pure.

Fix: cache the output of `_get_adminUnit_data` keyed by its arguments.

```python
from django.core.cache import cache

def _cached_province_data(level, location, year, pop_scenario, pop_growth):
    key = f"ws:data:{level}:{location}:{year}:{pop_scenario}:{pop_growth}"
    data = cache.get(key)
    if data is None:
        data = _get_adminUnit_data(level, location, year, pop_scenario, pop_growth)
        cache.set(key, data, 600)
    return data
```

- The dict holds a model instance (`'province'`) with a large geometry. Store only the fields the templates use, e.g. `{'ProvinceName': …, 'currentPopulation': …}`, so the cached value stays small.
- Invalidate with a version key (`cache.incr("ws:version")`) bumped from the existing `watersupply/signals.py` receivers and after imports. Otherwise rely on a short TTL.
- Split the data so that population-independent parts (extraction, pipe length, NRW, water quality) are cached under a key **without** `pop_scenario`/`pop_growth`. Changing the population slider then only recomputes demand.
- Add a `debounce` in the domain JS (`hx-trigger="input changed delay:250ms"`) so a slider drag doesn't send dozens of requests.

---

## 5. Stop shipping admin geometries back and forth

Examples: `watersupply/calculations.py:45,109,136,316,331`, `watersupply/views.py:58-59`, `urban_heat/calculations.py:26,41,81,82,156,290,293,318`.

`adminUnit.geom` is a MultiPolygon with thousands of vertices. Each `filter(geom__intersects=adminUnit.geom)` serialises it to EWKB in Python, sends it over the wire and parses it again in PostGIS. `_get_adminUnit_data` does this about 8 times per request, and `get_thermal_indices` sends it as **WKT** text (the slowest format) about 10 times.

Fix: have PostGIS read the geometry directly from the admin table:

```python
from django.db.models import OuterRef, Subquery

def admin_geom(unit):
    return Subquery(type(unit).objects.filter(pk=unit.pk).values("geom")[:1])

ExtractionWater.objects.filter(is_active=True, geom__intersects=admin_geom(adminUnit))
```

For the raw raster SQL, pass `(table, pk)` and join:
`… FROM urban_heat_pet r, administrative_city a WHERE a.id = %s AND ST_Intersects(r.raster, a.geom)`.

Also:
- Several water functions scan `ExtractionWater` with the same `is_active=True, geom__intersects=…` filter (`calculate_total_extraction` is called **twice**, once directly and once via `calculate_supply_security`; `calculate_energy_consumption` and `calculate_co2_emission` repeat the scan). Merge them into **one** `.aggregate(extraction=Sum(...), energy=Sum(...), co2=Sum(...))`.
- `calculate_nrw` runs three queries on the same rows. Use a single aggregate with `filter=Q(type='A')` / `Q(type='R')`.
- `ImportedWater` is aggregated in both `_get_adminUnit_data` and `calculate_total_production_day`.
- `if not qs.exists(): …; qs.aggregate(...)` (e.g. `calculate_water_quality`, `calculate_coverage`, `calculate_drought_area`) makes two round trips. A single `aggregate` returns `None`s on empty input anyway.
- For point-in-polygon lookups on very large boundaries (provinces, municipalities), a pre-subdivided helper table (`ST_Subdivide(geom, 256)`) with its own GiST index makes `ST_Intersects`/`ST_Contains` much cheaper. This is the standard PostGIS trick for this case.

---

## 6. Don't load columns you don't use

Django loads every column by default, including multi-MB geometries and PostGIS rasters.

| Location | Loads | Needs |
|---|---|---|
| `administrative/population.py:156` `City.objects.filter(province=unit)` | full geom per city | `.only("pk", "currentPopulation")` |
| `administrative/admin_units.py:48` `resolve_admin_unit_at_point` (up to 4 queries) | full geom of the match | `.defer("geom")`, or a single `UNION ALL … LIMIT 1` query |
| `administrative/admin_units.py:62-64` `city_of` → `unit.district.city` | 2 extra queries, 2 geoms | `City.objects.defer("geom").get(district__neighborhood=unit)` or `select_related` |
| `administrative/signals.py:31` `model.objects.filter(pk=pk).first()` | full parent row | `.values("area_km2", parent_fk).first()` |
| `physicalEnv/signals.py:51` neighborhood loop | full row per neighborhood | handled by the set-based update in §2 |
| `mainMap/views.py:599,658` WMS/raster `objects.all()` | **entire raster column** | `.only("id", "cog_path", "name", …)` / `.defer("raster")` |
| `importer/external_data.py:586` parents | all columns | `.only("pk", "geom", <area attr>)` |

Where a geometry must reach the browser as a map outline, `ST_Simplify` it in SQL first.

---

## 7. `available_layers`

`mainMap/views.py:515-682`

- `model.objects.count()` per vector model is a full `COUNT(*)`, which is a sequential scan of each table. The UI shows this only as a number, so the planner estimate is enough:
  ```sql
  SELECT relname, reltuples::bigint FROM pg_class WHERE relname = ANY(%s)
  ```
  This is one query for all layers instead of one per model. Run `ANALYZE` after imports so the estimates stay current.
- Raster `model.objects.all()` loads the raster binaries just to read `cog_path`. Use `.only(...)`, or better `.values("id", "cog_path", "name", "opacity", "colormap", "rescale")`.
- `build_landcover_style_and_legend()` runs on every call.
- The response changes only when data is imported, so cache the whole payload per `app_labels` (e.g. 10 min, or invalidated by the importer). `_field_metadata()` is static per process and can be memoised with `functools.lru_cache`.

---

## 8. Missing B-tree indexes

Django indexes FKs and spatial fields automatically, but nothing else. There are about 39 `year`/`date_time`/`is_active` fields across the apps, and only `weather` defines indexes. Columns used in `filter()`/`order_by()` that deserve an index:

| Model(s) | Columns | Used by |
|---|---|---|
| `watersupply.*` with `year` (`TotalWaterDemand`, `ConsumptionCapita`, `NonRevenueWater`, `WaterTreatment`, `OPEX`, `AreaAffectedDrought`, …) | `(city, year)` or `(year)` | every `calculate_*(…, year)` |
| `NonRevenueWater` | `(year, type)` | `calculate_nrw` |
| `ExtractionWater`, `ImportedWater` | partial index `WHERE is_active` | every extraction aggregate |
| `urban_heat` raster models | `date_time` | `ORDER BY r.date_time DESC LIMIT 1` |
| `physicalEnv.LandCoverVector` | `(city, year)` | land-cover signal |
| `Housing.*` with `year` | `(…, year)` | housing calculations |
| `Province.ProvinceName`, `City.cityName`, `District.districtName`, `Neighborhood.neighborhoodName` | name | `resolve_admin_unit` on **every** dashboard request |

Example:
```python
class Meta:
    indexes = [
        models.Index(fields=["city", "year"]),
        models.Index(fields=["is_active"], condition=models.Q(is_active=True), name="extraction_active_idx"),
    ]
```

For `class_name__icontains` in the land-cover filter, a `pg_trgm` GIN index (`django.contrib.postgres.indexes.GinIndex(opclasses=["gin_trgm_ops"])`) turns `ILIKE '%…%'` into an index lookup. The `LandCoverClasses` table is small, so this matters less than the others.

Also check that PostGIS spatial indexes are actually used. Run `ANALYZE` after large imports; the planner needs statistics to pick the GiST index.

---

## 9. Settings: connection reuse and a cache backend

`DigitalTwin/settings.py:159-168`

```python
DATABASES = {
    "default": {
        ...,
        "CONN_MAX_AGE": 60,          # reuse connections instead of reconnecting per request
        "CONN_HEALTH_CHECKS": True,
        # Django 5.1+ with psycopg 3 (pip install "psycopg[pool]"):
        # "OPTIONS": {"pool": True},
    }
}

CACHES = {
    "default": {
        # Redis in production; LocMem is fine on a single-process dev server
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/1"),
    }
}
```

Opening a new PostgreSQL connection costs several ms, and the map page makes many parallel API calls. A cache backend is required for §1, §4 and §7.

PostgreSQL server settings also matter. The defaults are sized for a very small machine. For a PostGIS workload, raise `shared_buffers` (~25% of RAM), `work_mem` (32–64 MB, which helps `ST_Union`/sort/hash), `maintenance_work_mem` (index builds), `effective_cache_size` (~50–75% of RAM), and set `random_page_cost = 1.1` on SSD.

---

## 10. Raster statistics

`urban_heat/calculations.py:112-142`

- `ST_Clip(raster, geom)` + `ST_SummaryStats` is only fast when the raster is stored **tiled** (e.g. 256×256 per row, as `raster2pgsql -t 256x256` does) with the `ST_ConvexHull` GiST index. If each raster is one large row, every call clips the whole image.
- The COGs already exist for TiTiler. Computing stats from the COG is usually faster than from PostGIS, e.g. `rasterio.mask` with overviews, or TiTiler's `/cog/statistics` endpoint with a GeoJSON body. The raster rows in PostGIS then serve only as the source of truth.
- Pass the geometry by admin id (see §5), not as WKT.
- `ST_SummaryStats(rast, 1, exclude_nodata_value => true)` with a coarser overview is enough for dashboard min/mean/max.
- Cache the result per `(model, admin unit, latest date_time)`. The rasters only change on import.

---

## 11. Population cascade

`administrative/signals.py:13-60`

- Two aggregates on the same child set (`Sum` and then `Max('populationDate')`). Merge them into one `.aggregate(total=…, urban=…, date=Max(…))`.
- `model.objects.filter(pk=pk).first()` loads the full row (geometry included) just to read `area_km2` and the parent FK. Use `.values("area_km2", parent_fk)`.
- The per-level recompute could be a single SQL `UPDATE … FROM (SELECT … GROUP BY)`. Saving one Neighborhood then costs 3 statements instead of ~9.
- In bulk imports, disconnect these receivers (the same deferred pattern as §2) and recompute each affected parent once at the end. Otherwise every imported neighborhood triggers a full District → City → Province cascade, plus the `city_population_changed` fan-out into watersupply.

---

## 12. GPU (CUDA) acceleration

### Where a GPU helps, and where it doesn't

A GPU speeds up **compute-bound array work**: the same arithmetic over millions of cells. Most of what is slow in CrossTwin today is **I/O- and query-bound**: whole-table scans, row-by-row inserts, round trips, and missing indexes (§1–§11). PostgreSQL/PostGIS runs on the CPU, and a GPU does nothing for those problems. Fix §1–§11 first. Then move the numeric workloads below to CUDA.

| Workload | GPU helps? | Why |
|---|---|---|
| Dashboard `calculate_*` aggregates, GeoJSON, catalog | ❌ No | DB-bound; a few rows of arithmetic after a query |
| Population projection / what-if (`administrative/population.py`) | ❌ No | Tens of values; NumPy vectorisation is plenty |
| **Deriving rasters from rasters**: DSM → SVF → Tmrt/PET/UTCI, shadow casting, the DAG gaps in `urban_heat` | ✅ **Yes, 10–100×** | Per-pixel ray marching over millions of pixels × dozens of azimuths × hours of the day |
| **Zonal statistics** over many rasters/timesteps (§10), e.g. hourly UTCI for every neighborhood | ✅ Yes, at volume | For one raster and one city, copying to the GPU takes most of the time. Hundreds of timesteps × hundreds of zones is where it pays off |
| **Voxel simulations** (sky/green view, solar irradiance), see [VOXCITY.md](VOXCITY.md) | ✅ Yes | VoxCity ships a Taichi GPU simulator (`pip install "voxcity[gpu]"`) |
| Scenario sweeps (e.g. Monte-Carlo over consumption × population × tariff) | ⚠️ Only if ≥ 10⁶ scenarios | Vectorise with NumPy first; CuPy is a drop-in replacement when the arrays get large |
| Bulk polygon overlay (land cover × neighborhoods, §2) | ⚠️ Rarely | The set-based PostGIS `UPDATE` in §2 usually removes the bottleneck. GPU spatial joins (RAPIDS cuSpatial / cuDF) are Linux/WSL2-only, and RAPIDS has been winding cuSpatial down, so check its status before depending on it |

### Tooling

| Library | Use | Windows? |
|---|---|---|
| **CuPy** | NumPy-compatible arrays on the GPU (`cp.asarray`, `cp.nanmean`, masks, convolutions via `cupyx.scipy.ndimage`) | ✅ |
| **Numba CUDA** (`numba.cuda.jit`) | Custom kernels written in Python (ray marching, SVF, shadows) | ✅ |
| **Taichi** | Used internally by VoxCity's GPU simulator; CUDA/Vulkan/Metal backends | ✅ |
| RAPIDS (cuDF, cuSpatial) | GPU dataframes / spatial joins | ❌ Linux or WSL2 only |

The project is developed on Windows (`.venv\Scripts\Activate`), so **CuPy + Numba CUDA** are the practical choice. Install the CUDA Toolkit version matching your driver, then e.g. `pip install cupy-cuda12x numba`.

### Architecture: keep the GPU out of the request cycle

- **Never run CUDA work inside a Django view or a `post_save` signal.** Kernels on a city-sized raster take seconds to minutes, and the GPU context is per process. Run them in a **management command** (like `export_cogs`) or a background worker (Celery / django-q / RQ) on the machine with the GPU.
- **Input and output are COGs, not PostGIS rasters.** Read the source DEM/DSM from its `cog_path` with rasterio, compute on the GPU, write a COG with `rio-cogeo`, and create the model row with `cog_path` set. `core/signals.py::auto_export_cog` skips export when `cog_path` is already set, and TiTiler serves the result with no further changes.
- **Always keep a CPU fallback** so tests and machines without a GPU still work:
  ```python
  # core/gpu.py
  try:
      import cupy as xp
      from numba import cuda
      GPU = cuda.is_available()
  except ImportError:
      import numpy as xp
      GPU = False
  ```
- Set `measurement_method` / `source` on the output rows (e.g. `"CrossTwin SVF (GPU horizon method)"`) so GPU-derived rasters can be told apart from SOLWEIG imports.

### Example 1: Sky View Factor from the DSM (Numba CUDA)

This fills the `DSM -> SVF` edge in `core/DAG.dot`, currently unimplemented (see CLAUDE.md, *DAG Edge Coverage Gaps*). It uses the horizon-angle method. Each GPU thread handles one pixel, marches outward along `n_az` azimuths, keeps the steepest horizon angle γ on each, and computes `SVF = 1 − mean(sin²γ)`. This is the cosine-weighted form used for radiation. The visualisation form in Zakšek et al. (2011) uses `sin γ` instead.

```python
# urban_heat/gpu/svf.py
import math
import numpy as np
import rasterio
from numba import cuda

@cuda.jit
def _svf_kernel(dsm, cell, n_az, max_steps, out):
    i, j = cuda.grid(2)
    rows, cols = dsm.shape
    if i >= rows or j >= cols:
        return
    z0 = dsm[i, j]
    acc = 0.0
    for a in range(n_az):
        ang = 2.0 * math.pi * a / n_az
        di = -math.cos(ang)          # north-up raster: north = decreasing row
        dj = math.sin(ang)
        max_tan = 0.0
        for s in range(1, max_steps + 1):
            ii = int(math.floor(i + di * s + 0.5))
            jj = int(math.floor(j + dj * s + 0.5))
            if ii < 0 or jj < 0 or ii >= rows or jj >= cols:
                break
            t = (dsm[ii, jj] - z0) / (s * cell)
            if t > max_tan:
                max_tan = t
        acc += max_tan * max_tan / (1.0 + max_tan * max_tan)   # sin²(atan t)
    out[i, j] = 1.0 - acc / n_az


def compute_svf(dsm_cog_path, out_path, n_az=36, radius_m=200):
    with rasterio.open(dsm_cog_path) as src:
        dsm = src.read(1).astype(np.float32)
        profile = src.profile
        cell = abs(src.transform.a)
    d_dsm = cuda.to_device(dsm)
    d_out = cuda.device_array_like(d_dsm)
    threads = (16, 16)
    blocks = ((dsm.shape[0] + 15) // 16, (dsm.shape[1] + 15) // 16)
    _svf_kernel[blocks, threads](d_dsm, cell, n_az, int(radius_m / cell), d_out)
    svf = d_out.copy_to_host()
    profile.update(dtype="float32", count=1, nodata=None)
    with rasterio.open(out_path, "w", **profile) as dst:
        dst.write(svf, 1)
    return out_path    # then cog_translate(...) and SkyViewFactor.objects.create(cog_path=..., ...)
```

A 5 × 5 km tile at 0.5 m (AHN) is 10⁸ pixels. At 36 azimuths × 400 steps that is about 10¹² memory reads, a job of hours on a CPU and minutes on a mid-range GPU. For areas larger than GPU memory, process overlapping tiles with a halo of `radius_m` and crop the halo before writing. Before replacing SOLWEIG's SVF with this output, check it against SOLWEIG for a test tile.

The same pattern (one thread per pixel, loops over azimuths and sun positions) extends to **shadow masks per hour** (march toward the sun's azimuth, compare with the sun altitude). Those feed Tmrt. The full Tmrt/PET/UTCI chain also needs longwave fluxes and meteorology, so porting SOLWEIG is a separate, larger project.

### Example 2: GPU zonal statistics for many timesteps (CuPy)

```python
import cupy as cp
import rasterio
from rasterio.features import geometry_mask
from rasterio.windows import from_bounds

def zonal_mean_over_time(cog_paths, zone_geom):   # zone_geom in the rasters' CRS
    means = []
    for path in cog_paths:                          # e.g. 24 hourly UTCI COGs
        with rasterio.open(path) as src:
            win = from_bounds(*zone_geom.bounds, transform=src.transform)
            arr = src.read(1, window=win, masked=False).astype("float32")
            mask = geometry_mask([zone_geom.__geo_interface__], arr.shape,
                                 src.window_transform(win), invert=True)
        g = cp.asarray(arr)
        g[~cp.asarray(mask)] = cp.nan
        means.append(float(cp.nanmean(g)))
    return means
```

The per-file read is still CPU work, so this pays off only when the per-pixel work is substantial: many zones per raster, percentiles, or exceedance-hour counts. Stack the timesteps into one 3-D array (`cp.stack`) and reduce along axis 0 so the GPU transfer happens once.

### Measuring the gain

Time each kernel with `cupyx.profiler.benchmark` or with `cuda.synchronize()` around `time.perf_counter()`, and compare against the NumPy fallback on the same tile. Include the host↔device copy in the timing, since for small rasters it dominates.

---

## Checklist

- [x] §0 Query-stats middleware, `db_stats` command, pinned query count *(still to do on the server: enable `pg_stat_statements` and record a baseline)*
- [ ] §9 Set `CONN_MAX_AGE` and `CACHES`; tune `postgresql.conf`
- [ ] §8 Add B-tree indexes (one migration per app)
- [ ] §6 Add `.only()`/`.defer()` on the listed queries
- [ ] §5 Use `Subquery` for admin geometries; merge duplicate aggregates
- [ ] §4 Cache `_get_adminUnit_data` in water, housing and heat; debounce the sliders
- [ ] §7 Use `reltuples` counts, `.only()` for rasters, and a cached catalog
- [x] §1 Add bbox, precision, JOINs and caching to GeoJSON; viewport loading in the map
- [ ] §1 MVT tiles for large layers
- [x] §2/§3 Deferred signals, set-based urban-area update, prepared geometries, `bulk_create`
- [ ] §10 Compute raster stats from COGs or tiled rasters; cache them
- [ ] §11 Merge the aggregates in `_recompute_population`
- [ ] §12 Add `core/gpu.py` with a CPU fallback; add a GPU SVF management command; validate its output against SOLWEIG
- [ ] Prototype the VoxCity pipeline ([VOXCITY.md](VOXCITY.md))
