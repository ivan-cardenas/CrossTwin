# CrossTwin: A DPSIR-Structured Urban Digital Twin for Integrated Geospatial Analysis of Dutch Cities

**Draft — for review and completion**

---

## Abstract

Urban digital twins (UDTs) are increasingly proposed as decision-support tools for city planners and policymakers, yet most implementations remain siloed within a single domain (e.g., energy or transport) and lack explicit causal structure linking urban drivers to policy responses. This paper presents CrossTwin, an open-source urban digital twin platform built on a Driver–Pressure–State–Impact–Response (DPSIR) causal network, integrating geospatial data across five urban systems: water supply, urban heat, energy, housing, and nature. CrossTwin is implemented as a Django/PostGIS web application backed by a PostgreSQL spatial database, a TiTiler raster tile server, and a Mapbox GL JS map frontend. A model registry system dynamically exposes all spatial models as vector or raster API endpoints, enabling a generic import pipeline from authoritative Dutch open data sources (PDOK, CBS, Sentinel-2, Google Earth Engine). We describe the system architecture, the DPSIR causal graph and its current implementation coverage, the indicator computation pattern, and the interactive map and dashboard interfaces. We discuss open gaps in the causal model, limitations of the current implementation, and directions for future work.

---

## 1. Introduction

Cities face compound and interacting stresses: demographic growth, climate-induced heat extremes, ageing water infrastructure, housing affordability crises, and biodiversity loss. Addressing these challenges requires analytical tools that cut across sectoral boundaries and make the causal dependencies between urban systems explicit to planners and decision-makers. Urban digital twins — real-time or near-real-time virtual representations of a city linked to sensor data and simulation models — have emerged as a candidate framework for such integration [CITATION].

However, most deployed UDTs are domain-specific: energy UDTs model building consumption but not how affordability stress affects payment rates; water UDTs model pipe losses but not how land cover changes alter recharge. The cross-domain causal structure — who drives what pressure on which state variable, with what impact, and what response is available — is rarely formalised.

CrossTwin addresses this gap by:

1. Adopting the DPSIR framework as an explicit causal backbone, encoded as a directed acyclic graph (DAG) in `common/DAG.dot`
2. Implementing five domain apps (water supply, urban heat, energy, housing, nature) as Django apps sharing a common administrative hierarchy (Province > City > District > Neighbourhood)
3. Building a generic model registry that auto-discovers all spatial models and exposes them as API endpoints, eliminating per-model boilerplate
4. Providing a catalog-driven external data import pipeline covering authoritative Dutch open data (PDOK WFS/WCS/Atom, CBS OData, Sentinel-2 Process API, Google Earth Engine)
5. Computing domain indicators via pure query functions with HTMX-driven what-if dashboards for policy exploration

The focus area is the Netherlands, using EPSG:28992 (Amersfoort / RD New) as the native coordinate reference system.

---

## 2. Methods

Building CrossTwin meant confronting one recurring question at every layer of the stack: *when a sixth domain app arrives next year, how much of the platform has to be rewritten to accommodate it?* The answer we designed toward, throughout, was "as little as possible." That single constraint — new domains should be additive, not disruptive — explains most of the architectural choices below: a shared administrative backbone that every domain hangs off, a registry that discovers models by introspection rather than by a hand-maintained list, and a computation pattern that separates *what a domain measures* from *how it is displayed*. What follows is not a menu of independent design decisions; it is one decision (extensibility through reflection over the Django model layer) applied consistently to five different problems: serving APIs, exporting rasters, importing external data, computing indicators, and structuring the causal model itself.

### 2.1 System Architecture

The first choice was how to serve two fundamentally different kinds of geospatial data — vector features that can be queried and filtered in SQL, and continuous rasters that need to be sliced into map tiles on demand — without forcing one server to do both jobs badly. We split the platform into two processes on a single host:

- **Django application server** (port 8000) owns everything relational: the web UI, all vector/API endpoints, data ingestion, and indicator computation. It reads configuration from a `.env` file via `python-dotenv`, and on Windows it auto-discovers the GDAL/GEOS binaries bundled inside the project's own virtual environment (`osgeo` package) rather than requiring a separate system install — a deliberate accommodation for the mixed Windows/Linux development environments common in municipal GIS teams.
- **TiTiler raster tile server** (port 8001) is a lightweight FastAPI process whose only job is turning Cloud-Optimised GeoTIFFs (COGs) into XYZ tiles on request. Keeping it separate from Django means raster tiling — which is CPU- and I/O-bound in a way that a request/response web app is not — can be scaled or restarted independently. Django never touches raster pixels itself; it only proxies tile URLs to TiTiler through a `TITILER_BASE_URL` setting.

Underneath both sits PostgreSQL 15+ with PostGIS. A more subtle decision here concerns coordinate systems: because the platform's primary users are Dutch municipalities, all geometry is stored natively in EPSG:28992 (Amersfoort / RD New) — the CRS in which Dutch cadastral and elevation data is already published, so no reprojection is needed on import. The web, however, speaks EPSG:4326 (WGS84), so every API response reprojects at query time via PostGIS's `ST_Transform`. Storing in the "native" CRS and transforming only at the boundary keeps area and distance calculations (population density, pipe network length) accurate in the projection they were designed for, while still handing the browser coordinates it can plot directly.

On the frontend, **Mapbox GL JS** renders the map (3D terrain, vector layers, raster overlays) while **HTMX** handles the indicator dashboards. This pairing was chosen specifically to avoid a full JavaScript framework: the dashboards are mostly "change a slider, get new numbers back," a pattern HTMX solves by letting the *server* stay the source of truth for both data and markup, rather than duplicating that logic in a client-side framework.

### 2.2 Administrative Hierarchy and Population Cascade

Every domain in CrossTwin — water, heat, housing, energy, nature — ultimately reports its indicators "for this city" or "for this province." Rather than let each domain app maintain its own notion of geography, all five hang off a single shared hierarchy that mirrors how the Netherlands is actually administered:

```
Province → City (Gemeente) → District (Wijk) → Neighbourhood (Buurt)
```

This raised an immediate consistency problem: `Neighbourhood` is where population data actually gets updated (from CBS statistics or manual entry), but `City` and `Province` totals need to reflect the sum of their children at all times, not just when someone remembers to recalculate them. We solved this with a cascading Django signal in `common/signals.py`: whenever a `Neighbourhood` is saved or deleted, a `post_save`/`post_delete` receiver calls `_recompute_population()`, which sums `currentPopulation` across siblings and writes the aggregate onto the parent `District`; that write in turn fires a `district_changed` receiver that recomputes `City`, which fires `city_changed` and recomputes `Province`. The result is a self-propagating chain that keeps every level of the hierarchy consistent from a single edit at the leaf, without any view or admin action needing to know the cascade exists.

The one implementation detail worth calling out is *how* each level updates its parent: `_recompute_population()` deliberately writes with `QuerySet.update()` rather than calling `.save()` on the model instance. Using `.save()` would itself fire that model's own `post_save` signal — which is exactly the mechanism that triggers the *next* level's recompute — so in principle the cascade is supposed to fire signals going up. The risk is a different one: `.save()` re-serializes and re-validates the *entire* row, including fields unrelated to population, and can re-trigger *other* receivers listening on that same model for unrelated reasons, creating cycles that are hard to reason about once more receivers are added later. `update()` performs a targeted SQL `UPDATE` on exactly the four changed columns and — critically — does not fire `post_save` on the row being updated, so each cascade step is a deliberate, single hop (implemented as an explicit call to the next `_recompute_population()`, not an implicit re-trigger), never an accidental loop.

### 2.3 Model Registry

By the time a third domain app was added, it became clear that writing a bespoke `geojson/` view, a bounds endpoint, and a layer-catalog entry for every new model would not scale — five domains already meant dozens of spatial models, each needing identical plumbing. The fix was to stop writing that plumbing per model and instead have Django tell us, at runtime, what models exist and what kind of geometry they carry.

`build_model_registry()` in `core/utils.py` does exactly this: it iterates a short list of allowed app labels, asks Django's app registry for every model in each app, and records them in `MODEL_REGISTRY` keyed as `"app_label.ModelName"`. Three further registries are derived from the same introspection by inspecting each model's `_meta.get_fields()` for specific field types:

| Registry | Contents | How it is determined |
|---|---|---|
| `MODEL_REGISTRY` | All models from allowed apps | Django app config lookup |
| `VECTOR_REGISTRY` | Models with a `GeometryField`, no `RasterField` | Field-type introspection |
| `RASTER_REGISTRY` | Models with a `RasterField` | Field-type introspection |
| `WMS_REGISTRY` | Models whose registry key contains "WMS" | String match on key |

Because the registries are built from live model metadata rather than a maintained list, three generic, model-agnostic views can serve *any* current or future spatial model without modification:

- `/api/layers/` — the full layer catalog, with geometry type, record count, per-field metadata (label, unit, type), and a Mapbox GL JS style definition per model
- `/api/layers/<app>/<model>/geojson/` — a GeoJSON `FeatureCollection` for any vector model, built with raw SQL using `ST_AsGeoJSON(ST_Transform(...))`
- `/api/layers/<app>/<model>/bounds/` — the model's bounding box via PostGIS `ST_Extent`

The consequence is that adding a sixth domain app requires exactly two lines of configuration — an entry in `INSTALLED_APPS` and in the `allowed_apps` list — and zero new view code. The same reflection pattern reappears twice more below (§2.4, §2.7), which is why we treat it as the platform's central architectural idea rather than a one-off convenience.

### 2.4 Raster Pipeline

Raster layers (elevation, thermal comfort indices, land cover, satellite composites) pose a different problem than vector data: a browser cannot render a multi-megabyte GeoTIFF directly, and PostGIS's own raster storage is not something a map library can tile from. The pipeline exists to bridge database storage and tile serving through an intermediate, tile-friendly file format:

1. The raster is pulled out of its PostGIS `RasterField` via `ST_AsGDALRaster` into an in-memory GeoTIFF — no need to touch disk for the raw extract.
2. **rasterio** reprojects it from the storage CRS (EPSG:28992) to EPSG:4326 — the CRS both TiTiler and the map frontend expect. This step used to carry a latent bug worth recording here as a cautionary note: the reproject call once targeted `EPSG:3857` while every other part of the function (the computed transform, the output dimensions, and the file's own CRS tag) assumed 4326, so the file's *header* claimed WGS84 degrees while its *pixels* were actually warped into Web Mercator meters — a mismatch invisible until a consumer tried to place the raster on a map and found it in the wrong location. The fix was to make every step of the function agree on one target CRS explicitly, rather than relying on a parameter that could drift out of sync with its neighbours.
3. **rio-cogeo** converts the reprojected file into a Cloud-Optimised GeoTIFF, which pre-computes overview levels so a viewer zoomed out to province scale doesn't force TiTiler to decode a full-resolution 0.5 m elevation raster.
4. The COG is written to disk under `cogs/<app_label>/`, named from whatever provenance metadata the source model carries (satellite index, acquisition date, source id) so files on disk stay identifiable by what produced them rather than by an opaque database id alone.
5. TiTiler serves XYZ tiles directly from that COG path, applying colormap and rescale parameters per request.

Rather than requiring a developer to remember to run this pipeline after importing or computing a new raster, a `post_save` signal in `core/signals.py` wires it up automatically — and it does so by iterating `RASTER_REGISTRY` from §2.3, connecting the same `auto_export_cog` receiver to *every* raster model at import time. This is the registry pattern paying off a second time: a new raster model needs no explicit signal registration, because it is already discovered by the same reflection that powers the API layer. The receiver itself is guarded on two sides — it skips models flagged `SKIP_RASTER_DB_STORAGE` (whose source file never touches the Postgres raster column in the first place, and is COG'd directly from disk instead) and skips re-export once `cog_path` is already set — so the pipeline runs exactly once per raster, on save, without manual intervention.

### 2.5 DPSIR Causal Network

A platform that models five domains side by side risks becoming five unconnected dashboards wearing one skin. To make the *cross-domain* causal structure a first-class, inspectable artefact rather than something implicit in scattered code, we adopted the DPSIR framework (Driver–Pressure–State–Impact–Response) and encoded it as an explicit directed graph in `common/DAG.dot` (Graphviz DOT), independent of any single app's code. The graph currently holds **102 directed edges** spanning all five domains, chaining causal steps such as:

```
Population_Growth → Total_Population → Urbanization → LandCover
LandCover → Infiltration → AvailableFreshWater → Supply_Security
Supply_Security → Service_Time → User_Acceptance_WS → OPEX → Affordability_Stress
PET → NBS → Green_Area → Accessibility → Property → House_Price_Index
```

The graph on its own is only a diagram; the traceability comes from linking it back to code. Each `calculations.py` function documents which edges it implements via inline `# DAG edges: A -> B` comments, so a reviewer can, in principle, walk from any arrow in the DAG to the exact function that computes it — or discover, as our own audit found (§4.1), that many arrows have no such function at all. Making the causal model machine-readable rather than descriptive prose is what makes that gap countable instead of anecdotal.

### 2.6 Indicator Computation Pattern

Each domain dashboard (water supply, housing) needs to answer three separable questions: *what does the raw data say*, *what should the user see*, and *what happens if the user changes an assumption*. Collapsing all three into one view function tends to produce code that is hard to test and impossible to reuse for a different output (an API response versus an HTML partial). We instead split every dashboard into three layers with a strict one-way dependency:

1. **`calculations.py`** — pure Django ORM query functions with no side effects, each answering one narrow question (e.g., "what is total demand for this province") by aggregating directly from the database. Because they have no side effects, they compose freely and can be unit-tested without touching a view or a template.
2. **`views.py`** — `_get_province_data()` calls every relevant `calculations.py` function and assembles the results into one context dict; `_build_indicators()` then takes that raw dict and derives the display-ready metrics (percentages, trend labels, classification bands), while also accepting parametric overrides such as `consumption_override` or `interest_rate_override`. Overrides are threaded through as plain function arguments rather than mutated database state, which is what makes "what-if" exploration safe: a slider move never writes to the database, it only changes which number flows through an otherwise identical calculation.
3. **Templates**, wired through HTMX: moving a slider fires `hx-get` to a `recalculate_indicators` endpoint, which re-runs steps 1–2 with the new override and returns *only* the indicator-grid partial — not a full page — so the round trip stays visually instantaneous.

Because step 2 is a pure function of its inputs, the same `_build_indicators()` works identically whether the database is populated or empty: a `MOCK_DATA` dict stands in for real query results when no province data exists yet, letting frontend and dashboard-layout work proceed independently of data-loading work.

### 2.7 External Data Import Pipeline

Cross-domain analysis is only as good as the data behind it, and the platform's target users — Dutch municipalities — should not need to hand-curate GIS files before they can use it. The `importer/` app addresses this with two complementary paths, both converging on the same ingestion code so validation and upsert logic are written once.

**File upload** handles the general case: a user uploads a GeoJSON or Shapefile, maps its fields to any registered model through a field-mapping UI, previews the first N features, and imports with database savepoints so a bad row can be rolled back without discarding the whole batch. The field-mapping UI itself reuses the reflection idea from §2.3 a third time — `_get_model_spec()` derives which fields are required, which are optional, and which are geometry or foreign-key fields directly from the target Django model's own field definitions (nullability, defaults, field type), rather than from a hand-written per-model schema. A `MODEL_OVERRIDES` dict then fills the gaps introspection cannot infer, chiefly per-model upsert keys, so re-importing the same source file updates existing rows instead of duplicating them.

**Catalog-driven external import** handles the recurring case: known, authoritative Dutch sources that should be one click away rather than a manual download-then-upload round trip. An `EXTERNAL_DATA_CATALOG` list declares each available dataset:

| Source | Format | Example datasets |
|---|---|---|
| PDOK (Publieke Dienstverlening Op de Kaart) | WFS, WCS, Atom | Administrative boundaries, buildings, AHN elevation, land cover |
| CBS (Centraal Bureau voor de Statistiek) | OData | Housing stock, demographics |
| Sentinel-2 (Sentinel Hub Process API) | Raster (GeoTIFF) | NDVI, true colour, NDWI, moisture index |
| Google Earth Engine | Raster | Global surface water, forest cover, CHIRPS precipitation |

Each catalog entry declares `requires_bbox`, `requires_auth`, `requires_date_range`, and `draw_bbox` flags, which the import UI reads to decide what to ask the user for — for instance, showing a Mapbox bounding-box picker only for datasets that need one. One exception illustrates why this is declarative rather than hard-coded: the municipality dataset (`pdok_cities`) cannot use the normal "click an existing city on the map" selection, because importing cities is precisely how city records come to exist in the first place — so that entry instead falls back to manual rectangle-drawing. The `import_dataset()` dispatcher in `external_data.py` then handles the format-specific mechanics (WFS pagination, WCS coverage requests, Atom feed parsing, Sentinel Hub OAuth2, GEE service-account authentication) and, once data is fetched, hands off to the *same* file-upload import path described above — so a PDOK boundary and a hand-uploaded Shapefile are validated and upserted through identical code.

### 2.8 Map Frontend

The map (`mainMap/`) is where the registry pattern becomes visible to the end user: because `/api/layers/` already knows about every vector, raster, and WMS model in the system (§2.3), the frontend never needs a hard-coded layer list — it renders whatever the catalog currently reports. On top of that catalog, the map provides:

- A **3D Mapbox GL JS view** with configurable pitch, bearing, and basemap, so building extrusions and terrain are legible rather than a flat diagram.
- A **layer catalog panel** grouping all registered layers by domain app, with visibility toggles, live record counts, and colour swatches drawn from each layer's style definition.
- **Per-layer Mapbox GL JS styles**, defined server-side in a `LAYER_STYLES` dict in `mainMap/views.py` rather than in frontend code — this keeps styling co-located with the model it describes, and allows full `paint`/`layout` specifications (3D building extrusions via `fill-extrusion`, dashed pipe-network lines, data-driven colour expressions) to travel with the API response instead of being duplicated in JavaScript.
- **Popups** that format feature properties using the same field metadata the API already exposes (verbose name, unit parsed from the model's `help_text`, date formatting), with `Intl.NumberFormat` applied client-side for locale-aware thousands separators.
- **Tool-based filtering**, where a toolbar swaps the layer panel between thematic views (urban heat, water, green infrastructure, groundwater) by filtering the same underlying catalog rather than loading a different one.

---

## 3. Results

### 3.1 Domain Coverage

CrossTwin integrates models across five domain apps, with the following spatial layers registered in the vector and raster registries:

**Common (administrative)**
- Province, City, District, Neighbourhood (polygon hierarchy)
- LandCoverVector (classified polygons), DigitalElevationModel, DigitalSurfaceModel (rasters)

**Water Supply**
- UsersLocation (points), Watershed, PipeNetwork (lines), CoverageWaterSupply, AreaAffectedDrought
- Tabular: ConsumptionCapita, TotalWaterDemand, SupplySecurity, ExtractionWater, WaterTreatment, NonRevenueWater, OPEX, TotalWaterProduction

**Urban Heat**
- NatureBasedSolutionPolygon, NatureBasedSolutionPoint
- Rasters: MeanRadiantTemperature (MRT), UTCI, PET, SkyViewFactor (SVF), LandSurfaceTemperature (LST), SurfaceUrbanHeatIslandIntensity (SUHII)

**Built-up Environment**
- ZoningArea, Street (lines), Park, Facility (points), Building (polygons with 3D extrusion), Property (points)

**Housing**
- HousingProject (polygons)
- Tabular: HousingSupplyDemand, Mortgage, Rentals, HousePriceIndex, HousingAffordability

**Nature**
- ProtectedArea, WaterWays (lines), WaterBodies, Forests, GreenSpaces

**Weather / Energy**
- WeatherStation (points), EnergyEfficiencyLabels

### 3.2 Water Supply Indicators

The water supply dashboard computes and displays the following indicators for a selected province:

- **Consumption per capita** (L/person/day) vs. benchmark
- **Total water demand** (Mm³/yr) and demand growth trend
- **Supply security** (%) — ratio of available freshwater to total demand
- **Non-Revenue Water (NRW)** (%) and Infrastructure Leakage Index (ILI)
- **Metering coverage** (%) and collection ratio
- **OPEX recovery** (%) — revenue recovered vs. operational expenditure
- **Water quality compliance** — sampling acceptance rate
- **User affordability** (%) — tariff as share of median income

All indicators support what-if sliders (consumption override, NRW target) that recompute via HTMX without a page reload.

### 3.3 Housing Indicators

The housing dashboard computes:

- **Housing supply/demand balance** — new units vs. demand projections
- **Housing affordability index** — median income vs. mortgage + rent burden
- **Affordability stress level** — classified as low / moderate / high / severe
- **House Price Index** trend
- **Credit supply conditions** — loan-to-value and debt-service ratios
- **Vacancy rate** by building type

### 3.4 External Data Import Coverage

The catalog covers **50+ datasets** across four sources. Successful import has been verified for:
- Dutch administrative boundaries (Province, City, District, Neighbourhood) from PDOK Bestuurlijke Grenzen
- Energy efficiency labels (EnergyEfficiencyLabels) from PDOK RVO
- Buildings and streets from BAG (Basisregistraties Adressen en Gebouwen)
- AHN 0.5m DTM/DSM elevation rasters
- CBS housing stock lifecycle statistics

---

## 4. Discussion

### 4.1 DPSIR Coverage Gaps

- Of the **102 edges** in the DPSIR causal graph, only **28 are backed by real derivation logic** — a `save()` method or `calculations.py` function that actually reads the source field. The remaining 74 are either flat stored fields with no computation, or functions whose docstring claims a DAG edge the code does not implement.
- The entire urban heat computation chain (`DSM → SVF → Tmrt/PET → UTCI`) is unimplemented in code; these rasters are expected to be pre-computed externally by SOLWEIG and imported as flat fields. CrossTwin currently cannot derive them from inputs.
- No `Urbanization` model exists, leaving the `Urbanization → CityArea/Buildings/Streets/LandCover` subgraph homeless.
- Affordability stress (`HousingAffordability.save()`) computes from stored fields only; it does not pull from live `Mortgage`, `Rentals`, or watersupply tariff data, breaking the cross-domain linkage that DPSIR models.

### 4.2 Cross-Domain Integration Limitations

- The `Accessibility` model referenced in `Facilities/Streets/Green_Area → Accessibility → Property → House_Price_Index` does not exist; `Building.connectivity` (a ManyToMany to Facility) is the closest proxy but lacks an index calculation.
- `watersupply.OPEX.save()` aggregates extraction OPEX but references `extraction_volume_m3`, a field that does not exist on `ExtractionWater` — a latent bug that would silently zero out the OPEX calculation.
- `calculate_collection_ratio()` ignores `userAffordability_PCT` despite its docstring claiming the edge `User_Acceptance_WS → Collection_Ratio`; the function currently averages raw acceptance rate only.

### 4.3 Scalability and Performance

- The `/api/layers/<app>/<model>/geojson/` endpoint returns full FeatureCollections with no pagination, tile clipping, or simplification. For models with tens of thousands of features (e.g., buildings, energy labels), this will be slow and large.
- A vector tile approach (MVT via `ST_AsMVT`) or server-side clustering would significantly reduce payload size for dense point and polygon layers.
- The raster COG pipeline re-exports on every `post_save`, which is acceptable for small datasets but will become a bottleneck for large rasters (AHN, Sentinel-2).

### 4.4 What-If Analysis and Scenario Planning

- The current what-if overrides (consumption slider, interest rate slider) are ad-hoc parameters added per indicator function. A generalised scenario management system — allowing users to save, compare, and share named scenarios — would significantly increase decision-support utility.
- Time-series analysis is absent: most models store a single `year` field but the dashboards show only the latest record. Temporal trend visualisation is a missing capability.

### 4.5 Data Freshness and Provenance

- External data imports are one-shot manual operations; there is no scheduled refresh mechanism. For CBS statistical tables that update annually and PDOK boundaries that update quarterly, a cron-driven refresh pipeline would be needed.
- No provenance metadata (source URL, import timestamp, data version) is stored on imported records, making audit and reproducibility difficult.

### 4.6 Validation and Uncertainty

- Indicator computations assume complete and accurate input data; there is no uncertainty propagation or confidence interval reporting.
- The affordability stress thresholds (low/moderate/high/severe) in `HousingAffordability` are not validated against literature — an explicit TODO in the codebase.
- NRW and ILI benchmarks are hardcoded; they should reference IWA (International Water Association) standards and be configurable per city context.

### 4.7 Open Data Dependency

- The platform relies entirely on Dutch open data sources (PDOK, CBS). Adapting CrossTwin to other countries requires adding catalog entries and field mapping overrides for national equivalents (e.g., OS Open Data for the UK, IGN for France).
- The PDOK WFS endpoints return data in EPSG:28992; external sources (Sentinel Hub, GEE) return data in EPSG:4326. The import pipeline handles this, but the coordinate system mismatch adds complexity and a potential source of spatial join errors.

---

## 5. Conclusion

CrossTwin demonstrates that a structured, cross-domain urban digital twin can be built using open-source components (Django, PostGIS, TiTiler, Mapbox GL JS) and authoritative Dutch open data, with the DPSIR framework providing an explicit causal backbone that links urban drivers to policy responses. The model registry architecture enables rapid addition of new spatial models without boilerplate API code, and the catalog-driven import pipeline significantly lowers the barrier to populating the database.

However, of the 102 causal edges in the DPSIR graph, fewer than 30% are implemented as executable derivations — the rest are flat stored fields that require manual data entry. Closing this gap, particularly for the urban heat chain (SVF, MRT, PET, UTCI) and the cross-domain links (water tariff → affordability stress, land cover → infiltration), represents the primary technical roadmap for CrossTwin to fulfil its stated integration ambition.

Future work should prioritise: (1) vector tile endpoints for high-density layers, (2) a temporal data model supporting trend analysis, (3) scenario management for what-if planning, (4) uncertainty quantification for computed indicators, and (5) a scheduled data refresh pipeline.

---

## References

> *(To be completed — suggested citations below)*

- Bauer, P., et al. (2021). The digital revolution of Earth-system science. *Nature Computational Science*, 1, 104–113.
- Dembski, F., et al. (2020). Urban digital twins for smart cities and citizens. *Sustainability*, 12(6), 2307.
- EEA (1999). Environmental indicators: Typology and overview. *European Environment Agency Technical Report* No 25.
- INSPIRE Directive 2007/2/EC — Infrastructure for Spatial Information in Europe.
- Ledoux, H., & Meijers, M. (2011). Topologically consistent 3D city models obtained by extrusion. *International Journal of Geographical Information Science*, 25(4), 557–574.
- van der Hoeven, F., & van den Brink, A. (2020). Towards an urban digital twin. *Smart Cities*, 3(3), 703–718.

---

*Draft prepared from codebase documentation. Sections 3 (Results) and References require completion with empirical data and formal citations before submission.*
