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

### 2.1 System Architecture

CrossTwin follows a two-server architecture deployed on a single host:

- **Django application server** (port 8000): handles the web UI, all API endpoints, data ingestion, and indicator computation. Settings are loaded from a `.env` file via `python-dotenv`; Windows GDAL/GEOS libraries are auto-discovered from the virtual environment.
- **TiTiler raster tile server** (port 8001): a FastAPI application that serves Cloud-Optimised GeoTIFF (COG) tiles for raster datasets. Django proxies tile requests to TiTiler via a `TITILER_BASE_URL` environment variable.

The data layer is PostgreSQL 15+ with the PostGIS extension. All vector geometry is stored in the native Dutch CRS (EPSG:28992) and transformed to WGS84 (EPSG:4326) at query time via `ST_Transform` for API responses.

The frontend uses **Mapbox GL JS** for map rendering (3D terrain, vector layers, raster overlays) and **HTMX** for partial page updates in the indicator dashboards, avoiding a full JavaScript framework dependency.

### 2.2 Administrative Hierarchy and Population Cascade

The spatial hierarchy follows the Dutch administrative structure:

```
Province → City (Gemeente) → District (Wijk) → Neighbourhood (Buurt)
```

Each level stores `currentPopulation`, `populationDensity`, and `area_km2`. When a Neighbourhood record is saved or deleted, a `post_save`/`post_delete` signal in `common/signals.py` triggers `_recompute_population()`, which propagates aggregated totals upward through District, City, and Province using `QuerySet.update()` (not `save()`) to prevent signal recursion.

### 2.3 Model Registry

A central `build_model_registry()` function in `core/utils.py` scans a curated list of allowed apps and inspects each model's fields to build four registries:

| Registry | Contents |
|---|---|
| `MODEL_REGISTRY` | All models from allowed apps |
| `VECTOR_REGISTRY` | Models with a `GeometryField` (no `RasterField`) |
| `RASTER_REGISTRY` | Models with a `RasterField` |
| `WMS_REGISTRY` | Models whose registry key contains "WMS" |

These registries power three generic API endpoints:

- `/api/layers/` — full layer catalog with geometry type, record count, per-field metadata (label, unit, type), and per-model Mapbox GL JS style definitions
- `/api/layers/<app>/<model>/geojson/` — GeoJSON FeatureCollection for any vector model, with all non-geometry properties included
- `/api/layers/<app>/<model>/bounds/` — bounding box extent via PostGIS `ST_Extent`

No per-model view code is required for new spatial models; registration in `INSTALLED_APPS` and `allowed_apps` is sufficient.

### 2.4 Raster Pipeline

Raster data (DEM, DSM, thermal comfort indices, land cover) follows a five-step pipeline:

1. PostGIS raster field → `ST_AsGDALRaster` → in-memory GeoTIFF
2. Reproject from EPSG:28992 to EPSG:4326 via **rasterio**
3. Convert to Cloud-Optimised GeoTIFF (COG) via **rio-cogeo** with overview levels
4. COG stored on disk under `cogs/<app_label>/<model_name>/`
5. TiTiler serves XYZ tiles from the COG path, with colormap and rescale parameters

A `post_save` signal in `core/signals.py` triggers this pipeline automatically for every model in `RASTER_REGISTRY` on save, so raster tiles are always current.

### 2.5 DPSIR Causal Network

The DPSIR framework (Driver–Pressure–State–Impact–Response) is used to structure causal relationships between urban systems. The full causal graph is defined in `common/DAG.dot` (Graphviz DOT format) and contains **102 directed edges** across the five domain systems. Example edges:

```
Population_Growth → Total_Population → Urbanization → LandCover
LandCover → Infiltration → AvailableFreshWater → Supply_Security
Supply_Security → Service_Time → User_Acceptance_WS → OPEX → Affordability_Stress
PET → NBS → Green_Area → Accessibility → Property → House_Price_Index
```

Each `calculations.py` function documents its implemented DAG edges via inline comments (`# DAG edges: A -> B`), enabling traceability between the causal model and executable code.

### 2.6 Indicator Computation Pattern

Domain dashboards (water supply, housing) follow a three-layer pattern:

1. **`calculations.py`** — pure Django ORM query functions that aggregate from the database. No side effects; all functions can be composed.
2. **`views.py`** — `_get_province_data()` assembles all calculations into a context dict; `_build_indicators()` is a pure function that derives display-ready metrics and supports parametric overrides (e.g., `consumption_override`, `interest_rate_override`) for what-if analysis.
3. **Templates** — HTMX-driven partials: a slider or input change triggers `hx-get` to a `recalculate_indicators` endpoint, which returns only the indicator grid partial, avoiding full page reload.

A `MOCK_DATA` dict provides fallback values when no province data exists in the database, allowing frontend development on an empty database.

### 2.7 External Data Import Pipeline

The `importer/` app provides two import paths:

**File upload**: Upload GeoJSON or Shapefile, map fields to any registered model via a field-mapping UI, preview the first N features, then import with database savepoints. A `MODEL_OVERRIDES` dict configures per-model upsert keys to prevent duplicate imports.

**Catalog-driven external import**: A `EXTERNAL_DATA_CATALOG` list defines datasets from authoritative Dutch open data sources:

| Source | Format | Example datasets |
|---|---|---|
| PDOK (Publieke Dienstverlening Op de Kaart) | WFS, WCS, Atom | Administrative boundaries, buildings, AHN elevation, land cover |
| CBS (Centraal Bureau voor de Statistiek) | OData | Housing stock, demographics |
| Sentinel-2 (Sentinel Hub Process API) | Raster (GeoTIFF) | NDVI, true colour, NDWI, moisture index |
| Google Earth Engine | Raster | Global surface water, forest cover, CHIRPS precipitation |

Each catalog entry declares `requires_bbox`, `requires_auth`, `requires_date_range`, and `draw_bbox` flags. When a bbox-requiring dataset is selected, the import UI shows a Mapbox map; for the municipality dataset (`pdok_cities`) — which cannot rely on existing city records — a manual rectangle-draw mode is provided instead of city-click selection.

The `import_dataset()` dispatcher in `external_data.py` handles format-specific fetching (WFS pagination, WCS coverage, Atom feed parsing, Sentinel Hub OAuth2, GEE service account authentication) and calls the shared file-upload import path for data ingestion.

### 2.8 Map Frontend

The map page (`mainMap/`) provides:

- **3D map** with Mapbox GL JS, configurable pitch, bearing, and basemap
- **Layer catalog panel** — all registered layers grouped by app, with visibility toggles, record counts, and colour swatches
- **Per-layer Mapbox GL JS styles** — defined server-side in `LAYER_STYLES` (a Python dict in `mainMap/views.py`), allowing full `paint`/`layout` specification including 3D building extrusions (`fill-extrusion`), dashed pipe networks, and data-driven expressions
- **Popups** — on feature click, properties are formatted using field metadata (verbose name, unit extracted from `help_text`, date formatting) and `Intl.NumberFormat` for locale-aware thousands separators
- **Tool-based filtering** — a toolbar switches the layer panel between thematic views (urban heat, water, green infrastructure, groundwater)

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
