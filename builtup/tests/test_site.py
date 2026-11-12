"""builtup/calculations/site.py: may a neighbourhood be built on this outline?"""
import json

from django.contrib.auth import get_user_model

from builtup.calculations.site import site_constraints
from builtup.models import Building, ZoningArea
from nature.models import ProtectedArea
from physicalEnv.models import HILUCSLandUse
from physicalEnv.tests.test_physicalenv import _UrbanFabricTestCase, _square

SITE = (200, 200, 500, 400)        # 300 m x 200 m inside the 1 km test city


def _outline():
    from django.conf import settings
    geom = _square(*SITE)
    geom.srid = settings.COORDINATE_SYSTEM
    return geom


class SiteCheckTests(_UrbanFabricTestCase):

    def _protected(self, kind, x0, y0, x1, y1, name="Area"):
        return ProtectedArea.objects.create(name=name, protection_type=kind, geom=_square(x0, y0, x1, y1))

    def _codes(self, check):
        return {(f["code"], f["severity"]) for f in check.findings}

    def test_free_site(self):
        check = site_constraints(_outline())
        self.assertFalse(check.blocked)
        self.assertAlmostEqual(check.buildable.area, 60_000, delta=0.01)
        self.assertIn(("protected", "ok"), self._codes(check))
        self.assertIn(("protected_data", "info"), self._codes(check))     # nothing imported nearby
        self.assertIn(("zoning", "info"), self._codes(check))

    def test_natura2000_and_nnn_are_cut_out(self):
        self._protected("N2K", 0, 0, 300, 1000, "Lonnekermeer")      # covers x 200-300 of the site
        self._protected("NNN", 450, 0, 1000, 1000, "NNN Overijssel")  # covers x 450-500
        check = site_constraints(_outline())
        self.assertFalse(check.blocked)
        self.assertAlmostEqual(check.buildable.area, 150 * 200, delta=0.01)
        self.assertAlmostEqual(check.excluded.area, 150 * 200, delta=0.01)
        cut = [f for f in check.findings if f["severity"] == "excluded"]
        self.assertEqual(len(cut), 2)
        self.assertNotIn(("protected_data", "info"), self._codes(check))
        self.assertEqual({p["type"] for p in check.summary["protected"]}, {"N2K", "NNN"})

    def test_fully_protected_site_is_blocked(self):
        self._protected("N2K", 0, 0, 1000, 1000)
        check = site_constraints(_outline())
        self.assertTrue(check.blocked)
        self.assertIn(("buildable", "block"), self._codes(check))

    def test_climate_buffer_only_warns(self):
        self._protected("OTH", 0, 0, 1000, 1000, "Klimaatbuffer")
        check = site_constraints(_outline())
        self.assertFalse(check.blocked)
        self.assertAlmostEqual(check.buildable.area, 60_000, delta=0.01)
        self.assertIn(("protected", "warn"), self._codes(check))

    def test_zoning(self):
        residential = HILUCSLandUse.objects.get(code="5.1")
        industry = HILUCSLandUse.objects.get(code="2")
        ZoningArea.objects.create(neighborhood=self.neighborhood, zone_type=residential, area=0, geom=_square(200, 200, 350, 400))
        check = site_constraints(_outline())
        self.assertIn(("zoning", "ok"), self._codes(check))
        ZoningArea.objects.create(neighborhood=self.neighborhood, zone_type=industry, area=0, geom=_square(350, 200, 500, 400))
        check = site_constraints(_outline())
        warning = next(f for f in check.findings if f["code"] == "zoning")
        self.assertEqual(warning["severity"], "warn")
        self.assertIn("50%", warning["message"])
        self.assertEqual(len(check.warned), 1)

    def test_existing_buildings_warn(self):
        Building.objects.create(id=123, usageFunction="woonfunctie", geom=_square(300, 300, 310, 310))
        check = site_constraints(_outline())
        self.assertIn(("existing_buildings", "warn"), self._codes(check))


class GeneratorSiteViewTests(_UrbanFabricTestCase):

    def setUp(self):
        super().setUp()
        self.staff = get_user_model().objects.create_user("staff", password="x", is_staff=True)
        geom = _outline().transform(4326, clone=True)
        self.outline = json.loads(geom[0].geojson)

    def _post(self, name, body):
        return self.client.post(f"/builtup/generator/{name}/", data=json.dumps(body), content_type="application/json")

    def test_preview_shows_the_cut_out_and_builds_around_it(self):
        ProtectedArea.objects.create(name="N2K", protection_type="N2K", geom=_square(0, 0, 300, 1000))
        data = self._post("preview", {"outline": self.outline, "params": {"typology": "row"}}).json()
        kinds = [f["properties"]["kind"] for f in data["layout"]["features"]]
        self.assertEqual(kinds.count("excluded"), 1)
        self.assertFalse(data["site"]["blocked"])
        self.assertAlmostEqual(data["metrics"]["site_m2"], 40_000, delta=1)
        self.assertTrue(any(f["code"] == "unit_size" for f in data["regulations"]))

    def test_commit_refused_on_a_protected_site(self):
        from housing.models import HousingProject
        ProtectedArea.objects.create(name="N2K", protection_type="N2K", geom=_square(0, 0, 1000, 1000))
        self.client.force_login(self.staff)
        response = self._post("commit", {"outline": self.outline, "params": {"typology": "row"}})
        self.assertEqual(response.status_code, 400)
        self.assertIn("Cannot build here", response.json()["error"])
        self.assertFalse(HousingProject.objects.exists())
        self.assertFalse(Building.objects.exists())

    def test_commit_stores_the_site_check(self):
        from housing.models import HousingProject
        ProtectedArea.objects.create(name="NNN", protection_type="NNN", geom=_square(0, 0, 300, 1000))
        self.client.force_login(self.staff)
        response = self._post("commit", {"outline": self.outline, "params": {"typology": "row", "angle_deg": 0}})
        self.assertEqual(response.status_code, 200, response.content)
        project = HousingProject.objects.get()
        self.assertEqual(project.generator_params["site_check"]["protected"][0]["type"], "NNN")
        for building in Building.objects.filter(source_project=project.pk):
            self.assertFalse(building.geom.intersects(_square(0, 0, 299.9, 1000)))
