"""
Land Surface Temperature from Landsat 8/9 with the Statistical Mono-Window algorithm.

Python port of the Earth Engine modules of users/sofiaermida/landsat_smw_lst
(as used by users/hanabobalova/LST_Landsat), adapted so the vegetation term of
the emissivity comes from CrossTwin's own NDVI layer:

    coefficients.py  SMW table and emissivity constants
    smw.py           the equations, pure numpy
    grid.py          the common EPSG:28992 grid
    gee.py           Landsat / ASTER GED / NCEP inputs from Earth Engine
    pipeline.py      calculate_lst(): NDVI layer + inputs -> LandSurfaceTemperature

Run it with `python manage.py calculate_lst --help`.

Submodules are not imported here: numpy, rasterio and ee stay out of the
Django startup path.

Ermida, S.L., Soares, P., Mantas, V., Göttsche, F.-M., Trigo, I.F., 2020.
Google Earth Engine open-source code for Land Surface Temperature estimation
from the Landsat series. Remote Sensing 12 (9), 1471.
https://doi.org/10.3390/rs12091471
"""
