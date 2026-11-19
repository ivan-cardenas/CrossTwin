import os

# The PostGIS installer sets PROJ_LIB/PROJ_DATA machine-wide to its own (older)
# proj.db, which breaks rasterio's bundled PROJ ("DATABASE.LAYOUT.VERSION.MINOR").
# Drop them before rasterio loads so it uses the PROJ data inside its wheel.
for _var in ("PROJ_LIB", "PROJ_DATA"):
    os.environ.pop(_var, None)

# GDAL settings for serving local COGs: don't list the cogs/ folder on every
# file open (it looks for sidecar files), keep decoded blocks in a 512 MB cache.
os.environ.setdefault("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")
os.environ.setdefault("GDAL_CACHEMAX", "512")

from titiler.core.factory import TilerFactory
from titiler.core.dependencies import DatasetParams
from fastapi import FastAPI, Query
from rio_tiler.io import Reader
from rio_tiler.models import ImageData
import numpy as np
from starlette.middleware.cors import CORSMiddleware

app = FastAPI(title="Raster TiTiler")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your Django domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def cache_versioned_tiles(request, call_next):
    """
    Tile and info responses whose URL carries `v=` (the COG's mtime, added by
    core/views.py::get_raster_tiles) never change, so the browser may keep them;
    a rewritten COG gets a new `v` and thus new URLs. Unversioned ones are not cached.
    """
    response = await call_next(request)
    if response.status_code == 200 and "v" in request.query_params:
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    else:
        response.headers.setdefault("Cache-Control", "no-cache")
    return response


# Standard COG tiler for pre-exported files
cog = TilerFactory()
app.include_router(cog.router, prefix="/cog", tags=["COG"])