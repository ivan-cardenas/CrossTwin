import logging
import os

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from core.cache import bump_layer_version
from core.utils import RASTER_REGISTRY, VECTOR_REGISTRY
# core.rasterOperations (numpy, scipy, rasterio, rio-cogeo) is imported inside
# auto_export_cog: this module loads at startup of every process (server,
# tests, every manage.py command), and that import alone took ~1.6 s.

logger = logging.getLogger(__name__)


def _say(text):
    """
    One console line about the COG export, e.g.
        [cog]    LandSurfaceTemperature id=3: exporting (new raster) ...
    This runs inside post_save, where an exception rolls back the raster's own
    save, so the text is forced to ASCII (a Windows cp1252 console can't
    print every character a name may hold). Warnings also go to `logger`.
    """
    print(f"[cog]    {text}".encode("ascii", "replace").decode("ascii"), flush=True)


def auto_export_cog(sender, instance, created, raw=False, update_fields=None, **kwargs):
    """(Re)create the COG whenever a raster row is saved, so the map never shows a stale one."""
    # The export itself saves update_fields=['cog_path']; skip that save.
    if update_fields is not None and set(update_fields) == {'cog_path'}:
        return
    # A fixture/restore row that already has its COG file keeps it
    if raw and getattr(instance, 'cog_path', None):
        return

    # Models flagged SKIP_RASTER_DB_STORAGE never get a raster written into
    # Postgres in the first place (see importer/external_data.py::
    # load_raster_into_target_model) — export_raster_to_cog would read a
    # NULL raster column here and always fail. Those models' COG is produced
    # directly from the source file by export_geotiff_to_cog instead.
    if getattr(sender, 'SKIP_RASTER_DB_STORAGE', False):
        return

    # A re-import updates the row in place (update_or_create, upsert keys):
    # the raster changed but cog_path is still set, so export again. The
    # file name carries metadata (e.g. the date), so it can change; remove
    # the old file then.
    old_path = getattr(instance, 'cog_path', None)
    label = f"{sender.__name__} id={instance.pk}"
    _say(f"{label}: exporting ({'new raster' if created else 'raster updated, replacing its COG'}) ...")
    try:
        from core.rasterOperations import export_raster_to_cog
        export_raster_to_cog(instance)
    except Exception as e:
        # Never raise here: it would roll back the save of the raster itself
        logger.warning("COG export failed for %s: %s", instance, e)
        _say(f"{label}: WARNING export failed, the map keeps the old image ({e})")
        return
    _say(f"{label}: ready -> {instance.cog_path}")
    if old_path and old_path != instance.cog_path and os.path.exists(old_path):
        try:
            os.unlink(old_path)
            _say(f"{label}: removed the previous file {old_path}")
        except OSError as e:
            logger.warning("Could not delete old COG %s: %s", old_path, e)
            _say(f"{label}: WARNING could not remove the previous file {old_path} ({e})")


# Connect the signal to EVERY raster model in the registry
for label, model_class in RASTER_REGISTRY.items():
    post_save.connect(auto_export_cog, sender=model_class)


# Saves through the concrete model (e.g. builtup.Property) send it as sender,
# so the proxy layers on its table (housing.ResidentialProperty) are bumped too.
_PROXY_LAYERS = {}
for model_class in VECTOR_REGISTRY.values():
    if model_class._meta.proxy:
        _PROXY_LAYERS.setdefault(model_class._meta.concrete_model, []).append(model_class)


def invalidate_layer_cache(sender, **kwargs):
    """Orphan the cached GeoJSON of a vector layer whenever one of its rows changes."""
    bump_layer_version(sender, *_PROXY_LAYERS.get(sender, ()))


# weak=False: the receiver is a module-level function, but keep a strong
# reference anyway so it can't be collected if this module is reloaded.
for label, model_class in VECTOR_REGISTRY.items():
    post_save.connect(invalidate_layer_cache, sender=model_class, weak=False,
                      dispatch_uid=f"layer_cache_save_{label}")
    post_delete.connect(invalidate_layer_cache, sender=model_class, weak=False,
                        dispatch_uid=f"layer_cache_delete_{label}")

