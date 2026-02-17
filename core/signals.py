from django.db.models.signals import post_save
from django.dispatch import receiver
from core.utils import RASTER_REGISTRY as RasterLayer
from core.rasterOperations import export_raster_to_cog


@receiver(post_save, sender=RasterLayer)
def auto_export_cog(sender, instance, created, **kwargs):
    """Automatically create a COG when a new raster is added."""
    if created and not instance.cog_path:
        try:
            export_raster_to_cog(instance)
            print(f"✅COG exported for {instance.name}")
        except Exception as e:
            print(f"⚠️Warning: COG export failed for {instance.name}: {e}")