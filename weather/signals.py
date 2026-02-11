from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.db import connection

def create_raster_view(raster_instance):
    """Create a database view for a single raster"""
    model_name = raster_instance.__class__.__name__.lower()
    table_name = raster_instance._meta.db_table
    view_name = f"view_{model_name}_{raster_instance.id}"
    
    # Create a friendly display name
    display_name = f"{raster_instance.name} ({raster_instance.date})"
    
    sql = f"""
        CREATE OR REPLACE VIEW {view_name} AS
        SELECT 
            id,
            '{display_name}'::varchar as display_name,
            name,
            date,
            raster,
            bounds,
            resolution_m,
            interpolation_method,
            created_at
        FROM {table_name}
        WHERE id = {raster_instance.id};
        
        COMMENT ON VIEW {view_name} IS '{display_name}';
    """
    
    with connection.cursor() as cursor:
        cursor.execute(sql)
    
    return view_name

def create_latest_view(model_class):
    """Create a view that always shows the latest raster"""
    model_name = model_class.__name__.lower()
    table_name = model_class._meta.db_table
    view_name = f"view_{model_name}_latest"
    
    sql = f"""
        CREATE OR REPLACE VIEW {view_name} AS
        SELECT 
            id,
            name || ' (LATEST)' as display_name,
            name,
            date,
            raster,
            bounds,
            resolution_m,
            interpolation_method,
            created_at
        FROM {table_name}
        ORDER BY date DESC, created_at DESC
        LIMIT 1;
        
        COMMENT ON VIEW {view_name} IS 'Latest {model_class._meta.verbose_name}';
    """
    
    with connection.cursor() as cursor:
        cursor.execute(sql)

def delete_raster_view(raster_instance):
    """Delete the view when a raster is deleted"""
    model_name = raster_instance.__class__.__name__.lower()
    view_name = f"view_{model_name}_{raster_instance.id}"
    
    sql = f"DROP VIEW IF EXISTS {view_name};"
    
    with connection.cursor() as cursor:
        cursor.execute(sql)

# Register signals for all your raster models
from weather.models import TemperatureRaster, PrecipitationRaster, HumidityRaster

@receiver(post_save, sender=TemperatureRaster)
@receiver(post_save, sender=PrecipitationRaster)
@receiver(post_save, sender=HumidityRaster)
def on_raster_saved(sender, instance, created, **kwargs):
    """Automatically create/update view when raster is saved"""
    create_raster_view(instance)
    create_latest_view(sender)

@receiver(post_delete, sender=TemperatureRaster)
@receiver(post_delete, sender=PrecipitationRaster)
@receiver(post_delete, sender=HumidityRaster)
def on_raster_deleted(sender, instance, **kwargs):
    """Automatically delete view when raster is deleted"""
    delete_raster_view(instance)
    create_latest_view(sender)  # Update the latest view