from django.core.management.base import BaseCommand
from core.rasterOperations import export_raster_to_cog
from core.utils import RASTER_REGISTRY  # adjust import path


class Command(BaseCommand):
    help = 'Export PostGIS rasters to Cloud Optimized GeoTIFFs'

    def add_arguments(self, parser):
        parser.add_argument(
            '--model',
            type=str,
            help='Export rasters from a specific model (e.g. "urbanHeat.LandSurfaceTemp")'
        )
        parser.add_argument(
            '--id',
            type=int,
            help='Export a specific raster by its ID'
        )
        parser.add_argument(
            '--list',
            action='store_true',
            help='List all available raster models'
        )

    def handle(self, *args, **options):
        
        # Just list available models
        if options['list']:
            self.stdout.write("Available raster models:")
            for key in RASTER_REGISTRY:
                model = RASTER_REGISTRY[key]
                count = model.objects.count()
                self.stdout.write(f"  {key} ({count} records)")
            return

        # Export a specific model + id
        if options['model']:
            model_key = options['model']
            if model_key not in RASTER_REGISTRY:
                self.stderr.write(f"Model '{model_key}' not found. Use --list to see options.")
                return
            
            Model = RASTER_REGISTRY[model_key]
            
            if options['id']:
                instance = Model.objects.get(id=options['id'])
                export_raster_to_cog(instance, model_key)
            else:
                # Export all records from that model
                for instance in Model.objects.all():
                    try:
                        export_raster_to_cog(instance, model_key)
                        self.stdout.write(self.style.SUCCESS(f"  ✓ {model_key} id={instance.id}"))
                    except Exception as e:
                        self.stderr.write(f"  ✗ {model_key} id={instance.id}: {e}")
            return

        # Default: export ALL rasters from ALL models
        for model_key, Model in RASTER_REGISTRY.items():
            self.stdout.write(f"\nProcessing {model_key}...")
            for instance in Model.objects.all():
                try:
                    export_raster_to_cog(instance, model_key)
                    self.stdout.write(self.style.SUCCESS(f"  ✓ id={instance.id}"))
                except Exception as e:
                    self.stderr.write(f"  ✗ id={instance.id}: {e}")

        self.stdout.write(self.style.SUCCESS('\nDone!'))