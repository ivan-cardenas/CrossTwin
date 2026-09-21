from django.test import SimpleTestCase

from core.utils import MODEL_REGISTRY, RASTER_REGISTRY, VECTOR_REGISTRY


class ModelRegistryTests(SimpleTestCase):
    def test_every_domain_app_is_registered(self):
        """A typo in allowed_apps is swallowed silently (LookupError), dropping the whole app."""
        apps_present = {key.split('.')[0] for key in MODEL_REGISTRY}
        for app in ('administrative', 'physicalEnv', 'urban_heat', 'watersupply',
                    'weather', 'builtup', 'Energy', 'housing', 'nature'):
            self.assertIn(app, apps_present)

    def test_urban_heat_rasters_reach_the_cog_pipeline(self):
        self.assertIn('urban_heat.UTCI', RASTER_REGISTRY)
        self.assertIn('urban_heat.NatureBasedSolutionPolygon', VECTOR_REGISTRY)
