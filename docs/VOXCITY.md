# VoxCity: a voxelized version of CrossTwin's data

Status: exploration only; nothing here is implemented. The information about VoxCity comes from its README, PyPI metadata and paper (v1.6.3, September 2026). The readthedocs site was not reachable from the environment where this was written, so parameter names marked **(verify)** should be checked against the docs before coding.

## 1. What VoxCity is

[VoxCity](https://github.com/kunifujiwara/VoxCity) (MIT licence, Python 3.10–3.13, `pip install voxcity`) converts buildings, tree canopy, land cover and terrain into **one semantic 3-D voxel grid**, then runs environmental simulations on it.

- **Generator**: `voxcity.generator.get_voxcity(rectangle_vertices, meshsize, building_source=…, land_cover_source=…, canopy_height_source=…, dem_source=…, output_dir=…)`. It downloads the four layers for a lon/lat rectangle (or takes your own, see §3) and voxelizes them at `meshsize` metres.
- **Output**: a `VoxCity` object whose voxel array is indexed `[north, east, up]` (row 0 = **south** edge), with `.to_xarray()` and `.extras["building_gdf"]`. It is saved as HDF5 with `axes`, `rotation_angle` and `rectangle_vertices` metadata. Voxel values are semantic class codes, e.g. 13 = Building, 5 = Tree, 11 = Developed; there are 14 land-cover classes.
- **Simulator**:
  - `get_view_index(voxcity, mode="sky" | "green", view_point_height=1.5, …)`: Sky View Index and Green View Index grids
  - `get_global_solar_irradiance_using_epw(voxcity, calc_type="instantaneous" | "cumulative", …)`: solar irradiance driven by an EPW weather file
  - `get_landmark_visibility_map(...)`, `get_network_values(...)`: visibility and mapping grid values onto street networks
- **GPU**: an optional `voxcity[gpu]` extra adds a **Taichi**-based `simulator_gpu` (ray tracing, solar), which runs on CUDA. It is the ready-made alternative to writing the kernels in PERFORMANCE.md §12 by hand. The CPU simulator uses Numba.
- **Exporters**: ENVI-met (INX/EDB), PALM-4U (NetCDF), OBJ (Blender/Rhino), MagicaVoxel (VOX).

Citation: Fujiwara et al. (2026), *Computers, Environment and Urban Systems* 123, 102366. doi:10.1016/j.compenvurbsys.2025.102366

## 2. Why it fits CrossTwin

VoxCity can fill several gaps listed in CLAUDE.md:

| CrossTwin gap | What VoxCity provides |
|---|---|
| `urban_heat`: the `DSM -> SVF -> Tmrt/PET`, `Vegetation_Coverage -> DSM`, `Canyon_Aspect -> DSM` chain is unimplemented; the rasters are expected pre-computed from SOLWEIG | A grid of buildings plus trees (the 3-D form behind the DSM), a **Sky View Index**, and **solar irradiance**, the shortwave input to Tmrt. It also exports to **ENVI-met / PALM**, which compute Tmrt/PET/UTCI in full |
| `builtup` TODO: *"Define green visibility index … for `Property.greenVisibility`"* | **Green View Index** (`mode="green"`) is exactly that metric. Sample it at each Property point |
| `PET -> NBS` (NBS coverage never reads heat values) | Add or remove trees in the voxel grid, rerun SVI/solar, and compare before and after. This is a what-if for nature-based solutions |
| `Energy`: no solar potential | Cumulative irradiance on roofs and façades (building surfaces) |
| Map is 2-D except `fill-extrusion` buildings | A consistent 3-D model of buildings and trees for visualization |

What VoxCity does **not** do: compute Tmrt, PET or UTCI itself. Those still need SOLWEIG, or the ENVI-met/PALM export and a run of that model. VoxCity's *Sky View Index* is a voxel-based view fraction and may differ from SOLWEIG's SVF definition, so compare the two before swapping one for the other.

## 3. Feeding it CrossTwin data instead of global sources

VoxCity's automatic sources are global or pan-European (OSM, Overture, EUBUCCO, ESA WorldCover, FABDEM/DeltaDTM, Meta 1 m canopy). For the Netherlands, CrossTwin already has, or can import, better data:

| VoxCity layer | Best Dutch source | Where it is in CrossTwin |
|---|---|---|
| Buildings (footprint + height) | BAG + 3D BAG heights | `builtup.Building` (`geom`, `height_m`) |
| Terrain | AHN DTM (0.5 m) | `physicalEnv.DigitalElevationModel.cog_path` |
| Canopy height | AHN **DSM − DTM** on vegetation pixels | `physicalEnv.DigitalSurfaceModel.cog_path` − DEM, masked by land cover |
| Land cover | BRT/BGT (PDOK) | `physicalEnv.LandCoverVector` / `LandCoverRaster` |

- **Buildings**: `get_voxcity` accepts a `building_gdf` GeoDataFrame. Export `Building` rows in EPSG:4326 with a height column. The exact column names VoxCity expects (e.g. `height`, `min_height`) are **(verify)**.
  ```python
  import geopandas as gpd
  from django.db import connection

  sql = """SELECT id, height_m AS height, ST_Transform(geom, 4326) AS geometry
           FROM builtup_building
           WHERE geom && ST_Transform(ST_MakeEnvelope(%s,%s,%s,%s,4326), 28992)"""
  buildings = gpd.read_postgis(sql, connection, geom_col="geometry", params=bbox)
  ```
  Buildings with a null `height_m` need a fallback, e.g. `numberFloors × 3 m`, or the 3D BAG `h_70p` percentile.
- **DEM / canopy / land cover**: VoxCity supports custom rasters for these layers. The parameter names for passing local GeoTIFFs are **(verify)**. Write clipped GeoTIFFs from the existing COGs with rasterio, reprojected to EPSG:4326, and pass their paths. Land cover must be **reclassified** to VoxCity's 14 classes; build a mapping table from `LandCoverClasses.class_name` in the same way `physicalEnv/signals.py` uses `URBAN_AREA_KEYWORDS`.
- **Custom designs**: `voxcity.importer.add_buildings_from_obj(voxcity, "design.obj", anchor_lonlat=…, anchor_elevation=…)` inserts a proposed building. This is useful for `housing.HousingProject` what-ifs.
- Some automatic sources go through Google Earth Engine (`earthengine-api`, `geemap`). CrossTwin already has an Earth Engine import path, so reuse the same credentials.

## 4. Proposed integration

```
builtup.Building ─┐
DEM / DSM COGs ───┼─► manage.py build_voxcity --city <id> --meshsize 2 ─► voxels/<app>/<city>_<mesh>.h5   (VoxelModel row)
LandCoverVector ──┘         (offline worker, GPU optional)                     │
                                                                               ├─► get_view_index(sky)   ─► COG ─► urban_heat.SkyViewFactor (source="VoxCity")
                                                                               ├─► get_view_index(green) ─► COG ─► sampled into builtup.Property.greenVisibility
                                                                               ├─► solar irradiance      ─► COG ─► new raster model (Energy / urban_heat)
                                                                               └─► OBJ / ENVI-met / PALM exports (for 3-D view and full microclimate runs)
```

1. **New model `VoxelModel`** (in `urban_heat` or a new `voxels` app): `city` FK (DO_NOTHING, per project convention), `meshsize`, `extent = PolygonField(srid=COORDINATE_SYSTEM)`, `h5_path`, `created`, and the source dates of the buildings, DEM and land cover used. Do **not** store the voxels in PostGIS. A 5 × 5 km city at 2 m with 100 vertical layers is 2500 × 2500 × 100 ≈ **625 M cells (~625 MB as uint8)**. Keep it as HDF5 on disk, alongside `cogs/`.
2. **Management command `build_voxcity`**, following `export_cogs`: export the inputs (§3), call `get_voxcity`, save the HDF5, then run the simulations. It runs offline, never in a request or a signal (PERFORMANCE.md §12). Use `voxcity[gpu]` on a CUDA machine.
3. **Back to 2-D rasters for the existing pipeline.** Simulation outputs are 2-D grids in VoxCity's `[north, east]` frame, with row 0 at the south. To make a GeoTIFF:
   - `np.flipud(grid)` (GeoTIFF row 0 is the north edge);
   - build the affine transform from `rectangle_vertices` and `meshsize`, write in EPSG:4326, then reproject to EPSG:28992 with rasterio. A lon/lat rectangle is slightly skewed in RD New, so resample rather than assume alignment. Keep `rotation_angle = 0`;
   - convert to a COG with `rio-cogeo` and create the model row with `cog_path` set. `core/signals.py` then skips the COG re-export, and TiTiler serves it with no further changes.
4. **Indicators.** The heat dashboard's `get_thermal_indices()` then picks up VoxCity-derived SVF like any other raster. Filter on `source`, or add a `source` choice, so SOLWEIG and VoxCity rasters aren't averaged together.
5. **3-D display (later step).** Mapbox GL has no native voxel or 3D Tiles support. Options:
   - (a) aggregate voxel columns into polygons and use the existing `fill-extrusion` style (cheapest);
   - (b) export OBJ, convert to 3D Tiles (e.g. `obj2tiles`/`py3dtiles`), and overlay with deck.gl's `Tile3DLayer` through `@deck.gl/mapbox`;
   - (c) a `PointCloudLayer` of occupied voxel centres for small areas.

   As with the rest of the map page, the JS belongs in `core/static/js/`, not in inline `<script>` blocks.

## 5. DAG traceability

Document these edges in the new calculation code, as the existing `calculations.py` files do:

- `Buildings -> DSM`, `Vegetation_Coverage -> DSM` (voxel generation)
- `DSM -> SVF` (`get_view_index(mode="sky")`)
- `Meteorology -> Tmrt` (shortwave part only, `get_global_solar_irradiance_using_epw`); the full `Tmrt -> PET/UTCI` still needs SOLWEIG/ENVI-met/PALM
- Green View Index has no DAG node yet. Add `Green_Visibility -> Property` to `core/DAG.dot` if it is adopted.

## 6. Risks and open questions

- **Dependencies**: VoxCity pulls in earthengine-api, geemap, osmnx, pyvista, taichi, ipyleaflet and more. Install it in a **separate worker environment** (`requirements-voxcity.txt`), not the Django web venv. GDAL should come from conda, which may clash with the project's pip `osgeo`/GDAL setup on Windows.
- **Scale**: resolution vs. memory. 1 m over a whole municipality is too large, so tile by district or neighborhood and merge the 2-D outputs.
- **Validation**: compare VoxCity SVI with SOLWEIG SVF, and 3D BAG heights with voxel building heights, on one neighborhood before using the results in indicators.
- **Unverified API details**: the custom raster input parameters, the `building_gdf` column names, and the exact return attributes. Check them in the [docs](https://voxcity.readthedocs.io/) and the example notebooks.

## 7. Suggested first prototype (about 1–2 days)

1. Pick one neighborhood. Export `builtup.Building` to a GeoDataFrame (EPSG:4326, `height`).
2. Run `get_voxcity(rect, meshsize=2, building_gdf=buildings, …)`, using the automatic sources for DEM, canopy and land cover at first.
3. Run `get_view_index(mode="sky")` and `mode="green"`.
4. Write both as COGs, load them into `SkyViewFactor` (source="VoxCity") and a scratch raster model, and view them on the map through TiTiler.
5. Compare with the existing SOLWEIG SVF raster. If they agree, replace the automatic DEM and canopy with AHN-derived inputs and write the `build_voxcity` command.

## Sources

- [VoxCity on GitHub](https://github.com/kunifujiwara/VoxCity)
- [voxcity on PyPI](https://pypi.org/project/voxcity/)
- [VoxCity documentation](https://voxcity.readthedocs.io/en/latest/index.html)
- [Paper (arXiv 2504.13934)](https://arxiv.org/abs/2504.13934) · [CEUS article](https://www.sciencedirect.com/science/article/pii/S019897152500119X)
- [Urban Analytics Lab project page](https://ual.sg/project/voxcity/)
- [Taichi Lang](https://taichi.graphics/)
