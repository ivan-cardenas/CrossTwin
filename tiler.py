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