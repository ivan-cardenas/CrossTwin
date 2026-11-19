"""
housing.signals.project_saved/project_deleted -> builtup/calculations/materialise.py
(DAG edges New_Units -> Buildings, Streets -> Buildings) and the generator views.
"""
import json

from django.contrib.auth import get_user_model

from builtup.models import Building, Property, Street
from housing.models import HousingProject
from physicalEnv.models import LandCoverVector, UrbanFabricCut
from physicalEnv.tests.test_physicalenv import _UrbanFabricTestCase, _square

PARAMS = {"typology": "row", "angle_deg": 0, "variation": 0}
SITE = (200, 200, 500, 400)        # 300 m x 200 m inside the 1 km test city


def _wgs84(geom):
    from django.conf import settings
    geom.srid = settings.COORDINATE_SYSTEM
    clone = geom.transform(4326, clone=True)
    return json.loads(clone[0].geojson if clone.geom_type == "MultiPolygon" else clone.geojson)


class GeneratedNeighbourhoodTests(_UrbanFabricTestCase):

    def _project(self, status="completed", params=PARAMS, **kwargs):
        return HousingProject.objects.create(
            neighborhood=self.neighborhood, year=2026, year_expected_completion=2030,
            project_name="Test wijk", project_area=60_000, project_units=250,
            status=status, generator_params=params, geom=_square(*SITE), **kwargs)

    def _generated(self, project):
        return (Street.objects.filter(source_project=project.pk),
                Building.objects.filter(source_project=project.pk),
                Property.objects.filter(building__source_project=project.pk))

    def test_a_completed_project_becomes_streets_buildings_and_dwellings(self):
        project = self._project()
        streets, buildings, dwellings = self._generated(project)
        self.assertEqual(project._layout_result["buildings"], 252)
        self.assertEqual(buildings.count(), 252)
        self.assertEqual(dwellings.count(), 504)          # 3-floor row houses hold two flats each (dwelling_mode auto)
        self.assertTrue(dwellings.filter(name__contains="floor 1 unit 2").exists())
        self.assertEqual(streets.count(), 5)
        self.assertTrue(all(pk < 0 for pk in buildings.values_list("pk", flat=True)))
        b = buildings.first()
        self.assertEqual((b.numberFloors, b.height_m, b.constructionYear, b.buildingType), (3, 9.0, 2030, "residential"))
        self.assertEqual(b.usageFunction, ["Residential function"])
        # Land cover: one urban-fabric polygon for the project, road surfaces cut out of it, no per-building rings
        self.assertFalse(LandCoverVector.objects.filter(source_building__isnull=False).exists())
        fabric = LandCoverVector.objects.get(source_project=project.pk)
        roads = LandCoverVector.objects.filter(source_street__isnull=False)
        self.assertEqual(set(roads.values_list("source_street", flat=True)), set(streets.values_list("pk", flat=True)))
        self.assertAlmostEqual(fabric.geom.area + sum(r.geom.area for r in roads), 300 * 200, delta=1)

    def test_a_planned_project_has_no_buildings(self):
        project = self._project(status="planned")
        self.assertFalse(any(qs.exists() for qs in self._generated(project)))

    def test_back_to_planned_and_delete_remove_everything(self):
        for action in ("planned", "delete"):
            with self.subTest(action):
                project = self._project()
                if action == "planned":
                    project.status = "planned"
                    project.save()
                else:
                    project.delete()
                self.assertFalse(any(qs.exists() for qs in self._generated(project)))
                self.assertFalse(LandCoverVector.objects.exclude(pk=self.pasture.pk).exists())
                self.assertFalse(UrbanFabricCut.objects.exists())
                self.pasture.refresh_from_db()
                self.assertAlmostEqual(self.pasture.geom.area, 1e6, delta=0.5)

    def test_new_parameters_rebuild_and_unrelated_edits_do_not(self):
        project = self._project()
        first_ids = set(Building.objects.filter(source_project=project.pk).values_list("pk", flat=True))
        project.project_description = "only text"
        project.save()
        self.assertEqual(set(Building.objects.filter(source_project=project.pk).values_list("pk", flat=True)), first_ids)
        project.generator_params = {**PARAMS, "typology": "detached"}
        project.save()
        self.assertEqual(Building.objects.filter(source_project=project.pk).count(), 108)


class GeneratorViewTests(_UrbanFabricTestCase):

    def setUp(self):
        super().setUp()
        self.staff = get_user_model().objects.create_user("staff", password="x", is_staff=True)
        self.outline = _wgs84(_square(*SITE))

    def _post(self, name, body):
        return self.client.post(f"/builtup/generator/{name}/", data=json.dumps(body), content_type="application/json")

    def test_preview_writes_nothing(self):
        before = (Building.objects.count(), Street.objects.count(), LandCoverVector.objects.count())
        response = self._post("preview", {"outline": self.outline, "params": {"typology": "slab"}})
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        kinds = {f["properties"]["kind"] for f in data["layout"]["features"]}
        self.assertEqual(kinds, {"block", "plot", "street", "building"})
        self.assertGreater(data["metrics"]["units"], 0)
        self.assertEqual((Building.objects.count(), Street.objects.count(), LandCoverVector.objects.count()), before)

    def test_preview_rejects_bad_input(self):
        self.assertEqual(self._post("preview", {"params": PARAMS}).status_code, 400)
        self.assertEqual(self._post("preview", {"outline": self.outline, "params": {"typology": "castle"}}).status_code, 400)

    def test_commit_needs_staff(self):
        self.assertEqual(self._post("commit", {"outline": self.outline, "params": PARAMS}).status_code, 403)
        self.assertFalse(HousingProject.objects.exists())

    def test_commit_then_restore_reverts_everything(self):
        from core.editing import active_backup, restore_backup
        from mainMap.models import EditBackup

        self.client.force_login(self.staff)
        EditBackup.objects.create(created_by=self.staff)
        response = self._post("commit", {"outline": self.outline, "params": PARAMS, "name": "Wijk",
                                         "year_expected_completion": 2031})
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        self.assertEqual(data["result"]["buildings"], Building.objects.filter(source_project=data["project"]["id"]).count())
        project = HousingProject.objects.get()
        self.assertEqual((project.status, project.neighborhood_id, project.generator_params["typology"]),
                         ("completed", self.neighborhood.pk, "row"))

        restore_backup(active_backup())
        self.assertFalse(HousingProject.objects.exists())
        self.assertFalse(Building.objects.exists())
        self.assertFalse(Street.objects.exists())
        self.assertFalse(Property.objects.exists())
        self.assertEqual(list(LandCoverVector.objects.values_list("pk", flat=True)), [self.pasture.pk])
        self.pasture.refresh_from_db()
        self.assertAlmostEqual(self.pasture.geom.area, 1e6, delta=0.5)

    def test_remove_sets_the_project_back_to_planned(self):
        self.client.force_login(self.staff)
        project_id = self._post("commit", {"outline": self.outline, "params": PARAMS}).json()["project"]["id"]
        response = self._post("remove", {"project_id": project_id})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(HousingProject.objects.get().status, "planned")
        self.assertFalse(Building.objects.exists())
