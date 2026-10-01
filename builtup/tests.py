from django.conf import settings
from django.contrib.gis.geos import MultiPolygon, Polygon
from django.test import TestCase

from builtup.models import Building


def _square(x, y, size=10):
    """A square MultiPolygon in the storage CRS (metres)."""
    polygon = Polygon(((x, y), (x + size, y), (x + size, y + size), (x, y + size), (x, y)))
    return MultiPolygon(polygon, srid=settings.COORDINATE_SYSTEM)


class BuildingDerivedFieldsTests(TestCase):
    """Fields Building.save() derives must be stored on every save path."""

    def test_create_derives_building_type(self):
        Building.objects.update_or_create(
            id=1, defaults={"usageFunction": "woonfunctie", "geom": _square(0, 0)})

        building = Building.objects.get(id=1)
        self.assertEqual(building.buildingType, "residential")
        self.assertEqual(building.usageFunction, ["Residential function"])
        self.assertEqual(building.area_sqm, 100)

    def test_update_or_create_on_existing_building_stores_derived_fields(self):
        # The importer's path for a re-imported building: update_or_create saves
        # with update_fields = the keys of `defaults`, which holds none of the
        # derived fields.
        Building.objects.update_or_create(
            id=1, defaults={"usageFunction": "woonfunctie", "geom": _square(0, 0)})

        _, created = Building.objects.update_or_create(
            id=1, defaults={"usageFunction": "winkelfunctie,woonfunctie", "geom": _square(0, 0, size=20)})

        self.assertFalse(created)
        building = Building.objects.get(id=1)
        self.assertEqual(building.buildingType, "mixed")
        self.assertEqual(building.usageFunction, ["Shop function", "Residential function"])
        self.assertEqual(building.area_sqm, 400)

    def test_resaving_stored_labels_keeps_building_type(self):
        # A stored building holds labels, not raw BAG codes; a plain re-save
        # (what a backfill does) must derive the same type from them.
        Building.objects.create(id=1, usageFunction="industriefunctie", geom=_square(0, 0))
        Building.objects.filter(id=1).update(buildingType="")

        building = Building.objects.get(id=1)
        building.save(update_fields=["buildingType"])

        self.assertEqual(Building.objects.get(id=1).buildingType, "industrial")

    def test_undefined_usage_has_no_building_type(self):
        # BAG reports some Pand records with an empty gebruiksdoel
        Building.objects.create(id=1, usageFunction="", geom=_square(0, 0))

        building = Building.objects.get(id=1)
        self.assertEqual(building.usageFunction, ["Undefined"])
        self.assertEqual(building.buildingType, "")
