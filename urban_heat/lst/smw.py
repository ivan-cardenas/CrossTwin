"""
Statistical Mono-Window (SMW) land surface temperature: the equations.

Pure numpy, no Earth Engine and no ORM: every function takes arrays on one
common grid and returns arrays on it. NaN means "no value" throughout and
propagates (a NaN NDVI, emissivity or brightness temperature gives a NaN LST).

Each function mirrors one module of users/sofiaermida/landsat_smw_lst
(named in its docstring), so results can be compared with the Earth Engine
script pixel by pixel. The two deviations are marked "Deviation:".

DAG edges: LandCover -> LST (NDVI -> FVC -> emissivity), RS_Imagery -> LST
(Landsat TIRS brightness temperature).
"""
import numpy as np

from .coefficients import (
    ASTER_TO_TIRS,
    EMISSIVITY_SNOW,
    EMISSIVITY_VEGETATION,
    EMISSIVITY_WATER,
    NCEP_STEP_MS,
    NDVI_BARE,
    NDVI_VEG,
    QA_CLOUD_BIT,
    QA_CLOUD_SHADOW_BIT,
    QA_SNOW_BIT,
    QA_WATER_BIT,
    SMW_COEFFICIENTS,
    TPW_BIN_WIDTH_MM,
    TPW_MISSING,
)

KELVIN = 273.15


def fractional_vegetation_cover(ndvi):
    """
    FVC = ((NDVI - 0.2) / (0.86 - 0.2))^2, clipped to [0, 1]   (compute_FVC.js)

    The clip comes after the square, as in the Earth Engine module, so an NDVI
    below 0.2 still gives a small positive FVC (NDVI 0 -> 0.09). Kept on purpose
    so results match the published code; water and snow get a fixed emissivity
    afterwards anyway (apply_qa_emissivity).
    """
    ndvi = np.asarray(ndvi, dtype="float64")
    fvc = ((ndvi - NDVI_BARE) / (NDVI_VEG - NDVI_BARE)) ** 2
    return np.clip(fvc, 0.0, 1.0)


def bare_ground_emissivity(aster_emissivity, aster_ndvi):
    """
    Remove ASTER's own vegetation from an ASTER GED band   (ASTER_bare_emiss.js):

        em_bare = (em_ASTER - 0.99 * FVC_ASTER) / (1 - FVC_ASTER)

    with FVC_ASTER from ASTER's mean NDVI. Inputs are physical values
    (emissivity 0-1, NDVI -1..1), not the GED's scaled integers.
    Fully vegetated ASTER pixels (FVC = 1) have no bare-ground signal: NaN.
    """
    fvc = fractional_vegetation_cover(aster_ndvi)
    em = np.asarray(aster_emissivity, dtype="float64")
    with np.errstate(divide="ignore", invalid="ignore"):
        bare = (em - EMISSIVITY_VEGETATION * fvc) / (1.0 - fvc)
    return np.where(fvc < 1.0, bare, np.nan)


def tirs_emissivity_from_aster(em13, em14):
    """ASTER bands 13/14 -> Landsat 8/9 band 10: c13*em13 + c14*em14 + c   (compute_emissivity.js)."""
    c13, c14, c0 = ASTER_TO_TIRS
    return c13 * np.asarray(em13, dtype="float64") + c14 * np.asarray(em14, dtype="float64") + c0


def surface_emissivity(fvc, bare_em13, bare_em14):
    """
    Dynamic band-10 emissivity   (compute_emissivity.js, use_ndvi = true):

        em = FVC * 0.99 + (1 - FVC) * em_bare,   em_bare = c13*em13_bare + c14*em14_bare + c
    """
    em_bare = tirs_emissivity_from_aster(bare_em13, bare_em14)
    fvc = np.asarray(fvc, dtype="float64")
    return fvc * EMISSIVITY_VEGETATION + (1.0 - fvc) * em_bare


def _bit_set(qa, bit):
    qa = np.nan_to_num(np.asarray(qa, dtype="float64"), nan=0.0).astype("int64")
    return (qa & (1 << bit)) != 0


def apply_qa_emissivity(emissivity, qa_pixel):
    """Water (QA bit 7) -> 0.99, then snow/ice (bit 5) -> 0.989   (compute_emissivity.js)."""
    em = np.array(emissivity, dtype="float64", copy=True)
    em[_bit_set(qa_pixel, QA_WATER_BIT)] = EMISSIVITY_WATER
    em[_bit_set(qa_pixel, QA_SNOW_BIT)] = EMISSIVITY_SNOW
    return em


def cloud_mask(qa_pixel):
    """True where QA_PIXEL flags cloud (bit 3) or cloud shadow (bit 4)   (cloudmask.js, sr)."""
    return _bit_set(qa_pixel, QA_CLOUD_BIT) | _bit_set(qa_pixel, QA_CLOUD_SHADOW_BIT)


def interpolate_tpw(fields, step_ms=NCEP_STEP_MS):
    """
    Total precipitable water (mm) at the image time   (NCEP_TPW.js).

    `fields` is a list of (tpw_array, |t_field - t_image| in ms) for the
    water-vapour fields of the acquisition day, `step_ms` the time between
    fields (6 h for NCEP, 1 h for ERA5). The two closest are blended with
    weights proportional to the *other* field's time distance, in steps:

        TPW = TPW_1 * dt_2 + TPW_2 * dt_1

    which is linear interpolation when the image lies between the two fields.
    No field that day -> TPW_MISSING everywhere, which smw_lst masks.

    Deviation: with exactly one field the Earth Engine code returns
    TPW_1 * dt_1 (it scales the value by its time distance); here it returns
    TPW_1 unchanged. NCEP has four fields per day, so this case is rare.
    """
    if not fields:
        return np.float64(TPW_MISSING)   # broadcasts over the grid
    ordered = sorted(fields, key=lambda f: f[1])
    tpw1, dist1 = ordered[0]
    tpw1 = np.asarray(tpw1, dtype="float64")
    if len(ordered) == 1:
        return tpw1
    tpw2, dist2 = ordered[1]
    return tpw1 * (dist2 / step_ms) + np.asarray(tpw2, dtype="float64") * (dist1 / step_ms)


def tpw_bin(tpw):
    """
    Index of the SMW coefficient row: (0,6] -> 0, (6,12] -> 1, ..., > 54 -> 9,
    and 0 for TPW <= 0 or NaN   (NCEP_TPW.js).
    """
    tpw = np.asarray(tpw, dtype="float64")
    pos = np.ceil(np.nan_to_num(tpw, nan=0.0) / TPW_BIN_WIDTH_MM) - 1
    return np.clip(pos, 0, 9).astype("int64")


def smw_lst(brightness_temperature_k, emissivity, tpw, sensor="L9"):
    """
    LST (K) = A * Tb / em + B / em + C   (SMWalgorithm.js)

    Tb is the TOA brightness temperature of TIRS band 10 in kelvin, em the
    band-10 surface emissivity, (A, B, C) the row of SMW_COEFFICIENTS[sensor]
    for the pixel's TPW bin. Pixels with TPW < 0 (no NCEP data) are NaN.
    """
    if sensor not in SMW_COEFFICIENTS:
        raise ValueError(f"Unknown sensor {sensor!r}; expected one of {sorted(SMW_COEFFICIENTS)}")
    table = np.asarray(SMW_COEFFICIENTS[sensor], dtype="float64")
    tpw = np.asarray(tpw, dtype="float64")
    pos = tpw_bin(tpw)
    a, b, c = table[pos, 0], table[pos, 1], table[pos, 2]
    tb = np.asarray(brightness_temperature_k, dtype="float64")
    em = np.asarray(emissivity, dtype="float64")
    with np.errstate(divide="ignore", invalid="ignore"):
        lst = a * tb / em + b / em + c
    return np.where(tpw < 0, np.nan, lst)


def land_surface_temperature(
    *,
    brightness_temperature_k,
    qa_pixel,
    aster_em13,
    aster_em14,
    aster_ndvi,
    tpw,
    ndvi=None,
    sensor="L9",
    mask_clouds=True,
):
    """
    The whole chain of Landsat_LST.js for one scene, on one grid.

    With `ndvi` (CrossTwin's NDVI layer resampled to the grid) the emissivity
    is the dynamic, vegetation-corrected one (use_ndvi = true). Without it the
    emissivity comes straight from ASTER (use_ndvi = false), and `aster_ndvi`
    is unused.

    Returns a dict of arrays: FVC (None without ndvi), EM, LST_K, LST_C.
    """
    if ndvi is not None:
        fvc = fractional_vegetation_cover(ndvi)
        em = surface_emissivity(
            fvc,
            bare_ground_emissivity(aster_em13, aster_ndvi),
            bare_ground_emissivity(aster_em14, aster_ndvi),
        )
    else:
        fvc = None
        em = tirs_emissivity_from_aster(aster_em13, aster_em14)

    em = apply_qa_emissivity(em, qa_pixel)
    if ndvi is not None:
        # Outside the CrossTwin NDVI layer there is no emissivity, not even
        # for water pixels: keep the LST footprint equal to the NDVI's.
        em = np.where(np.isnan(np.asarray(ndvi, dtype="float64")), np.nan, em)
    lst_k = smw_lst(brightness_temperature_k, em, tpw, sensor=sensor)
    if mask_clouds:
        lst_k = np.where(cloud_mask(qa_pixel), np.nan, lst_k)
    return {"FVC": fvc, "EM": em, "LST_K": lst_k, "LST_C": lst_k - KELVIN}
