"""
SOLWEIG thermal comfort for a map view and one hour (docs/THERMAL_COMFORT.md).

    view (WGS84) -> inputs.plan / inputs.build: DSM (+ editor building
        patches), ground, Building_DSM, Trees, Landcover on one grid with a halo
    met.Met (manual / nearest KNMI station / ERA5) -> met.write_umep
    solweig-gpu (PyTorch, CUDA when available): walls + aspect, SVF and shadow
        matrices (cached per input hash), Solweig_2022a -> Tmrt -> UTCI
    PET from Tmrt (pet_lookup), halo cropped
    -> one MeanRadiantTemperature, UTCI and PET row (COGs via core/signals.py),
       replacing earlier rows of the same hour inside the view

The sun follows the view: SOLWEIG takes latitude/longitude from the centre of
the input grid and the UTC offset from its timezone on that date.

Runs are ThermalComfortRun rows, executed one at a time in a background
thread (start_run): a view of a few hundred metres takes minutes the first
time (the SVF), so the map's tool polls the run instead of waiting on the
request.

DAG edges: DSM -> SVF, SVF -> Tmrt, SVF -> PET, Meteorology -> Tmrt,
Meteorology -> PET, Meteorology -> UTCI, Tmrt -> PET, Tmrt -> UTCI. On demand,
no receivers: a post_save must not start a GPU run.
"""
import logging
import os
import threading

from django.conf import settings

logger = logging.getLogger(__name__)

NODATA = -9999.0
SOURCE_PREFIX = "SOLWEIG DSM "
WORK_ROOT = os.path.join(settings.BASE_DIR, "cogs", "solweig_work")
# Band of the analysed hour in SOLWEIG's outputs (met.write_umep writes the
# hour before it first).
RESULT_BAND = 2
# PET: Höppe's (1999) standard person; wind as in the met file, like UMEP's SOLWEIG.
PET_PERSON = {"met": 1.37, "clo": 0.9, "age": 35, "weight": 75, "height": 1.75, "sex": "male"}
PET_STEP_C = 0.25
# A run still 'running' after this long died with its process.
RUN_TIMEOUT_S = 3 * 3600

_gpu = threading.Lock()


def solweig_available():
    try:
        import solweig_gpu  # noqa: F401
        import torch  # noqa: F401
    except ImportError:
        return False
    return True


def local_timezone(lon, lat):
    """
    Timezone of a point, as SOLWEIG finds it (TimezoneFinder); the analysed
    hour is local time there. Europe/Amsterdam without the extra.
    """
    from zoneinfo import ZoneInfo

    try:
        from timezonefinder import TimezoneFinder
        name = TimezoneFinder().timezone_at(lng=lon, lat=lat)
    except ImportError:
        name = None
    return ZoneInfo(name or "Europe/Amsterdam")


def centre(bbox_wgs84):
    return (bbox_wgs84[0] + bbox_wgs84[2]) / 2, (bbox_wgs84[1] + bbox_wgs84[3]) / 2


def device():
    import torch

    return "cuda" if torch.cuda.is_available() else "cpu"


def sun_position(when_local, lon, lat):
    """Solar altitude/azimuth (degrees) with solweig-gpu's SPA, or None without the extra."""
    try:
        from solweig_gpu.sun_position import sun_position as spa
    except ImportError:
        return None
    offset = when_local.utcoffset().total_seconds() / 3600
    sun = spa({"year": when_local.year, "month": when_local.month, "day": when_local.day,
               "hour": when_local.hour, "min": when_local.minute, "sec": 0, "UTC": offset},
              {"latitude": lat, "longitude": lon, "altitude": 3.0})
    import numpy as np

    zenith, azimuth = (float(np.ravel(sun[k])[0]) for k in ("zenith", "azimuth"))
    return {"altitude": round(90.0 - zenith, 1), "azimuth": round(azimuth, 1)}


def pet_lookup(tmrt, met):
    """
    PET (°C) of every Tmrt cell. Air temperature, humidity and wind are the
    same everywhere (one met record), so PET depends on Tmrt alone: solve it
    on a 1-D grid of PET_STEP_C over the Tmrt range and interpolate.
    """
    import numpy as np
    from pythermalcomfort.models import pet_steady

    finite = tmrt[np.isfinite(tmrt)]
    if not finite.size:
        return np.full_like(tmrt, np.nan)
    grid = np.arange(np.floor(finite.min()), np.ceil(finite.max()) + PET_STEP_C, PET_STEP_C)
    pet = np.array([pet_steady(tdb=met.ta_c, tr=float(t), v=max(met.wind_ms, 0.1), rh=met.rh_pct,
                               p_atm=met.pressure_kpa * 10.0, **PET_PERSON).pet for t in grid])
    return np.interp(tmrt, grid, pet).astype(np.float32)


def run_solweig(inputs, met, when_local):
    """
    Run SOLWEIG-GPU on the inputs; returns (tmrt, utci) of the analysed hour on
    the window grid. Work files live in WORK_ROOT/<inputs.key>/, so a rerun of
    the same view (other weather or hour) reuses walls and SVF.
    """
    import numpy as np
    import rasterio
    from solweig_gpu import run_utci_tiles
    from solweig_gpu.walls_aspect import process_file_parallel

    from . import inputs as solweig_inputs
    from .met import write_umep

    base = os.path.join(WORK_ROOT, inputs.key)
    pre = os.path.join(base, "pre")
    solweig_inputs.write_tiles(inputs, pre)
    os.makedirs(os.path.join(pre, "metfiles"), exist_ok=True)
    write_umep(met, when_local, os.path.join(pre, "metfiles", "metfile_0_0.txt"))
    walls = os.path.join(pre, "walls", "walls_0_0.tif")
    if not os.path.exists(walls):
        for folder in ("walls", "aspect"):
            os.makedirs(os.path.join(pre, folder), exist_ok=True)
        # The per-tile worker of run_walls_aspect(), which would start a process pool.
        process_file_parallel(("Building_DSM_0_0.tif", os.path.join(pre, "Building_DSM"),
                               os.path.join(pre, "walls"), os.path.join(pre, "aspect")))
        if not os.path.exists(walls):
            raise RuntimeError("SOLWEIG could not compute the wall heights.")
    run_utci_tiles(base, pre, when_local.strftime("%Y-%m-%d"), save_tmrt=True)
    out = os.path.join(base, "output_folder", "0_0")
    results = []
    for name in ("TMRT_0_0.tif", "UTCI_0_0.tif"):
        with rasterio.open(os.path.join(out, name)) as src:
            results.append(src.read(min(RESULT_BAND, src.count)).astype(np.float32))
    return tuple(results)


def _raster(array, origin, cell, srid):
    import numpy as np
    from django.contrib.gis.gdal import GDALRaster

    data = np.ascontiguousarray(np.where(np.isfinite(array), array, NODATA), dtype="float32")
    return GDALRaster({
        "srid": srid, "width": data.shape[1], "height": data.shape[0], "origin": origin,
        "scale": (cell, -cell), "datatype": 6,
        "bands": [{"data": data, "nodata_value": NODATA}],
    })


def replace_covered(model, record, when_local, area, cell):
    """Delete the other SOLWEIG rows of `model` for the same hour inside `area`, with their COGs."""
    from physicalEnv.svf import _storage_box

    replaced = []
    inside = (model.objects.filter(source__startswith=SOURCE_PREFIX, date_time=when_local,
                                   raster__contained=_storage_box(area.extent, pad=cell / 2))
              .exclude(pk=record.pk).defer("raster"))
    for old in inside:
        cog_path = old.cog_path
        replaced.append(old.pk)
        old.delete()
        if cog_path and os.path.exists(cog_path):
            try:
                os.unlink(cog_path)
            except OSError as e:
                logger.warning("Could not delete COG %s: %s", cog_path, e)
    return replaced


def _stats(array):
    import numpy as np

    valid = array[np.isfinite(array)]
    if not valid.size:
        return {"min": None, "max": None, "mean": None}
    return {"min": round(float(valid.min()), 2), "max": round(float(valid.max()), 2),
            "mean": round(float(valid.mean()), 2)}


def calculate(run):
    """Execute one ThermalComfortRun (inputs, SOLWEIG, PET, storage); sets its result fields."""
    from django.contrib.gis.geos import Polygon
    from django.db import transaction

    from physicalEnv import svf

    from urban_heat.models import PET, UTCI, MeanRadiantTemperature

    from . import inputs as solweig_inputs
    from .met import Met

    when_local = run.date_time.astimezone(local_timezone(*centre(run.bbox_wgs84)))
    met = Met(**run.met)
    p = solweig_inputs.plan(svf.wgs84_to_storage(run.bbox_wgs84), cell=run.resolution)
    _progress(run, "Preparing the input rasters…")
    inputs = solweig_inputs.build(p)
    run.device = device()
    _progress(run, f"Running SOLWEIG on {run.device.upper()} "
                   f"({inputs.shape[1]} x {inputs.shape[0]} cells)…")
    with _gpu:
        tmrt, utci = run_solweig(inputs, met, when_local)

    r0, c0, rows, cols = inputs.crop
    tmrt, utci = tmrt[r0:r0 + rows, c0:c0 + cols], utci[r0:r0 + rows, c0:c0 + cols]
    _progress(run, "Computing PET…")
    pet = pet_lookup(tmrt, met)

    origin, cell, srid = inputs.view_origin, inputs.cell, inputs.srid
    source = f"{SOURCE_PREFIX}{p['dsm'].pk}: {met.source}"[:100]
    method = f"SOLWEIG 2022a (solweig-gpu), {run.device}"
    replaced = {}
    with transaction.atomic():
        records = {}
        for key, model, array in (("mrt", MeanRadiantTemperature, tmrt), ("utci", UTCI, utci), ("pet", PET, pet)):
            method_label = f"{method}, PET lookup" if key == "pet" else method
            records[key] = model.objects.create(
                raster=_raster(array, origin, cell, srid), date_time=when_local,
                source=source, measurement_method=method_label[:100], resolution=cell)
        extent = Polygon.from_bbox(records["mrt"].raster.extent)
        extent.srid = srid
        for key, model in (("mrt", MeanRadiantTemperature), ("utci", UTCI), ("pet", PET)):
            replaced[key] = replace_covered(model, records[key], when_local, extent, cell)
        run.area = extent
        run.mrt, run.utci, run.pet = records["mrt"], records["utci"], records["pet"]
    run.inputs = {**inputs.labels, "grid": [inputs.shape[1], inputs.shape[0]], "halo_m": solweig_inputs.HALO_M,
                  "timezone": str(when_local.tzinfo), "sun": sun_position(when_local, *centre(run.bbox_wgs84))}
    run.stats = {"tmrt": _stats(tmrt), "utci": _stats(utci), "pet": _stats(pet), "replaced": replaced}
    return run


def _progress(run, message):
    run.message = message
    run.save(update_fields=["message"])


def execute(run_id):
    """Run a queued ThermalComfortRun to the end, recording success or failure."""
    from django.db import connection
    from django.utils import timezone

    from urban_heat.models import ThermalComfortRun

    from .inputs import SolweigError
    from .met import MetError

    run = ThermalComfortRun.objects.get(pk=run_id)
    run.status = "running"
    run.save(update_fields=["status"])
    try:
        calculate(run)
        run.status, run.message = "done", ""
    except (SolweigError, MetError) as e:
        run.status, run.message = "failed", str(e)
    except Exception as e:
        logger.exception("SOLWEIG run %s failed", run_id)
        run.status, run.message = "failed", f"SOLWEIG failed: {e}"
    finally:
        run.finished = timezone.now()
        run.save()
        if threading.current_thread() is not threading.main_thread():
            connection.close()
    return run


def start_run(run):
    """Execute `run` in a background thread (one GPU run at a time, see _gpu)."""
    from django.db import transaction

    # After the commit, so the thread sees the row.
    transaction.on_commit(lambda: threading.Thread(
        target=execute, args=(run.pk,), name=f"solweig-{run.pk}", daemon=True).start())


def run_state(run):
    """Status of a run for the map tool; a run left 'running' by a dead process reads as failed."""
    from django.utils import timezone

    status, message = run.status, run.message
    if status in ("queued", "running") and (timezone.now() - run.created).total_seconds() > RUN_TIMEOUT_S:
        status, message = "failed", "The run did not finish (the server may have restarted)."
    return status, message


def stale_results(view):
    """
    Results that the editor's building changes made stale inside `view`
    (storage CRS): SkyViewFactor rows and finished ThermalComfortRun rows
    (with their Tmrt still stored) older than a DSMEdit that overlaps them.
    Returns {"svf": [ids], "thermal": [run ids]}.
    """
    from physicalEnv.models import DSMEdit
    from physicalEnv.svf import _storage_box

    from urban_heat.models import SkyViewFactor, ThermalComfortRun

    box = _storage_box(view)
    svf, thermal = set(), set()
    for edit in DSMEdit.objects.filter(area__bboverlaps=box).order_by("-at")[:200]:
        svf.update(SkyViewFactor.objects.filter(raster__bboverlaps=edit.area).filter(
            raster__bboverlaps=box, date_time__lt=edit.at).values_list("pk", flat=True))
        thermal.update(ThermalComfortRun.objects.filter(
            status="done", mrt__isnull=False, area__bboverlaps=edit.area, finished__lt=edit.at)
            .filter(area__bboverlaps=box).values_list("pk", flat=True))
    return {"svf": sorted(svf), "thermal": sorted(thermal)}
