"""The card's "Show on map" button (Templates/partials/_show_on_map.html)."""
from django.template import Context, Template
from django.test import SimpleTestCase


def render(args):
    return Template('{% include "partials/_show_on_map.html" ' + args + ' %}').render(Context({}))


class ShowOnMapTests(SimpleTestCase):
    def test_vector_layers(self):
        html = render('with layers="builtup.Building" label="building stock"')
        self.assertIn('data-layers="builtup.Building"', html)
        self.assertNotIn('data-raster-id', html)

    def test_exact_raster_row(self):
        html = render('with raster_model="urban_heat.PET" raster=3 label="PET"')
        self.assertIn('data-layers="urban_heat.PET"', html)
        self.assertIn('data-raster-id="3"', html)

    def test_no_raster_behind_the_number_no_button(self):
        self.assertNotIn('<button', render('with raster_model="urban_heat.PET" raster=None label="PET"'))
