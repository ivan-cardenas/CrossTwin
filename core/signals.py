from django.db.models.signals import post_save
from django.dispatch import receiver
from core.utils import RASTER_REGISTRY
from core.rasterOperations import export_raster_to_cog


def auto_export_cog(sender, instance, created, **kwargs):
    """Automatically create a COG when a new raster is added."""
    print(f"🔔 Signal fired! created={created}, sender={sender.__name__}")
    if not instance.cog_path:
        try:
            export_raster_to_cog(instance)
            print(f"✅ COG exported for {instance}")
        except Exception as e:
            print(f"⚠️ Warning: COG export failed for {instance}: {e}")


# Connect the signal to EVERY raster model in the registry
for label, model_class in RASTER_REGISTRY.items():
    post_save.connect(auto_export_cog, sender=model_class)
    print(f"📡 Signal registered for: {label}")