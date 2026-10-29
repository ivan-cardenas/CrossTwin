# Thermal comfort with SOLWEIG (Tmrt, UTCI, PET)

CrossTwin computes outdoor thermal comfort for the area shown on the map at
one hour chosen by the user. It combines the twin's stored layers (surface
model, terrain, buildings, land cover) with meteorology. The weather comes
from the user, from the KNMI station nearest to the area or from ERA5. The
radiation model is SOLWEIG (Lindberg et al. 2008), run on the GPU with
`solweig-gpu`. Building changes made in the map editor update the surface
model, and results they make outdated are flagged for recalculation.

Code: `urban_heat/solweig/` (`inputs.py`, `met.py`, `pipeline.py`,
`views.py`), `physicalEnv/dsm_patches.py`, `core/static/js/SolweigTool.js`.
Equations: `docs/functions_and_equations.tex` (sections *Building changes on
the DSM* and *Thermal comfort with SOLWEIG*).

## DPSIR edges

| DAG edge (`core/DAG.dot`) | Where |
|---|---|
| `Buildings -> DSM` | `physicalEnv/dsm_patches.py` (editor changes as an overlay on the DSM; receivers in `physicalEnv/signals.py`) |
| `DSM -> SVF` | SOLWEIG's sky view factors (cached per input); also the standalone SVF tool (`physicalEnv/svf.py`) |
| `SVF -> Tmrt`, `Meteorology -> Tmrt` | SOLWEIG 2022a radiant fluxes |
| `Tmrt -> UTCI`, `Meteorology -> UTCI` | SOLWEIG-GPU's UTCI |
| `Tmrt -> PET`, `SVF -> PET`, `Meteorology -> PET` | `pipeline.urban_pet` with `pet-adjusted` (Tmrt; SVF of the upwind source area in the heat island; the met record and the day's values) |

The thermal-comfort run is computed on demand, not by a receiver: a model save
must never start a GPU job. `Buildings -> DSM` is stored and propagates through
signals. Its downstream results are not recomputed automatically; they are
marked stale instead.

## Process

```mermaid
flowchart TD
    subgraph EDIT["Map editor (staff)"]
        B1["Create / reshape / re-height / delete<br/>a builtup.Building"]
    end
    B1 -- "post_save / post_delete<br/>(editor changes only)" --> P1["DSMBuildingPatch<br/>original footprint, footprint, height"]
    P1 -- "post_save / post_delete<br/>(Restore included)" --> E1["DSMEdit<br/>area + time"]
    P1 -. "journalled: Restore reverts it" .-> R1["EditBackup"]
    E1 --> S1["stale_results(view)<br/>SVF / runs older than an overlapping edit"]
    S1 --> M1(["Stale mark on the Actions menu,<br/>SVF and Thermal comfort rows"])

    subgraph VIEW["Thermal comfort tool (map view, date + hour)"]
        V1["View bbox (WGS84)"] --> V2["+ 50 m halo, cell 1/2/5 m<br/>limit 1 M cells"]
        V3["Date + hour<br/>(local time at the view centre)"]
    end

    subgraph LAYERS["CrossTwin layers"]
        L1["DigitalSurfaceModel (AHN COG)"]
        L2["DigitalElevationModel<br/>(else minimum filter of the DSM)"]
        L3["builtup.Building footprints"]
        L4["LandCoverVector (latest year)"]
    end

    V2 --> I0
    L1 --> I0["svf.load_dsm<br/>+ apply_patches"]
    P1 --> I0
    I0 --> I1["Building_DSM<br/>DSM in footprints, ground elsewhere"]
    L2 --> I1
    L3 --> I1
    I0 --> I2["Trees<br/>DSM − ground > 2.5 m outside footprints"]
    L2 --> I2
    L4 --> I3["Landcover<br/>1 paved · 2 buildings · 5 grass · 6 bare · 7 water"]
    L3 --> I3

    subgraph MET["Meteorology (one hour, uniform)"]
        W1["Manual"]
        W2["Nearest KNMI station<br/>(validated hourly data)"]
        W3["ERA5 hourly<br/>(Earth Engine, view centre)"]
    end
    V3 --> W2
    V3 --> W3
    W1 --> W4["Ta, RH, wind, wind dir.,<br/>Kdown, pressure<br/>(editable in the card)"]
    W2 --> W4
    W3 --> W4
    W4 --> W5["UMEP met file<br/>hour before + analysed hour"]

    subgraph SOL["solweig-gpu (PyTorch, CUDA if available)"]
        G1["Wall heights + aspects"]
        G2["Sky view factors + shadow matrices<br/>(cached per input hash)"]
        G3["Sun position: SPA at the grid centre,<br/>timezone of that point"]
        G4["Solweig_2022a<br/>radiant fluxes → Tmrt"]
        G5["UTCI"]
    end
    I1 --> G1
    I1 --> G2
    I2 --> G2
    I3 --> G4
    G1 --> G4
    G2 --> G4
    G3 --> G4
    W5 --> G4
    G4 --> G5
    W5 --> G5

    G4 --> C1["Crop the halo (band 2)"]
    G5 --> C1
    G4 --> PET["PET (pet-adjusted): Ta + urban heat island,<br/>1.2 m wind from buildings and trees"]
    W4 --> PET
    PET --> C1
    C1 --> O1["MeanRadiantTemperature · UTCI · PET rows<br/>(replace the same hour inside the view)"]
    O1 --> O2["COG export (core/signals.py)"]
    O2 --> O3(["Map layers; ThermalComfortRun<br/>records inputs, met, device, stats"])
    O3 -. "newer than the edits: mark cleared" .-> S1
```

## Steps

### 1. Area and time

The user opens **Actions → Calculate for this view → Thermal Comfort
(SOLWEIG)**, picks a date and an hour and a cell size (1, 2 or 5 m). The view's
bounding box is reprojected to EPSG:28992 and extended by `HALO_M` = 50 m on
every side. Shadows of buildings just outside the view still fall into it, and
the halo is cropped off the results. 50 m covers the shadow of a 30 m building
at a solar altitude of about 31°. The read window is limited to
`MAX_CELLS` = 1 M cells, about 1 × 1 km at 1 m.

The hour is local time at the view centre. Its timezone comes from
`timezonefinder`, the same lookup SOLWEIG uses for the sun, so a run in summer
uses CEST.

### 2. Surface model with the editor's building changes (`Buildings -> DSM`)

The DSM covering most of the view is read for the window (`svf.load_dsm`; the
AHN COG is warped onto the storage grid). Building changes made in the map
editor are applied on top (`dsm_patches.apply_patches`):

1. the original footprint of each edited building is set to ground level;
2. its current footprint is raised to ground + height: `height_m`, otherwise
   3 m per floor; with neither, the footprint is only cleared.

The DSM COG itself is never rewritten. It is a city-wide file, and an overlay
can be undone: patches are journalled with the editor's backup, so **Restore**
reverts them together with the buildings. Only editor changes create patches.
A BAG import must not replace AHN's measured roof shapes with flat blocks.

### 3. Ground

The ground is the DEM, read on exactly the same grid. Without a DEM it is
estimated from the DSM with a minimum filter over 40 m, which removes buildings
narrower than that. The source used is recorded in the run (`inputs.ground`).

### 4. SOLWEIG input rasters

| Raster | Derivation |
|---|---|
| `Building_DSM` | DSM inside `builtup.Building` footprints, ground elsewhere |
| `DEM` | ground |
| `Trees` | DSM − ground outside footprints where above 2.5 m (canopy height above ground), else 0 |
| `Landcover` | latest-year `LandCoverVector`, class names mapped to SOLWEIG classes (1 paved, 2 buildings, 5 grass, 6 bare soil, 7 water); buildings burned last; omitted without land cover |

AHN's DSM contains vegetation, which is why no separate tree layer is needed.
Note that SOLWEIG-GPU's documentation lists classes 3/4/5 for water,
vegetation and bare soil. The package's own table
(`landcoverclasses_2016a.txt`) uses 5/6/7, and it rewrites 3/4 to grass, so the
codes above follow the table.

### 5. Meteorology

One record for the hour, uniform over the view:

| Source | How |
|---|---|
| Manual | typed into the card |
| Nearest KNMI station | one request to KNMI's validated hourly data (`daggegevens.knmi.nl/klimatologie/uurgegevens`, all stations); the closest station to the view centre that measured temperature, humidity, wind and radiation that hour. The hour field `HH` is the UT hour the observation ends; global radiation Q (J/cm² per hour) → W/m² = Q·10⁴/3600 |
| ERA5 | `ECMWF/ERA5/HOURLY` on Earth Engine at the view centre: RH from dew point (Magnus), wind speed and from-direction from u/v, Kdown = ssrd/3600 s |

The fetched values fill the card and stay editable. The card shows the station
and its distance. A run stores the values it used and their source (`met` on
the `ThermalComfortRun`, the station name in the rasters' `source`).

The record is written as a UMEP met file with **two rows**, the hour before
and the analysed hour. SOLWEIG reads the file with `np.loadtxt`, which turns a
single row into a 1-D array it cannot index, and the extra hour lets SOLWEIG's
ground-temperature scheme settle. The result is band 2.

### 6. SOLWEIG-GPU

Called stage by stage with one tile:

1. wall heights and aspects (`walls_aspect.process_file_parallel`, the
   per-tile worker; `run_walls_aspect` would start a process pool);
2. `run_utci_tiles`: sky view factors and shadow matrices (cached in the
   work dir), solar position, Solweig_2022a radiant fluxes → Tmrt → UTCI.

`preprocess()` is not used: on bad input it calls `exit(1)`, which would end
the Django process. The tile layout it would produce is written directly
(`inputs.write_tiles`).

**Sun position.** SOLWEIG converts the centre of the input grid to WGS84 and
runs the SPA algorithm (Reda & Andreas 2004) there, with the UTC offset of that
point's timezone on the date. The sun therefore follows the area in view. The
card shows the solar altitude and azimuth before the run.

**Device.** PyTorch uses CUDA when available, otherwise the CPU (about 10×
slower). On an RTX 4050 laptop GPU (6 GB) the first run of a window takes about
1.2 ms per cell, most of it the sky view factors. A rerun of the same window
with other weather or another hour reuses them (~0.6 ms per cell). The work
dir is keyed by a hash of the input arrays (`cogs/solweig_work/<hash>/`), so a
building edit or a new DEM gives a new one.

**Execution.** A run takes minutes for a few hundred metres. It is therefore a
`ThermalComfortRun` executed in a background thread (one GPU run at a time),
and the card polls its status.

### 7. PET

PET comes from the `pet-adjusted` package (`pipeline.urban_pet`,
`pet_adjusted.urban_pet_from_rasters`). It solves the steady-state PET model
of `pythermalcomfort` (Höppe 1999, corrected by Walther & Goestchel 2018;
standard person 35 years, 1.75 m, 75 kg, 0.9 clo, 1.37 met) for every cell at
once, on CuPy when a CUDA GPU is available, otherwise NumPy. Two inputs vary
per cell, following Koopmans et al. (2020):

- **Air temperature** = the met record's + the urban heat island. The daily
  maximum UHI (Eq. S.3) scales with the day's Tmax − Tmin, mean Kdown and mean
  wind, and falls with the sky view factor and vegetation fraction of the
  cell's source area (1 km upwind + 100 m downwind × 500 m on 25 m tiles;
  a 700 m square below 1.5 m/s). It
  is multiplied by the diurnal factor of the UTC hour (Tables S.3/S.4).
- **Wind** = the 10 m wind reduced to 1.2 m by the frontal area densities and
  mean height of buildings and trees in a 280 × 140 m source area (Macdonald
  2000).

Inputs are the SOLWEIG window: DSM = `Building_DSM` + `Trees`, `DEM`, the
SOLWEIG land cover, and a stand-in NDVI (0.6 on trees and grass, −0.1 on
water), since pet-adjusted only thresholds NDVI at 0.16. PET runs on the
whole window before the halo is cropped, so the view's cells see 50 m beyond
it. Building cells are nodata, since PET is for pedestrians.

The day's values (`tmax_c`, `tmin_c`, `kdown_day_wm2`, `wind_day_ms`) are
filled by *Fetch*: the same KNMI station's hours 1–24 of the day, or ERA5's
hours of the UTC day. Without them, outside 1 April – 30 September (the
diurnal table's range) or with Tmax = Tmin, the heat island is left out and
the air temperature is the met record's; the wind is still reduced to 1.2 m.
`measurement_method` and `ThermalComfortRun.inputs["pet_model"]` say which
model was used.

PET runs on NumPy unless CuPy is installed, since the `solweig` extra does not
include `pet-adjusted[cuda]`. On the CPU it took ~35 s per 250 000 cells (a
500 m view at 1 m), which is small next to SOLWEIG itself.

### 8. Storage

One `MeanRadiantTemperature`, one `UTCI` and one `PET` row (°C, nodata −9999,
the view's extent):
- `date_time` is the analysed hour;
- `source` is `SOLWEIG DSM <id>: <met source>`;
- `measurement_method` records the model and device.

Their COGs are exported by `core/signals.py`, and the map adds the UTCI layer
(Tmrt and PET are listed for toggling). A rerun of the same hour replaces the
earlier rows inside the view; other hours are kept.

The `ThermalComfortRun` row records:
- the area;
- the met values;
- the inputs: DSM id, ground source, building cells, land cover, grid, halo,
  timezone, sun position;
- the device and statistics.

### 9. Stale results after building edits

Every change of a DSM patch appends a `DSMEdit` with the area it touched,
including Restore and deletes. An SVF raster or a finished run whose extent
overlaps an edit made after it is **stale** (`pipeline.stale_results`). The map
asks `/urban_heat/solweig/stale/?bbox=` after each building save, Restore and
map move. It shows an orange dot on the Actions button and on the Sky View
Factor / Thermal Comfort rows, and the card's button reads *Recalculate*.
Recalculating produces results newer than the edits, which clears the mark.

## Assumptions and limitations

- Meteorology is uniform over the view; the urban heat island effect on air
  temperature (`use_uhi`) and directional wind coefficients (`build_wind_ext_coeff`)
  are not used.
- Edited buildings get flat roofs on the median ground of their footprint.
- Trees are any non-building surface more than 2.5 m above the ground, which
  can include street furniture, bridges or vehicles in the DSM. Without a DEM,
  the ground estimate fails for buildings wider than 40 m.
- PET's heat-island source areas reach up to 1 km upwind, but the window has a
  50 m halo: the source areas are truncated at its edge, so the heat island of
  a small view is underestimated. Frontal areas are exact only for N/E/S/W
  winds (pet-adjusted's shortcut).
- Land-cover classes are mapped by name keywords; urban fabric counts as paved.
- One hour per run; a diurnal cycle would be 24 runs (the cached sky view
  factors make each additional hour cheaper).
- The validated KNMI hourly data and ERA5 lag real time by several days.

## Installation

```bash
uv sync --extra solweig          # solweig-gpu, torch (CUDA 12.8 wheels), pet-adjusted
uv run python -c "import torch; print(torch.cuda.is_available())"
```

On Windows the GDAL bindings that solweig-gpu imports come from the Gohlke
wheel CrossTwin already installs. On Linux, solweig-gpu needs GDAL's Python
bindings (`osgeo`) matching the system libgdal.

## API

| Path | Purpose |
|---|---|
| `GET /urban_heat/solweig/info/?bbox=&datetime=&resolution=` | DSM, grid, cell count and limit, sun position, device, estimated time, stale results |
| `GET /urban_heat/solweig/met/?bbox=&datetime=&source=knmi\|era5` | Met values to prefill the card (and the station) |
| `POST /urban_heat/solweig/calculate/` | Start a run (staff): `bbox`, `datetime`, `resolution`, `ta_c`, `rh_pct`, `wind_ms`, `wind_dir_deg`, `kdown_wm2`, `pressure_kpa`, `source`; optional `tmax_c`, `tmin_c`, `kdown_day_wm2`, `wind_day_ms` (heat island in PET) |
| `GET /urban_heat/solweig/runs/<id>/` | Run status; when done, the three layers |
| `GET /urban_heat/solweig/stale/?bbox=` | SVF and thermal-comfort results made stale by building edits |

## References

- Lindberg, F., Holmer, B., & Thorsson, S. (2008). SOLWEIG 1.0 – Modelling spatial variations of 3D radiant fluxes and mean radiant temperature in complex urban settings. *International Journal of Biometeorology*, 52(7), 697–713.
- SOLWEIG-GPU 2.0.0. https://github.com/nvnsudharsan/solweig-gpu, https://solweig-gpu.readthedocs.io
- Bröde, P., Fiala, D., Błażejczyk, K., et al. (2012). Deriving the operational procedure for the Universal Thermal Climate Index (UTCI). *International Journal of Biometeorology*, 56(3), 481–494.
- Höppe, P. (1999). The physiological equivalent temperature – a universal index for the biometeorological assessment of the thermal environment. *International Journal of Biometeorology*, 43(2), 71–75.
- Koopmans, S., Heusinkveld, B. G., & Steeneveld, G. J. (2020). A standardized Physical Equivalent Temperature urban heat map at 1-m spatial resolution to facilitate climate stress tests in the Netherlands. *Building and Environment*, 181, 106984.
- Cárdenas, I. pet-adjusted 0.1.5: PET with urban-adjusted air temperature and 1.2 m wind speed. https://github.com/ivan-cardenas/PET-Adjusted
- Walther, E., & Goestchel, Q. (2018). The P.E.T. comfort index: Questioning the model. *Building and Environment*, 137, 1–10.
- Reda, I., & Andreas, A. (2004). Solar position algorithm for solar radiation applications. *Solar Energy*, 76(5), 577–589.
- Hersbach, H., et al. (2020). The ERA5 global reanalysis. *Quarterly Journal of the Royal Meteorological Society*, 146(730), 1999–2049.
- Alduchov, O. A., & Eskridge, R. E. (1996). Improved Magnus form approximation of saturation vapor pressure. *Journal of Applied Meteorology*, 35(4), 601–609.
- KNMI. Uurgegevens van het weer in Nederland. https://www.daggegevens.knmi.nl/klimatologie/uurgegevens
