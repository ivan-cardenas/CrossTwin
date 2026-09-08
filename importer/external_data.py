"""
External Data Catalog & Import Logic
=====================================
Defines available datasets from PDOK, Sentinel-2, and Google Earth Engine
that can be fetched and imported into CrossTwin models.

Each catalog entry specifies:
  - source:       'pdok' | 'sentinel2' | 'gee'
  - key:          unique identifier
  - name:         human-readable display name
  - description:  short description for the UI
  - target_model: Django model path (app_label.ModelName)
  - url/endpoint: where to fetch the data
  - format:       'wfs' | 'wcs' | 'wms' | 'raster' | 'atom'
  - field_mapping: dict mapping WFS properties → model fields
  - unique_field:  field to use for update_or_create lookup
"""

import json
import logging
import math
import os
import time
from pathlib import Path
from typing import Optional, Dict, Any, Tuple, List
from datetime import datetime, timedelta
from urllib.parse import urlencode

import requests
from pyproj import Transformer
from django.apps import apps
from django.db import transaction, IntegrityError
from django.contrib.gis.geos import GEOSGeometry, Point, Polygon, MultiPolygon
from django.conf import settings
from django.utils import timezone

from .external_catalog import FIELD_MAPPINGS, CATALOG_BY_KEY

coordinate_system = settings.COORDINATE_SYSTEM

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Import Handlers
# ---------------------------------------------------------------------------

class ImportResult:
    """Result object for import operations."""
    def __init__(self, status: str, message: str, records_created: int = 0, records_updated: int = 0, file_path: str = None, needs_credentials: bool = False):
        self.status = status  # 'success', 'error', 'skipped', 'pending'
        self.message = message
        self.records_created = records_created
        self.records_updated = records_updated
        self.file_path = file_path
        # True when this failure specifically means "the caller's (or default)
        # credentials didn't authenticate" — the frontend uses this to know
        # when to surface a credentials input rather than just showing an error.
        self.needs_credentials = needs_credentials

    def to_dict(self):
        return {
            "status": self.status,
            "message": self.message,
            "records_created": self.records_created,
            "records_updated": self.records_updated,
            "file_path": self.file_path,
            "needs_credentials": self.needs_credentials,
        }


def ensure_multipolygon(geom: GEOSGeometry) -> MultiPolygon:
    """Convert Polygon to MultiPolygon if needed."""
    if geom.geom_type == 'Polygon':
        return MultiPolygon(geom)
    elif geom.geom_type == 'MultiPolygon':
        return geom
    else:
        raise ValueError(f"Expected Polygon or MultiPolygon, got {geom.geom_type}")


def get_model_class(model_path: str):
    """
    Get Django model class from 'app_label.ModelName' string.
    """
    try:
        return apps.get_model(model_path)
    except LookupError:
        raise ValueError(f"Model not found: {model_path}")


def _legend_url_from_capabilities(base_url: str, layer: str) -> Optional[str]:
    """
    Look up a layer's <LegendURL><OnlineResource xlink:href="..."/> from the
    WMS GetCapabilities document — the standards-correct way to discover a
    legend, since a server can (and PDOK's LGN service does) publish a
    static legend image per layer without supporting the dynamic
    GetLegendGraphic request at all.
    """
    from xml.etree import ElementTree as ET

    try:
        resp = requests.get(
            base_url,
            params={"service": "WMS", "version": "1.3.0", "request": "GetCapabilities"},
            timeout=15,
        )
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
    except Exception as e:
        logger.warning(f"Could not fetch/parse GetCapabilities for legend lookup ({base_url}): {e}")
        return None

    def local(tag: str) -> str:
        return tag.rsplit('}', 1)[-1]

    for layer_el in root.iter():
        if local(layer_el.tag) != "Layer":
            continue
        name_el = next((c for c in layer_el if local(c.tag) == "Name"), None)
        if name_el is None or name_el.text != layer:
            continue
        for legend_el in layer_el.iter():
            if local(legend_el.tag) != "LegendURL":
                continue
            for res_el in legend_el:
                if local(res_el.tag) != "OnlineResource":
                    continue
                href = next((v for k, v in res_el.attrib.items() if local(k) == "href"), None)
                if href:
                    return href
    return None


def default_wms_legend_url(base_url: str, layer: str) -> Optional[str]:
    """
    Resolve a legend image URL for a WMS layer, used as a fallback when a
    catalog entry doesn't specify its own `legend_url`. Tries the server's
    own advertised <LegendURL> from GetCapabilities first (correct and free
    of guesswork), then falls back to constructing a GetLegendGraphic
    request for servers that support the operation but don't advertise a
    static legend.

    A server that supports neither returns a WMS ServiceExceptionReport
    (XML) with a 200 status rather than a clean error, which would
    otherwise get stored and rendered as a broken image in the map legend —
    so the GetLegendGraphic fallback is actually fetched and only returned
    if the response is really an image.
    """
    legend_url = _legend_url_from_capabilities(base_url, layer)
    if legend_url:
        return legend_url

    # SLD_VERSION isn't part of the WMS spec's required params, but PDOK's
    # MapServer-backed services (e.g. AHN) reject GetLegendGraphic with
    # MissingParameterValue without it.
    url = f"{base_url}?{urlencode({'service': 'WMS', 'version': '1.3.0', 'request': 'GetLegendGraphic', 'format': 'image/png', 'layer': layer, 'SLD_VERSION': '1.1.0'})}"
    try:
        resp = requests.get(url, timeout=10)
        if resp.ok and resp.headers.get("content-type", "").startswith("image/"):
            return url
    except requests.RequestException as e:
        logger.warning(f"GetLegendGraphic check failed for layer={layer}: {e}")
    return None


def load_raster_into_target_model(
    filepath: str,
    dataset: Dict,
    bbox: Optional[list] = None,
    date_to: Optional[str] = None,
    acquisition_date: Optional[datetime] = None,
) -> Tuple[bool, str]:
    """
    Load a downloaded raster file into its catalog entry's target_model.

    The WCS/openEO fetchers previously stopped once the .tif landed on disk,
    which meant no model row (and therefore no post_save signal) was ever
    created — core/signals.py's auto_export_cog only fires on save(), so the
    raster never became a COG and TiTiler had nothing to serve. This mirrors
    importer/views.py::_raster_import (the file-upload path, which already
    works) so external imports go through the same save() -> signal -> COG
    pipeline, generalized to resolve Province/year metadata from bbox/date
    when the target model requires them (e.g. common.LandCoverRaster).
    """
    from django.contrib.gis.gdal import GDALRaster
    from core.rasterOperations import get_raster_field_name, export_geotiff_to_cog
    import rasterio
    from rasterio.warp import calculate_default_transform, reproject, Resampling
    import tempfile
    import shutil

    model_path = dataset["target_model"]
    try:
        Model = get_model_class(model_path)
        field_name = get_raster_field_name(Model)
    except (ValueError, LookupError) as e:
        return False, f"Downloaded, but cannot load into {model_path}: {e}"

    # Models flagged SKIP_RASTER_DB_STORAGE (common.DigitalElevationModel/
    # DigitalSurfaceModel) never get their raster written into Postgres at
    # all — nothing queries it with server-side PostGIS raster SQL, so a
    # RasterField blob there is a large, purely redundant write. It's also
    # the actual failure mode for city-scale imports: a multi-hundred-MB
    # mosaic sent as a single query parameter can crash the Postgres backend
    # outright ("server closed the connection unexpectedly") rather than
    # erroring cleanly. Skip straight to a COG built from the source file.
    skip_db_storage = getattr(Model, "SKIP_RASTER_DB_STORAGE", False)

    model_srid = Model._meta.get_field(field_name).srid

    temp_reprojected = None
    writable_file = None
    gdal_raster = None
    try:
        model_field_names = {f.name for f in Model._meta.get_fields()}
        field_values = {}
        lookup_keys = []

        if not skip_db_storage:
            with rasterio.open(filepath) as src:
                src_epsg = src.crs.to_epsg() if src.crs else None

            raster_to_load = filepath
            if src_epsg and src_epsg != model_srid:
                fd, temp_reprojected = tempfile.mkstemp(suffix=".tif")
                os.close(fd)
                with rasterio.open(filepath) as src:
                    dst_crs = f"EPSG:{model_srid}"
                    transform, width, height = calculate_default_transform(
                        src.crs, dst_crs, src.width, src.height, *src.bounds
                    )
                    kwargs = src.meta.copy()
                    kwargs.update({"crs": dst_crs, "transform": transform, "width": width, "height": height})
                    with rasterio.open(temp_reprojected, "w", **kwargs) as dst:
                        for i in range(1, src.count + 1):
                            reproject(
                                source=rasterio.band(src, i),
                                destination=rasterio.band(dst, i),
                                src_transform=src.transform,
                                src_crs=src.crs,
                                dst_transform=transform,
                                dst_crs=dst_crs,
                                resampling=Resampling.bilinear,
                            )
                raster_to_load = temp_reprojected

            # GDALRaster in write mode needs its own file handle, separate from
            # whatever we just read with rasterio above.
            fd, writable_file = tempfile.mkstemp(suffix=".tif")
            os.close(fd)
            shutil.copy2(raster_to_load, writable_file)
            gdal_raster = GDALRaster(writable_file, write=True)
            field_values[field_name] = gdal_raster

        if "city" in model_field_names and bbox:
            from common.models import City

            centroid = Point((bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2, srid=4326)
            centroid.transform(coordinate_system)
            city = City.objects.filter(geom__intersects=centroid).first()
            if city:
                field_values["city"] = city
                lookup_keys.append("city")

        if "year" in model_field_names:
            year_str = (date_to or "")[:4]
            field_values["year"] = int(year_str) if year_str.isdigit() else datetime.now().year
            lookup_keys.append("year")

        # Carry the catalog entry's satellite/process metadata onto the model
        # row so LandCoverRaster/SatelliteImagery/DigitalElevationModel/
        # DigitalSurfaceModel records reflect what actually produced them,
        # instead of only holding a bare raster + cog_path.
        if "date" in model_field_names and acquisition_date:
            # `acquisition_date` is a real timestamp looked up from the
            # actual satellite catalog (Copernicus Data Space's OData API
            # for Sentinel-2 — see Sentinel2Importer._lookup_acquisition_date
            # — or the source ImageCollection's own system:time_start for
            # GEE, inline in GEEImporter.export_raster), not the requested
            # search window or the import time. openEO/GEE composites carry
            # no acquisition timestamp in the downloaded file itself
            # (confirmed empty GDAL tags on a real openEO TrueColor
            # download), so previously this fell back to date_to or
            # datetime.now() — both are guesses, not real satellite data, so
            # the field is left unset when no real date could be found
            # rather than stamping it with an invented one.
            field_values["date"] = acquisition_date
        if "source" in model_field_names:
            source_labels = {"pdok": "PDOK", "sentinel2": "Sentinel-2 / Copernicus", "gee": "Google Earth Engine"}
            field_values["source"] = source_labels.get(dataset.get("source"), dataset.get("source"))
        if "satellite_type" in model_field_names and dataset.get("satellite_type"):
            field_values["satellite_type"] = dataset["satellite_type"]
        if "index" in model_field_names:
            index_value = dataset.get("openeo_process") or dataset.get("layer") or dataset.get("band") or dataset.get("name")
            if index_value:
                field_values["index"] = index_value
        if "resolution" in model_field_names and dataset.get("resolution_m") is not None:
            field_values["resolution"] = dataset["resolution_m"]

        if lookup_keys:
            lookup = {k: field_values[k] for k in lookup_keys}
            defaults = {k: v for k, v in field_values.items() if k not in lookup_keys}
            obj, created = Model.objects.update_or_create(**lookup, defaults=defaults)
        else:
            obj = Model.objects.create(**field_values)
            created = True

        if skip_db_storage:
            # The post_save signal (core/signals.py::auto_export_cog) is a
            # no-op for these models — cog_path is produced directly from
            # the source file here instead of read back out of Postgres.
            export_geotiff_to_cog(filepath, obj)

        return True, f"Loaded into {model_path} ({'created' if created else 'updated'} id={obj.id})."

    except Exception as e:
        logger.exception(f"Failed to load raster '{filepath}' into {model_path}")
        return False, f"Downloaded, but failed to load into {model_path}: {e}"

    finally:
        if gdal_raster is not None:
            del gdal_raster
        for tmp in (temp_reprojected, writable_file):
            if tmp and os.path.exists(tmp):
                try:
                    os.unlink(tmp)
                except Exception as e:
                    logger.warning(f"Could not delete temp file {tmp}: {e}")


class GEEAuthManager:
    """Manages Google Earth Engine authentication."""
    
    _initialized = False
    _credentials = None
    _project_id = None
    
    @classmethod
    def initialize(cls, service_account_json: str) -> Tuple[bool, str]:
        """
        Initialize GEE with service account credentials.
        """
        try:
            import ee
            
            # Parse and validate JSON
            try:
                credentials_dict = json.loads(service_account_json)
            except json.JSONDecodeError as e:
                return False, f"Invalid JSON: {e}"
            
            # Check required fields
            required_fields = ['type', 'project_id', 'private_key', 'client_email']
            missing = [f for f in required_fields if f not in credentials_dict]
            if missing:
                return False, f"Missing required fields: {', '.join(missing)}"
            
            if credentials_dict.get('type') != 'service_account':
                return False, "JSON must be a service account key (type='service_account')"
            
            # Create credentials
            from google.oauth2 import service_account
            credentials = service_account.Credentials.from_service_account_info(
                credentials_dict,
                scopes=['https://www.googleapis.com/auth/earthengine']
            )
            
            # Initialize Earth Engine
            ee.Initialize(credentials=credentials, project=credentials_dict['project_id'])
            
            # Test connection
            ee.Number(1).getInfo()
            
            cls._initialized = True
            cls._credentials = credentials
            cls._project_id = credentials_dict['project_id']
            
            return True, f"Successfully authenticated as {credentials_dict['client_email']}"
            
        except ImportError:
            return False, "Google Earth Engine library not installed. Run: pip install earthengine-api google-auth"
        except Exception as e:
            cls._initialized = False
            return False, f"GEE authentication failed: {str(e)}"
    
    @classmethod
    def is_initialized(cls) -> bool:
        return cls._initialized
    
    @classmethod
    def get_project_id(cls) -> Optional[str]:
        return cls._project_id
    
    @classmethod
    def reset(cls):
        cls._initialized = False
        cls._credentials = None
        cls._project_id = None


class PDOKImporter:
    """Import handler for PDOK datasets - imports directly to Django models."""
    
    @staticmethod
    def fetch_wfs(dataset: Dict, bbox: Optional[list] = None, max_features: int = 1000000) -> ImportResult:
        """
        Fetch vector data from PDOK WFS service and import directly to Django model.
        
        Args:
            dataset: Catalog entry dict
            bbox: [xmin, ymin, xmax, ymax] in EPSG:28992
            max_features: Maximum features to fetch
        """
        try:
            url = dataset["url"]
            layer = dataset["layer"]
            dataset_key = dataset["key"]
            model_path = dataset["target_model"]
            
            # Get field mapping for this dataset
            mapping = FIELD_MAPPINGS.get(dataset_key)
            if not mapping:
                return ImportResult("error", f"No field mapping defined for {dataset_key}")
            
            # Get model class
            try:
                Model = get_model_class(model_path)
            except ValueError as e:
                return ImportResult("error", str(e))
            
            # Build WFS request parameters
            params = {
                "service": "WFS",
                "version": "2.0.0",
                "request": "GetFeature",
                "typeName": layer,
                "outputFormat": "application/json",
                "srsName": dataset["params"].get("srsName", "EPSG:28992"),
            }

            # Add bbox filter if provided (bbox arrives in WGS84 from frontend)
            if bbox:
                target_srs = dataset["params"].get("srsName", "EPSG:28992")
                target_epsg = int(target_srs.split(":")[-1])
                if target_epsg != 4326:
                    tx = Transformer.from_crs("EPSG:4326", f"EPSG:{target_epsg}", always_xy=True)
                    x1, y1 = tx.transform(bbox[0], bbox[1])
                    x2, y2 = tx.transform(bbox[2], bbox[3])
                    bbox = [x1, y1, x2, y2]
                params["bbox"] = f"{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]},urn:ogc:def:crs:EPSG::{target_epsg}"

            # Add CQL filter if specified
            if "cql_filter" in dataset.get("params", {}):
                params["cql_filter"] = dataset["params"]["cql_filter"]

            # PDOK's GeoServer instances silently cap a single GetFeature response
            # at 1000 features regardless of the requested count, so anything past
            # that would otherwise be dropped with no error. Page through the full
            # result set with startIndex, stopping once a page comes back short
            # (the reliable "last page" signal — numberMatched/numberReturned
            # aren't consistently present across PDOK layers).
            page_size = min(max_features, 1000)
            all_features = []
            start_index = 0
            max_pages = 100  # safety cap against a server that ignores startIndex
            logger.info(f"Fetching WFS: {url} layer={layer}")
            for page in range(max_pages):
                params["count"] = page_size
                params["startIndex"] = start_index
                response = requests.get(url, params=params, timeout=120)
                response.raise_for_status()
                geojson = response.json()
                features = geojson.get("features", [])
                all_features.extend(features)

                if len(features) < page_size or len(all_features) >= max_features:
                    break
                start_index += len(features)
            else:
                logger.warning(f"[{dataset_key}] hit the {max_pages}-page safety cap while paginating")

            all_features = all_features[:max_features]
            logger.info(f"Fetched {len(all_features)} feature(s) from {layer} across {page + 1} page(s)")
            features = all_features

            if not features:
                return ImportResult("success", "No features found in the specified area.", 0)

            # Import features to database
            geom_field = mapping.get("__geometry__", "geom")
            unique_wfs_prop = mapping.get("__unique__")
            unique_model_field = mapping.get("__unique_field__")

            # PDOK/GeoServer WFS layers (bag:pand in particular) can return the same
            # feature — same identificatie — more than once in a single GetFeature
            # response (e.g. a pand that straddles an internal tile boundary). Since
            # __unique_field__ is often the model's actual primary key (see
            # pdok_buildings), two rows for the same identificatie both attempting an
            # INSERT with the same pk trips "duplicate key value violates unique
            # constraint", even against an empty table. Deduplicate up front, keeping
            # the first occurrence, so each unique id is only ever create()'d once.
            if unique_wfs_prop:
                seen_keys = set()
                deduped = []
                duplicate_count = 0
                for feat in features:
                    key = feat.get("properties", {}).get(unique_wfs_prop)
                    if key is not None and key in seen_keys:
                        duplicate_count += 1
                        continue
                    if key is not None:
                        seen_keys.add(key)
                    deduped.append(feat)
                if duplicate_count:
                    logger.warning(
                        f"[{dataset['key']}] dropped {duplicate_count} duplicate feature(s) "
                        f"sharing an existing '{unique_wfs_prop}' value before import."
                    )
                features = deduped

            created_count = 0
            updated_count = 0
            errors = []

            # Pre-load parent model objects for spatial FK resolution (done once per batch)
            spatial_fk_conf = mapping.get("__spatial_fk__")
            parent_objects = []
            if spatial_fk_conf:
                ParentModel = get_model_class(spatial_fk_conf["model"])
                parent_objects = list(ParentModel.objects.all())
                if not parent_objects and spatial_fk_conf.get("required", True):
                    return ImportResult(
                        "error",
                        f"No {spatial_fk_conf['model']} records found — cannot resolve '{spatial_fk_conf['field']}' FK. "
                        f"Import the parent records first.",
                    )

            for feat in features:
                try:
                    with transaction.atomic():
                        props = feat.get("properties", {})
                        geom_json = feat.get("geometry")
                        
                        if not geom_json:
                            continue
                        
                        # Parse geometry
                        geom = GEOSGeometry(json.dumps(geom_json))

                        # GeoJSON parsing always sets srid=4326 by convention, but
                        # PDOK returns coordinates in the requested srsName CRS
                        # (EPSG:28992 by default). Force the correct SRID so Django
                        # doesn't try to transform RD New meter values as WGS84 degrees.
                        source_srs = dataset.get("params", {}).get("srsName", "EPSG:28992")
                        source_epsg = int(source_srs.split(":")[-1])
                        geom.srid = source_epsg
                        
                        # Convert to MultiPolygon if model expects it
                        model_geom_field = Model._meta.get_field(geom_field)
                        if hasattr(model_geom_field, 'geom_type'):
                            if model_geom_field.geom_type == 'MULTIPOLYGON' and geom.geom_type == 'Polygon':
                                geom = MultiPolygon(geom)
                            elif model_geom_field.geom_type == 'MULTILINESTRING' and geom.geom_type == 'LineString':
                                from django.contrib.gis.geos import MultiLineString
                                geom = MultiLineString(geom)
                            elif model_geom_field.geom_type == 'MULTIPOINT' and geom.geom_type == 'Point':
                                from django.contrib.gis.geos import MultiPoint
                                geom = MultiPoint(geom)
                        
                        # Build field values from mapping
                        field_values = {geom_field: geom}

                        for wfs_prop, model_field in mapping.items():
                            if wfs_prop.startswith("__"):
                                continue  # Skip special keys
                            if wfs_prop in props and props[wfs_prop] is not None:
                                field_values[model_field] = props[wfs_prop]

                        # __static__ fields aren't sourced from WFS properties at
                        # all (e.g. every feature in the natura2000 dataset is by
                        # definition a Natura 2000 area) -- always applied last so
                        # they win over anything a WFS property might otherwise map.
                        field_values.update(mapping.get("__static__", {}))

                        # Resolve spatial FK: find the parent whose geometry contains this feature's centroid
                        if spatial_fk_conf and parent_objects:
                            centroid = geom.centroid
                            parent = next((p for p in parent_objects if p.geom.contains(centroid)), None)
                            if parent is None:
                                # Boundary edge case: fall back to intersection
                                parent = next((p for p in parent_objects if p.geom.intersects(centroid)), None)
                            if parent:
                                field_values[spatial_fk_conf["field"]] = parent
                            elif spatial_fk_conf.get("required", True):
                                errors.append(
                                    f"No parent {spatial_fk_conf['model']} found for feature "
                                    f"'{props.get(unique_wfs_prop, '?')}' — skipped."
                                )
                                continue

                        # Use update_or_create if unique field is defined
                        if unique_wfs_prop and unique_model_field and unique_wfs_prop in props:
                            lookup = {unique_model_field: props[unique_wfs_prop]}
                            defaults = {k: v for k, v in field_values.items() if k != unique_model_field}

                            try:
                                with transaction.atomic():
                                    obj, was_created = Model.objects.update_or_create(
                                        **lookup,
                                        defaults=defaults
                                    )
                            except IntegrityError:
                                existing = Model.objects.filter(**lookup).first()
                                if existing is None:
                                    raise
                                for field_name, value in defaults.items():
                                    setattr(existing, field_name, value)
                                existing.save()
                                obj = existing
                                was_created = False

                            if was_created:
                                created_count += 1
                            else:
                                updated_count += 1
                        else:
                            # Just create new records
                            Model.objects.create(**field_values)
                            created_count += 1
                            
                except Exception as e:
                    errors.append(str(e))
                    if len(errors) > 10:
                        break  # Stop after too many errors

            # Build result message
            msg_parts = []
            if created_count:
                msg_parts.append(f"created {created_count}")
            if updated_count:
                msg_parts.append(f"updated {updated_count}")
            
            msg = f"Imported {len(features)} features from {layer}: " + ", ".join(msg_parts) + "."
            
            if errors:
                msg += f" ({len(errors)} errors)"
                logger.warning(f"Import errors for {dataset_key}: {errors[:5]}")
            
            return ImportResult("success", msg, created_count, updated_count)
            
        except requests.RequestException as e:
            return ImportResult("error", f"WFS request failed: {e}")
        except Exception as e:
            logger.exception(f"WFS import error for {dataset['key']}")
            return ImportResult("error", f"Import failed: {e}")

    # PDOK's mapserver-backed WCS endpoints cap a single GetCoverage response at
    # MAXSIZE=4000 pixels per dimension. AHN's 0.5m DEM/DSM coverages hit this on
    # anything bigger than a ~2km square, so a bbox that would exceed it gets
    # split into a grid of sub-requests and mosaicked back together below. Kept
    # a bit under 4000 as a safety margin for rounding.
    MAX_WCS_TILE_PIXELS = 3800

    # A mosaic bigger than this (total pixels across all tiles) reliably
    # crashes the local Postgres connection when GDALRaster sends it as a
    # single query parameter — observed: 16 tiles / ~230M px / ~285MB failed
    # with "server closed the connection unexpectedly"; 2 tiles / ~6.6M px /
    # ~15MB succeeded. Reject up front, before fetching anything, rather than
    # downloading the whole mosaic only to have the database connection die
    # on load.
    MAX_WCS_TOTAL_PIXELS = 16_000_000

    @staticmethod
    def _wcs_grid_edges(min_v: float, max_v: float, resolution_m: float) -> List[float]:
        """
        Split [min_v, max_v] into evenly-sized segments, each no larger than
        MAX_WCS_TILE_PIXELS at the given resolution, returning the tile
        boundary coordinates (n+1 edges for n tiles).
        """
        span = max_v - min_v
        pixel_count = span / resolution_m
        tile_count = max(1, math.ceil(pixel_count / PDOKImporter.MAX_WCS_TILE_PIXELS))
        step = span / tile_count
        return [min_v + i * step for i in range(tile_count + 1)]

    @staticmethod
    def fetch_wcs(dataset: Dict, bbox: list, resolution: float = 5.0) -> ImportResult:
        """
        Fetch raster data from PDOK WCS service, tiling the request when the
        area would exceed the service's per-request pixel cap and mosaicking
        the tiles back into a single GeoTIFF.
        """
        try:
            url = dataset.get("wcs_url", dataset["url"])
            layer = dataset["layer"]

            # bbox arrives in WGS84 from the frontend (city extent or a drawn
            # rectangle — see importer/views_external.py::get_cities_geojson).
            # The subset below has no CRS declaration, so WCS 2.0.1 interprets
            # it in the coverage's native CRS; for a CRS like AHN's RD New
            # (EPSG:28992), passing raw lon/lat numbers lands nowhere near the
            # actual coverage extent and PDOK returns an ExtentError. Reproject
            # to the coverage's CRS first, the same way fetch_wfs already does.
            request_bbox = bbox
            target_srs = dataset.get("params", {}).get("srsName", "EPSG:28992")
            target_epsg = int(target_srs.split(":")[-1])
            if target_epsg != 4326:
                tx = Transformer.from_crs("EPSG:4326", f"EPSG:{target_epsg}", always_xy=True)
                x1, y1 = tx.transform(bbox[0], bbox[1])
                x2, y2 = tx.transform(bbox[2], bbox[3])
                request_bbox = [x1, y1, x2, y2]

            resolution_m = dataset.get("resolution_m") or resolution
            x_edges = PDOKImporter._wcs_grid_edges(request_bbox[0], request_bbox[2], resolution_m)
            y_edges = PDOKImporter._wcs_grid_edges(request_bbox[1], request_bbox[3], resolution_m)

            total_width_px = (request_bbox[2] - request_bbox[0]) / resolution_m
            total_height_px = (request_bbox[3] - request_bbox[1]) / resolution_m
            total_pixels = total_width_px * total_height_px
            if total_pixels > PDOKImporter.MAX_WCS_TOTAL_PIXELS:
                max_side_km = (PDOKImporter.MAX_WCS_TOTAL_PIXELS ** 0.5) * resolution_m / 1000
                return ImportResult(
                    "error",
                    f"Selected area is too large for {layer} at {resolution_m}m resolution "
                    f"({len(x_edges) - 1}x{len(y_edges) - 1} tiles, ~{total_pixels / 1e6:.0f}M pixels). "
                    f"Please draw a smaller area — roughly {max_side_km:.1f}km x {max_side_km:.1f}km or less.",
                )

            temp_dir = Path(settings.MEDIA_ROOT) / "imports" / "pdok" / "rasters"
            temp_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            tile_paths = []
            total_bytes = 0
            for i in range(len(x_edges) - 1):
                for j in range(len(y_edges) - 1):
                    tile_bbox = [x_edges[i], y_edges[j], x_edges[i + 1], y_edges[j + 1]]
                    params = {
                        "service": "WCS",
                        "version": "2.0.1",
                        "request": "GetCoverage",
                        "CoverageId": layer,
                        "format": "image/tiff",
                        "subset": [
                            f"x({tile_bbox[0]},{tile_bbox[2]})",
                            f"y({tile_bbox[1]},{tile_bbox[3]})",
                        ],
                    }
                    logger.info(f"Fetching WCS tile ({i},{j}) of {len(x_edges)-1}x{len(y_edges)-1}: {url} coverage={layer}")
                    response = requests.get(url, params=params, timeout=300)
                    response.raise_for_status()

                    tile_path = temp_dir / f"{dataset['key']}_{timestamp}_tile{i}_{j}.tif"
                    with open(tile_path, 'wb') as f:
                        f.write(response.content)
                    tile_paths.append(tile_path)
                    total_bytes += len(response.content)

            filepath = temp_dir / f"{dataset['key']}_{timestamp}.tif"
            if len(tile_paths) == 1:
                tile_paths[0].rename(filepath)
            else:
                import rasterio
                from rasterio.merge import merge as rio_merge

                sources = [rasterio.open(p) for p in tile_paths]
                try:
                    mosaic, out_transform = rio_merge(sources)
                    out_meta = sources[0].meta.copy()
                    out_meta.update({
                        "height": mosaic.shape[1],
                        "width": mosaic.shape[2],
                        "transform": out_transform,
                    })
                    with rasterio.open(filepath, "w", **out_meta) as dst:
                        dst.write(mosaic)
                finally:
                    for src in sources:
                        src.close()
                    for p in tile_paths:
                        p.unlink(missing_ok=True)

            load_ok, load_msg = load_raster_into_target_model(str(filepath), dataset, bbox)

            tile_note = f", mosaicked from {len(tile_paths)} tiles" if len(tile_paths) > 1 else ""
            return ImportResult(
                "success" if load_ok else "error",
                f"Downloaded raster from {layer}{tile_note} ({total_bytes / 1024:.1f} KB). {load_msg}",
                1,
                0,
                str(filepath)
            )

        except requests.RequestException as e:
            return ImportResult("error", f"WCS request failed: {e}")
        except Exception as e:
            logger.exception(f"WCS import error for {dataset['key']}")
            return ImportResult("error", f"Import failed: {e}")

    @staticmethod
    def fetch_atom(dataset: Dict, bbox: list, max_tiles: int = 4) -> ImportResult:
        """
        Download raster tiles from PDOK ATOM feed.
        """
        try:
            from xml.etree import ElementTree as ET
            
            atom_url = dataset["url"]
            
            logger.info(f"Fetching ATOM feed: {atom_url}")
            response = requests.get(atom_url, timeout=60)
            response.raise_for_status()
            
            # Parse ATOM XML
            root = ET.fromstring(response.content)
            ns = {'atom': 'http://www.w3.org/2005/Atom', 'georss': 'http://www.georss.org/georss'}
            
            # Find entries with download links
            entries = root.findall('.//atom:entry', ns)
            
            if not entries:
                return ImportResult("error", "No entries found in ATOM feed.")
            
            # Filter by bbox intersection
            bbox_polygon = Polygon.from_bbox(bbox)
            matching_tiles = []
            
            for entry in entries:
                link_el = entry.find('atom:link[@rel="alternate"]', ns)
                if link_el is None:
                    continue
                
                tile_url = link_el.get('href')
                
                # Try to get georss:polygon or georss:box
                georss_box = entry.find('georss:box', ns)
                if georss_box is not None:
                    coords = georss_box.text.split()
                    if len(coords) == 4:
                        tile_bbox = [float(c) for c in coords]
                        tile_polygon = Polygon.from_bbox([tile_bbox[1], tile_bbox[0], tile_bbox[3], tile_bbox[2]])
                        if bbox_polygon.intersects(tile_polygon):
                            matching_tiles.append(tile_url)
                else:
                    # No georss info, include tile (can't filter)
                    matching_tiles.append(tile_url)
            
            if not matching_tiles:
                return ImportResult("success", "No tiles intersect the specified bounding box.", 0)
            
            # Limit number of tiles
            tiles_to_download = matching_tiles[:max_tiles]
            
            # Download tiles
            temp_dir = Path(settings.MEDIA_ROOT) / "imports" / "pdok" / "rasters"
            temp_dir.mkdir(parents=True, exist_ok=True)
            
            downloaded = []
            for tile_url in tiles_to_download:
                try:
                    tile_response = requests.get(tile_url, timeout=300)
                    tile_response.raise_for_status()
                    
                    tile_filename = tile_url.split('/')[-1]
                    tile_path = temp_dir / tile_filename
                    
                    with open(tile_path, 'wb') as f:
                        f.write(tile_response.content)
                    
                    downloaded.append(str(tile_path))
                except Exception as e:
                    logger.warning(f"Failed to download tile {tile_url}: {e}")
            
            if not downloaded:
                return ImportResult("error", "Failed to download any tiles.")
            
            return ImportResult(
                "success",
                f"Downloaded {len(downloaded)} of {len(matching_tiles)} tiles ({max_tiles} max).",
                len(downloaded),
                0,
                downloaded[0] if len(downloaded) == 1 else str(temp_dir)
            )
            
        except Exception as e:
            logger.exception(f"ATOM import error for {dataset['key']}")
            return ImportResult("error", f"ATOM import failed: {e}")

    @staticmethod
    def register_wms(dataset: Dict) -> ImportResult:
        """
        Register a WMS layer by creating/updating its row in the target WMS
        model. This used to just return a fake "success" message without
        writing anything — the map only shows a WMS layer if a row exists
        for it (mainMap/views.py::available_layers queries WMS_REGISTRY
        models via .objects.all()), so no WMS dataset selected in the
        importer ever actually appeared on the map.
        """
        layer = dataset.get("layer", "unknown")
        url = dataset["url"]
        model_path = dataset["target_model"]

        try:
            Model = get_model_class(model_path)
        except ValueError as e:
            return ImportResult("error", str(e))

        obj, created = Model.objects.update_or_create(
            name=dataset["key"],
            defaults={
                "display_name": dataset.get("name", layer),
                "url": url,
                "layers_param": layer,
                "legend_url": dataset.get("legend_url") or default_wms_legend_url(url, layer),
                "is_active": True,
            },
        )

        return ImportResult(
            "success",
            f"WMS layer {'registered' if created else 'updated'}: {layer}.",
            1,
            0,
        )

class CBSImporter:
    """Import handler for CBS StatLine OData datasets."""
    
    BASE_URL_API  = "https://opendata.cbs.nl/ODataApi/OData/{table_id}"
    BASE_URL_FEED = "https://opendata.cbs.nl/ODataFeed/OData/{table_id}"
    
    @staticmethod
    def fetch(
    dataset: Dict,
    date_from: Optional[str] = None,   # ISO date or year, e.g. "2020-01-01" or "2020"
    date_to: Optional[str] = None,     # ISO date or year, e.g. "2023-12-31" or "2023"
    bbox: Optional[list] = None,       # [xmin, ymin, xmax, ymax] in WGS84
    ) -> ImportResult:
        """
        Fetch tabular data from CBS OData API and import to Django model.

        Args:
            dataset:   Catalog entry dict
            date_from: Start date/year, e.g. "2020-01-01" or "2020"
            date_to:   End date/year, e.g. "2023-12-31" or "2023"
            bbox:      WGS84 bounding box; used to restrict results to municipalities
                       (RegioS) whose City geometry intersects it. CBS data is tabular,
                       so this filters by administrative region rather than clipping geometry.
        """
        try:
            table_id    = dataset["table_id"]
            model_path  = dataset["target_model"]
            dataset_key = dataset["key"]

            mapping = FIELD_MAPPINGS.get(dataset_key)
            if not mapping:
                return ImportResult("error", f"No field mapping defined for {dataset_key}")

            try:
                Model = get_model_class(model_path)
            except ValueError as e:
                return ImportResult("error", str(e))

            use_feed = dataset.get("params", {}).get("use_feed", False)
            base = CBSImporter.BASE_URL_FEED if use_feed else CBSImporter.BASE_URL_API
            url  = f"{base.format(table_id=table_id)}/TypedDataSet"

            # Build $filter — merge dataset-level filter with date range
            filter_parts = []

            dataset_filter = dataset.get("params", {}).get("filter")
            if dataset_filter:
                filter_parts.append(dataset_filter)

            # CBS annual period codes look like "2023JJ00"
            # Use startswith on the year prefix for a safe range filter.
            # date_from/date_to arrive as full ISO dates (e.g. "2026-08-01") from the
            # date-range picker, so only the leading 4-digit year is relevant to CBS.
            year_from = date_from[:4] if date_from else None
            year_to = date_to[:4] if date_to else None

            if year_from and year_to:
                year_filters = " or ".join(
                    f"startswith(Perioden,'{y}')"
                    for y in range(int(year_from), int(year_to) + 1)
                )
                filter_parts.append(f"({year_filters})")
            elif year_from:
                filter_parts.append(f"startswith(Perioden,'{year_from}')")
            elif year_to:
                filter_parts.append(f"startswith(Perioden,'{year_to}')")

            # Restrict to municipalities intersecting the selected bbox, if provided.
            # CBS RegioS codes are "GM" + the gemeente number, and City.pk is that
            # same gemeente number (see the RegioS -> City FK resolution below).
            if bbox:
                from common.models import City

                bbox_geom = Polygon.from_bbox(bbox)
                bbox_geom.srid = 4326
                bbox_geom.transform(coordinate_system)
                # Reprojecting a WGS84 rectangle's corners into EPSG:28992 doesn't yield an
                # exact axis-aligned box, so a city extent that is nominally "within" the
                # original bbox can end up a hair outside it. A small buffer (meters, since
                # we're in a projected CRS) absorbs that reprojection noise.
                bbox_geom = bbox_geom.buffer(1)
                print(f"Filtering CBS data to cities within bbox {bbox_geom.extent} (EPSG:{coordinate_system})")

                city_pks = list(
                    City.objects.filter(geom__intersects=bbox_geom).values_list("pk", flat=True)
                )
                if not city_pks:
                    return ImportResult("success", "No cities found within the selected area.", 0)

                region_filters = " or ".join(f"startswith(RegioS,'GM{pk:04d}')" for pk in city_pks)
                filter_parts.append(f"({region_filters})")

            params = {"$format": "json"}
            if filter_parts:
                params["$filter"] = " and ".join(filter_parts)

            select_fields = dataset.get("params", {}).get("select")
            if select_fields:
                params["$select"] = ",".join(select_fields)

            logger.info(f"Fetching CBS OData: table={table_id} filter={params.get('$filter', 'none')}")

            # Paginate
            all_rows = []
            next_url = url

            while next_url:
                response = requests.get(next_url, params=params, timeout=120)
                response.raise_for_status()
                data = response.json()
                all_rows.extend(data.get("value", []))
                next_url = data.get("odata.nextLink") or data.get("@odata.nextLink")
                params = {}

            if not all_rows:
                return ImportResult("success", "No rows returned from CBS.", 0)
            
            # Import rows
            unique_cbs_field   = mapping.get("__unique__")
            unique_model_field = mapping.get("__unique_field__")
            unique_composite   = mapping.get("__unique_fields__")  # e.g. ["city", "year"]

            # Transform config: extract year from Perioden, resolve City FK from RegioS
            year_source = mapping.get("__year_source__")
            year_field  = mapping.get("__year_field__")
            city_source = mapping.get("__city_source__")
            city_field  = mapping.get("__city_field__")

            # Pre-fetch city lookup cache if needed
            city_cache = {}
            if city_source and city_field:
                from django.apps import apps as django_apps
                City = django_apps.get_model("common", "City")
                city_cache = {c.pk: c for c in City.objects.all()}

            created_count = updated_count = 0
            errors = []

            with transaction.atomic():
                for row in all_rows:
                    try:
                        field_values = {}

                        for cbs_col, model_field in mapping.items():
                            if cbs_col.startswith("__"):
                                continue
                            value = row.get(cbs_col)
                            if value is not None:
                                # Strip trailing spaces common in CBS region codes
                                if isinstance(value, str):
                                    value = value.strip()
                                field_values[model_field] = value

                        # Extract year from Perioden (e.g. "2023KW04" → 2023)
                        if year_source and year_field:
                            period = str(row.get(year_source, "")).strip()
                            if len(period) >= 4:
                                field_values[year_field] = int(period[:4])
                            else:
                                continue  # skip rows without a valid period

                        # Resolve City FK from RegioS (e.g. "GM0363  " → City pk=363)
                        if city_source and city_field:
                            region = str(row.get(city_source, "")).strip()
                            gm_code = region.replace("GM", "")
                            try:
                                city_pk = int(gm_code)
                            except ValueError:
                                errors.append(f"Invalid GM code: {region}")
                                continue
                            city_obj = city_cache.get(city_pk)
                            if not city_obj:
                                continue  # city not imported yet, skip
                            field_values[city_field] = city_obj

                        if not field_values:
                            continue

                        # Determine dedup strategy
                        if unique_composite:
                            # Composite unique: e.g. lookup by (city, year)
                            lookup = {f: field_values[f] for f in unique_composite if f in field_values}
                            defaults = {k: v for k, v in field_values.items() if k not in unique_composite}
                            obj, was_created = Model.objects.update_or_create(
                                **lookup, defaults=defaults
                            )
                            created_count += was_created
                            updated_count += not was_created
                        elif unique_cbs_field and unique_model_field:
                            raw_key = row.get(unique_cbs_field, "")
                            lookup  = {unique_model_field: raw_key.strip() if isinstance(raw_key, str) else raw_key}
                            defaults = {k: v for k, v in field_values.items() if k != unique_model_field}
                            obj, was_created = Model.objects.update_or_create(
                                **lookup, defaults=defaults
                            )
                            created_count += was_created
                            updated_count += not was_created
                        else:
                            Model.objects.create(**field_values)
                            created_count += 1

                    except Exception as e:
                        errors.append(str(e))
                        if len(errors) > 10:
                            break
            
            msg = f"Imported {len(all_rows)} rows from CBS {table_id}: created {created_count}, updated {updated_count}."
            if errors:
                msg += f" ({len(errors)} errors)"
                logger.warning(f"CBS import errors for {dataset_key}: {errors[:5]}")
            
            return ImportResult("success", msg, created_count, updated_count)
        
        except requests.RequestException as e:
            return ImportResult("error", f"CBS OData request failed: {e}")
        except Exception as e:
            logger.exception(f"CBS import error for {dataset['key']}")
            return ImportResult("error", f"Import failed: {e}")
    
    @staticmethod
    def get_metadata(table_id: str) -> Dict:
        """
        Fetch column definitions and units for a CBS table.
        Useful for building field mappings.
        """
        url = f"https://opendata.cbs.nl/ODataApi/OData/{table_id}/DataProperties"
        response = requests.get(url, params={"$format": "json"}, timeout=30)
        response.raise_for_status()
        return response.json().get("value", [])

class Sentinel2Importer:
    """Import handler for Sentinel-2 datasets."""

    # Band sets for each spectral index/composite, fetched from the
    # SENTINEL2_L2A collection and combined in fetch_openeo(). These replace
    # the old Sentinel Hub Process API evalscripts (Sentinel Hub's on-demand
    # processing is now a paid tier) with equivalent openEO band math run on
    # the Copernicus Data Space Ecosystem's free openEO backend — see
    # https://documentation.dataspace.copernicus.eu/APIs/openEO/Python_Client/Python.html
    OPENEO_BANDS = {
        "NDVI": ["B04", "B08"],
        "NDWI": ["B03", "B08"],
        "MOISTURE_INDEX": ["B8A", "B11"],
        "TRUE_COLOR": ["B04", "B03", "B02"],
         ## -------- CONSIDER ADDING MORE INDICES HERE --------
                    ## -------- CONSIDER ADDING FUNCTIONS OF EXTERNAL PROCESSING LIBRARIES (e.g., scikit-image, landcover ML, RF, etc) --------
    }

    @staticmethod
    def _lookup_acquisition_date(bbox: list, date_from: str, date_to: str, max_cloud_cover: float = 85.0) -> Optional[datetime]:
        """
        Look up the real acquisition timestamp of the most recent Sentinel-2
        L2A scene matching the requested area/date range/cloud filter, via
        Copernicus Data Space's public OData catalog (no auth needed for
        search). The openEO composite downloaded in fetch_openeo() carries
        no acquisition timestamp of its own — confirmed empty GDAL tags on a
        real download — so without this, imports were dated by the search
        window or the import time instead of when the satellite actually
        captured the data.
        """
        try:
            poly = (
                f"POLYGON(({bbox[0]} {bbox[1]},{bbox[2]} {bbox[1]},"
                f"{bbox[2]} {bbox[3]},{bbox[0]} {bbox[3]},{bbox[0]} {bbox[1]}))"
            )
            filter_str = (
                "Collection/Name eq 'SENTINEL-2' "
                f"and OData.CSC.Intersects(area=geography'SRID=4326;{poly}') "
                f"and ContentDate/Start gt {date_from}T00:00:00.000Z "
                f"and ContentDate/Start lt {date_to}T23:59:59.999Z "
                "and contains(Name,'MSIL2A') "
                "and Attributes/OData.CSC.DoubleAttribute/any("
                f"att:att/Name eq 'cloudCover' and att/OData.CSC.DoubleAttribute/Value lt {max_cloud_cover})"
            )
            resp = requests.get(
                "https://catalogue.dataspace.copernicus.eu/odata/v1/Products",
                params={"$filter": filter_str, "$orderby": "ContentDate/Start desc", "$top": 1},
                timeout=20,
            )
            resp.raise_for_status()
            products = resp.json().get("value", [])
            if not products:
                return None
            start = products[0]["ContentDate"]["Start"]  # e.g. "2026-09-06T10:46:21.025000Z"
            return datetime.strptime(start[:19], "%Y-%m-%dT%H:%M:%S")
        except Exception as e:
            logger.warning(f"Could not look up Sentinel-2 acquisition date for bbox={bbox}: {e}")
            return None

    @staticmethod
    def fetch_wcs(dataset: Dict, bbox: list) -> ImportResult:
        """Fetch raster from Sentinel-2 WCS (e.g., WorldCover)."""
        try:
            url = dataset.get("wcs_url", dataset["url"])
            layer = dataset["layer"]
            
            params = {
                "service": "WCS",
                "version": "2.0.1",
                "request": "GetCoverage",
                "CoverageId": layer,
                "format": "image/tiff",
                "subset": [
                    f"Lat({bbox[1]},{bbox[3]})",
                    f"Long({bbox[0]},{bbox[2]})",
                ],
            }
            
            logger.info(f"Fetching Sentinel-2 WCS: {url}")
            response = requests.get(url, params=params, timeout=300)
            response.raise_for_status()
            
            temp_dir = Path(settings.MEDIA_ROOT) / "imports" / "sentinel2"
            temp_dir.mkdir(parents=True, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{dataset['key']}_{timestamp}.tif"
            filepath = temp_dir / filename
            
            with open(filepath, 'wb') as f:
                f.write(response.content)

            loaded, load_msg = load_raster_into_target_model(str(filepath), dataset, bbox)

            return ImportResult(
                "success",
                f"Downloaded {layer} ({len(response.content) / 1024:.1f} KB). {load_msg}",
                1,
                0,
                str(filepath)
            )

        except Exception as e:
            logger.exception(f"Sentinel-2 WCS error for {dataset['key']}")
            return ImportResult("error", f"WCS request failed: {e}")

    @staticmethod
    def fetch_openeo(
        dataset: Dict,
        bbox: list,
        date_from: str = None,
        date_to: str = None,
        client_id: str = None,
        client_secret: str = None,
    ) -> ImportResult:
        """
        Fetch processed Sentinel-2 imagery via the Copernicus Data Space
        Ecosystem's openEO backend. Replaces the (now paid) Sentinel Hub
        Process API — auth is a CDSE OIDC client_id/client_secret pair
        (client-credentials grant), not a single bearer token; see
        https://documentation.dataspace.copernicus.eu/APIs/openEO/authentication/client_credentials.html
        """
        try:
            import openeo
        except ImportError:
            return ImportResult("error", "openeo package not installed. Run: pip install openeo")

        # Fall back to the default CDSE service credentials from .env
        # (SENTINEL_CLIENT_ID/SENTINEL_CLIENT_SECRET) when the caller didn't
        # supply its own — most requests shouldn't need to ask the user for
        # anything. Only if those defaults fail to authenticate do we tell the
        # caller to prompt for personal credentials instead.
        used_default_credentials = False
        if not client_id or not client_secret:
            client_id = client_id or settings.SENTINEL_CLIENT_ID
            client_secret = client_secret or settings.SENTINEL_CLIENT_SECRET
            used_default_credentials = True

        if not client_id or not client_secret:
            return ImportResult(
                "error",
                "openEO requires a Copernicus Data Space client_id and client_secret.",
                needs_credentials=True,
            )

        index_key = dataset.get("openeo_process", "TRUE_COLOR")
        bands = Sentinel2Importer.OPENEO_BANDS.get(index_key)
        if not bands:
            return ImportResult("error", f"Unknown openEO process: {index_key}")

        # Default date range: last 30 days
        if not date_from:
            date_from = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        if not date_to:
            date_to = datetime.now().strftime("%Y-%m-%d")

        try:
            connection = openeo.connect(dataset.get("url", "https://openeo.dataspace.copernicus.eu"))
            connection.authenticate_oidc_client_credentials(client_id=client_id, client_secret=client_secret)
        except Exception as e:
            logger.warning(f"openEO authentication failed for {dataset['key']} (default_creds={used_default_credentials}): {e}")
            if used_default_credentials:
                return ImportResult(
                    "error",
                    "The default Copernicus Data Space credentials failed to authenticate. "
                    "Please enter your own openEO client ID and client secret.",
                    needs_credentials=True,
                )
            return ImportResult("error", f"openEO authentication failed: {e}", needs_credentials=True)

        try:
            datacube = connection.load_collection(
                "SENTINEL2_L2A",
                spatial_extent={"west": bbox[0], "south": bbox[1], "east": bbox[2], "north": bbox[3]},
                temporal_extent=[date_from, date_to],
                bands=bands,
                max_cloud_cover=85,
            )

            if index_key == "NDVI":
                red, nir = datacube.band("B04"), datacube.band("B08")
                result_cube = (nir - red) / (nir + red)
            elif index_key == "NDWI":
                green, nir = datacube.band("B03"), datacube.band("B08")
                result_cube = (green - nir) / (green + nir)
            elif index_key == "MOISTURE_INDEX":
                nir_narrow, swir = datacube.band("B8A"), datacube.band("B11")
                result_cube = (nir_narrow - swir) / (nir_narrow + swir)
            ## -------- CONSIDER ADDING MORE INDICES HERE --------
            ## -------- CONSIDER ADDING FUNCTIONS OF EXTERNAL PROCESSING LIBRARIES (e.g., scikit-image, landcover ML, RF, etc) --------
            else:  # TRUE_COLOR
                result_cube = datacube * 2.5

            # Composite the time series down to a single raster — mirrors the
            # old Process API's leastCC mosaicking closely enough for a preview layer.
            result_cube = result_cube.reduce_dimension(dimension="t", reducer="mean")

            temp_dir = Path(settings.MEDIA_ROOT) / "imports" / "sentinel2"
            temp_dir.mkdir(parents=True, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{dataset['key']}_{timestamp}.tif"
            filepath = temp_dir / filename

            logger.info(f"Fetching Sentinel-2 via openEO: {index_key}")

            # The synchronous /result download is a single long-lived request
            # while CDSE computes the whole thing server-side, and its gateway
            # will sometimes reset the connection mid-response with no HTTP
            # error at all (requests.exceptions.ConnectionError /
            # RemoteDisconnected) — this is a known flaky-gateway behavior, not
            # a sign the request itself is wrong, so retry a few times before
            # giving up.
            max_attempts = 3
            last_error = None
            for attempt in range(1, max_attempts + 1):
                try:
                    result_cube.download(str(filepath))
                    last_error = None
                    break
                except Exception as e:
                    last_error = e
                    if attempt < max_attempts:
                        logger.warning(
                            f"[{dataset['key']}] openEO download attempt {attempt}/{max_attempts} "
                            f"failed ({e}); retrying..."
                        )
                        time.sleep(5 * attempt)
            if last_error:
                raise last_error

            acquisition_date = Sentinel2Importer._lookup_acquisition_date(bbox, date_from, date_to)
            loaded, load_msg = load_raster_into_target_model(
                str(filepath), dataset, bbox, date_to, acquisition_date=acquisition_date
            )

            return ImportResult(
                "success",
                f"Downloaded {index_key} for {date_from} to {date_to} via openEO. {load_msg}",
                1,
                0,
                str(filepath)
            )

        except Exception as e:
            logger.exception(f"Sentinel-2 openEO error for {dataset['key']}")
            return ImportResult(
                "error",
                f"openEO request failed after retries: {e}. The CDSE backend may be under load — try again, "
                f"or narrow the bounding box / date range.",
            )

    @staticmethod
    def register_wms(dataset: Dict) -> ImportResult:
        """
        Register a Sentinel-2 WMS layer by creating/updating its row in the
        target WMS model — see PDOKImporter.register_wms for why this needs
        to actually write to the DB rather than just report success.
        """
        layer = dataset.get("layer", "unknown")
        url = dataset["url"]
        model_path = dataset["target_model"]

        try:
            Model = get_model_class(model_path)
        except ValueError as e:
            return ImportResult("error", str(e))

        obj, created = Model.objects.update_or_create(
            name=dataset["key"],
            defaults={
                "display_name": dataset.get("name", layer),
                "url": url,
                "layers_param": layer,
                "legend_url": dataset.get("legend_url") or default_wms_legend_url(url, layer),
                "is_active": True,
            },
        )

        return ImportResult(
            "success",
            f"WMS layer {'registered' if created else 'updated'}: {layer}.",
            1,
            0,
        )


class GEEImporter:
    """Import handler for Google Earth Engine datasets."""
    
    @staticmethod
    def export_raster(
        dataset: Dict,
        bbox: list,
        date_from: str = None,
        date_to: str = None
    ) -> ImportResult:
        """
        Export raster from GEE to local GeoTIFF.
        """
        try:
            import ee
            
            if not GEEAuthManager.is_initialized():
                return ImportResult("error", "GEE not authenticated. Please provide credentials.")
            
            asset_id = dataset.get("asset_id")
            band = dataset.get("band")
            
            if not asset_id:
                return ImportResult("error", "No asset_id specified for GEE dataset.")
            
            # Define region
            region = ee.Geometry.Rectangle(bbox)
            
            # Load image or image collection
            acquisition_date = None
            try:
                # Try as ImageCollection first
                collection = ee.ImageCollection(asset_id)

                # Apply date filter if needed
                if date_from and date_to:
                    collection = collection.filterDate(date_from, date_to)

                # Filter by region
                collection = collection.filterBounds(region)

                # Real acquisition timestamp of the most recent scene that
                # actually contributes to the composite below, rather than
                # the requested search window or the import time — GEE
                # already carries this on every image (system:time_start),
                # so no extra catalog lookup is needed, just one lightweight
                # getInfo() call for the scalar value.
                try:
                    latest = collection.sort('system:time_start', False).first()
                    millis = latest.get('system:time_start').getInfo()
                    if millis:
                        acquisition_date = datetime.utcfromtimestamp(millis / 1000)
                except Exception as e:
                    logger.warning(f"Could not look up GEE acquisition date for {asset_id}: {e}")

                # Composite (mean)
                image = collection.mean()

            except Exception:
                # Fall back to single Image
                image = ee.Image(asset_id)
            
            # Select band if specified
            if band:
                image = image.select(band)
            
            # Clip to region
            image = image.clip(region)
            
            # Get download URL
            url = image.getDownloadURL({
                'scale': 30,
                'region': region,
                'format': 'GEO_TIFF',
                'crs': 'EPSG:4326'
            })
            
            logger.info(f"Downloading GEE raster from: {url[:100]}...")
            response = requests.get(url, timeout=300)
            response.raise_for_status()
            
            # Save to file
            temp_dir = Path(settings.MEDIA_ROOT) / "imports" / "gee"
            temp_dir.mkdir(parents=True, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{dataset['key']}_{timestamp}.tif"
            filepath = temp_dir / filename
            
            with open(filepath, 'wb') as f:
                f.write(response.content)

            loaded, load_msg = load_raster_into_target_model(
                str(filepath), dataset, bbox, date_to, acquisition_date=acquisition_date
            )

            return ImportResult(
                "success",
                f"Downloaded {band or asset_id} ({len(response.content) / 1024:.1f} KB). {load_msg}",
                1,
                0,
                str(filepath)
            )

        except ImportError:
            return ImportResult("error", "earthengine-api not installed.")
        except Exception as e:
            logger.exception(f"GEE export error for {dataset['key']}")
            return ImportResult("error", f"GEE export failed: {e}")


def import_dataset(
    dataset_key: str,
    bbox: Optional[list] = None,
    date_from: str = None,
    date_to: str = None,
    gee_credentials: str = None,
    openeo_client_id: str = None,
    openeo_client_secret: str = None,
) -> ImportResult:
    """
    Main dispatcher for importing a dataset.

    Args:
        dataset_key: Key from EXTERNAL_DATA_CATALOG
        bbox: Bounding box [xmin, ymin, xmax, ymax]
        date_from: Start date for temporal datasets
        date_to: End date for temporal datasets
        gee_credentials: GEE service account JSON (for GEE sources)
        openeo_client_id: CDSE OIDC client id (for Sentinel-2 openEO datasets)
        openeo_client_secret: CDSE OIDC client secret (for Sentinel-2 openEO datasets)

    Returns:
        ImportResult with status and details
    """
    if dataset_key not in CATALOG_BY_KEY:
        return ImportResult("error", f"Unknown dataset: {dataset_key}")
    
    dataset = CATALOG_BY_KEY[dataset_key]
    
    # Check if enabled
    if not dataset.get("enabled", True):
        return ImportResult("skipped", "Dataset is not yet enabled.")
    
    # Check bbox requirement
    if dataset.get("requires_bbox") and not bbox:
        return ImportResult("skipped", "This dataset requires a bounding box.")
    
    # Initialize GEE if needed
    if dataset["source"] == "gee":
        if gee_credentials:
            success, msg = GEEAuthManager.initialize(gee_credentials)
            if not success:
                return ImportResult("error", msg)
        elif not GEEAuthManager.is_initialized():
            return ImportResult("error", "GEE requires authentication. Please provide service account JSON.")
    
    # Dispatch based on source and format
    source = dataset["source"]
    fmt = dataset.get("format", "wfs")
    
    print(f"[DISPATCH] import_dataset: dataset_key={dataset_key} bbox={bbox} date_from={date_from} date_to={date_to}")
    if source in ("pdok", "rivm") or (source == "CBS" and fmt == "wfs"):

        if fmt == "wfs":
            return PDOKImporter.fetch_wfs(dataset, bbox)
        elif fmt == "wcs":
            return PDOKImporter.fetch_wcs(dataset, bbox)
        elif fmt == "wms":
            return PDOKImporter.register_wms(dataset)
        elif fmt == "atom":
            return PDOKImporter.fetch_atom(dataset, bbox)

    elif source == "CBS" and fmt == "odata":
        return CBSImporter.fetch(dataset, date_from, date_to, bbox)
    
    elif source == "sentinel2":
        if fmt == "wcs":
            return Sentinel2Importer.fetch_wcs(dataset, bbox)
        elif fmt == "openeo":
            return Sentinel2Importer.fetch_openeo(
                dataset, bbox, date_from, date_to, openeo_client_id, openeo_client_secret
            )
        elif fmt == "wms":
            return Sentinel2Importer.register_wms(dataset)
    
    elif source == "gee":
        return GEEImporter.export_raster(dataset, bbox, date_from, date_to)
    
    return ImportResult("error on EXTERNAL_DATA", f"No handler for source={source}, format={fmt}")
