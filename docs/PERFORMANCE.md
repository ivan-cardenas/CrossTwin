# Performance Review: Database & Query Optimization

Status: analysis only, nothing here is implemented yet. The findings come from reading the code.
No profiling was done against a populated database, so the impact ratings are estimates.
Run the measurements in [§0](#0-measure-first) before and after each change to confirm them.

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

---

## 4. Indicator dashboards: cache the DB layer

`watersupply/views.py:263-272`. `Housing/views.py` and `urban_heat/views.py` follow the same pattern.

`recalculate_indicators` is called on **every slider input** and calls `_get_province_data()`, which runs about 25 queries, including several `geom__intersects` scans and an `Intersection`/`Length` over `PipeNetwork`. Only `consumption_override` changed. The three-layer design already separates this cleanly: `_build_indicators()` is pure.

Fix: cache the output of `_get_province_data` keyed by its arguments.

```python
from django.core.cache import cache

def _cached_province_data(level, location, year, pop_scenario, pop_growth):
    key = f"ws:data:{level}:{location}:{year}:{pop_scenario}:{pop_growth}"
    data = cache.get(key)
    if data is None:
        data = _get_province_data(level, location, year, pop_scenario, pop_growth)
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

`adminUnit.geom` is a MultiPolygon with thousands of vertices. Each `filter(geom__intersects=adminUnit.geom)` serialises it to EWKB in Python, sends it over the wire and parses it again in PostGIS. `_get_province_data` does this about 8 times per request, and `get_thermal_indices` sends it as **WKT** text (the slowest format) about 10 times.

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
- `ImportedWater` is aggregated in both `_get_province_data` and `calculate_total_production_day`.
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

## Checklist

- [ ] §0 Install debug-toolbar/silk and `pg_stat_statements`; record baseline query counts and times
- [ ] §9 Set `CONN_MAX_AGE` and `CACHES`; tune `postgresql.conf`
- [ ] §8 Add B-tree indexes (one migration per app)
- [ ] §6 Add `.only()`/`.defer()` on the listed queries
- [ ] §5 Use `Subquery` for admin geometries; merge duplicate aggregates
- [ ] §4 Cache `_get_province_data` in water, housing and heat; debounce the sliders
- [ ] §7 Use `reltuples` counts, `.only()` for rasters, and a cached catalog
- [ ] §1 Add bbox, precision, JOINs and caching to GeoJSON; then MVT tiles for large layers
- [ ] §2/§3 Deferred signals, set-based urban-area update, prepared geometries, `bulk_create`
- [ ] §10 Compute raster stats from COGs or tiled rasters; cache them
- [ ] §11 Merge the aggregates in `_recompute_population`
