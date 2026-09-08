from django.db.models.signals import post_save
from django.dispatch import receiver
from core.utils import RASTER_REGISTRY
from core.rasterOperations import export_raster_to_cog


def auto_export_cog(sender, instance, created, **kwargs):
    """Automatically create a COG when a new raster is added."""
    # Plain ASCII only: this runs inside post_save, so an exception here
    # (e.g. UnicodeEncodeError printing an emoji on a Windows cp1252 console)
    # propagates out of save() itself and rolls back the object being saved.
    print(f"[auto_export_cog] signal fired: created={created}, sender={sender.__name__}")

    # Models flagged SKIP_RASTER_DB_STORAGE never get a raster written into
    # Postgres in the first place (see importer/external_data.py::
    # load_raster_into_target_model) — export_raster_to_cog would read a
    # NULL raster column here and always fail. Those models' COG is produced
    # directly from the source file by export_geotiff_to_cog instead.
    if getattr(sender, 'SKIP_RASTER_DB_STORAGE', False):
        return

    if not getattr(instance, 'cog_path', None):
        try:
            export_raster_to_cog(instance)
            print(f"[auto_export_cog] COG exported for {instance}")
        except Exception as e:
            print(f"[auto_export_cog] WARNING: COG export failed for {instance}: {e}")


# Connect the signal to EVERY raster model in the registry
for label, model_class in RASTER_REGISTRY.items():
    post_save.connect(auto_export_cog, sender=model_class)

