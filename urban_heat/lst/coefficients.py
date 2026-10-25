"""
Constants of the Statistical Mono-Window (SMW) LST algorithm for Landsat 8/9.

Copied from Sofia Ermida's Earth Engine modules
(users/sofiaermida/landsat_smw_lst: SMW_coefficients.js, compute_emissivity.js,
compute_FVC.js; GitHub mirror sofiaermida/Landsat_SMW_LST). Cite:

    Ermida, S.L., Soares, P., Mantas, V., Göttsche, F.-M., Trigo, I.F., 2020.
    Google Earth Engine open-source code for Land Surface Temperature estimation
    from the Landsat series. Remote Sensing 12 (9), 1471.
    https://doi.org/10.3390/rs12091471

Only the Landsat 8/9 rows are kept: both use TIRS band 10 and the same ASTER
spectral-adjustment coefficients, so the rest of the package needs no
per-sensor branching beyond the SMW table.
"""

# (A, B, C) per total-precipitable-water bin. Bin i covers TPW in (6i, 6(i+1)] mm,
# bin 9 everything above 54 mm (see smw.tpw_bin).
SMW_COEFFICIENTS = {
    "L8": (
        (0.9751, -205.8929, 212.7173),
        (1.0090, -232.2750, 230.5698),
        (1.0541, -253.1943, 238.9548),
        (1.1282, -279.4212, 244.0772),
        (1.1987, -307.4497, 251.8341),
        (1.3205, -348.0228, 257.2740),
        (1.4540, -393.1718, 263.5599),
        (1.6350, -451.0790, 268.9405),
        (1.5468, -429.5095, 275.0895),
        (1.9403, -547.2681, 277.9953),
    ),
    "L9": (
        (0.9751, -206.2187, 213.0526),
        (1.0093, -232.7408, 230.9401),
        (1.0539, -253.4430, 239.2572),
        (1.1267, -279.1685, 244.2379),
        (1.1961, -306.7961, 251.8873),
        (1.3155, -346.5312, 257.2174),
        (1.4463, -390.7794, 263.3479),
        (1.6229, -447.2745, 268.5970),
        (1.5396, -427.0904, 274.6380),
        (1.9223, -541.7084, 277.4964),
    ),
}

TPW_BIN_WIDTH_MM = 6.0

# ASTER GED bands 13/14 -> Landsat 8/9 TIRS band 10 emissivity:
# em_B10 = C13 * em13 + C14 * em14 + C0
ASTER_TO_TIRS = (0.6820, 0.2578, 0.0584)

# Fraction of vegetation cover, FVC = ((NDVI - NDVI_BARE) / (NDVI_VEG - NDVI_BARE))^2
NDVI_BARE = 0.2
NDVI_VEG = 0.86

EMISSIVITY_VEGETATION = 0.99
EMISSIVITY_WATER = 0.99
EMISSIVITY_SNOW = 0.989

# Landsat Collection 2 QA_PIXEL bits.
QA_SNOW_BIT = 5
QA_WATER_BIT = 7
QA_CLOUD_BIT = 3
QA_CLOUD_SHADOW_BIT = 4

# NCEP reanalysis surface water vapour is 6-hourly.
NCEP_STEP_MS = 6 * 3600 * 1000
# Placeholder the Earth Engine module uses when no NCEP field exists for the day;
# pixels with TPW < 0 are masked out of the LST.
TPW_MISSING = -999.0

SENSORS = tuple(SMW_COEFFICIENTS)
