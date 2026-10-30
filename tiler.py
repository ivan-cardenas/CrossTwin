import os

# The PostGIS installer sets PROJ_LIB/PROJ_DATA machine-wide to its own (older)
# proj.db, which breaks rasterio's bundled PROJ ("DATABASE.LAYOUT.VERSION.MINOR").
# Drop them before rasterio loads so it uses the PROJ data inside its wheel.
for _var in ("PROJ_LIB", "PROJ_DATA"):
    os.environ.pop(_var, None)

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

# Standard COG tiler for pre-exported files
cog = TilerFactory()
app.include_router(cog.router, prefix="/cog", tags=["COG"])