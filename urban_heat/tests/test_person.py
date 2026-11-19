"""The person PET is felt by (urban_heat/calculations/person.py) and its endpoint."""
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from urban_heat.calculations import person


class PersonTests(SimpleTestCase):
    def test_default_is_the_reference_person(self):
        resolved = person.resolve()
        self.assertEqual(person.pet_kwargs(resolved), person.pet_kwargs(None))
        self.assertEqual(person.pet_kwargs(None), person.STANDARD_PERSON)
        self.assertEqual(person.describe(resolved)["preset_label"], "PET reference person (Höppe 1999)")

    def test_clo_is_the_sum_of_the_garments(self):
        # ASHRAE 55 Table 5.2.2.2B: 0.04 + 0.08 + 0.08 + 0.02
        self.assertEqual(person.clothing_clo(["briefs", "t_shirt", "walking_shorts", "sandals"]), 0.22)
        resolved = person.resolve({"garments": "briefs,coat", "clo": "2.5"})
        self.assertEqual(resolved["clo"], 0.64)   # garments win over a typed clo

    def test_activity_sets_met_and_posture(self):
        resolved = person.resolve({"activity": "walk"})
        self.assertEqual((resolved["met"], resolved["position"]), (2.6, "standing"))

    def test_preset_then_edit_is_custom(self):
        self.assertEqual(person.describe(person.resolve({"preset": "child"}))["preset_label"], "Child playing")
        edited = person.resolve({"preset": "child", "age": "10"})
        self.assertEqual(person.describe(edited)["preset_label"], "Custom person")

    def test_derived_values(self):
        info = person.describe(person.resolve())
        self.assertEqual(info["body_surface_m2"], 1.91)   # DuBois, 75 kg, 1.75 m
        self.assertEqual(info["metabolic_w"], round(1.37 * 58.15 * person.body_surface_area(75, 1.75)))

    def test_bad_values_are_refused(self):
        for bad in ({"age": "300"}, {"sex": "x"}, {"garments": "cape"}, {"activity": "fly"}, {"weight": "a"}):
            with self.assertRaises(person.PersonError):
                person.resolve(bad)


class PersonEndpointTests(TestCase):
    def test_options_and_resolved_person(self):
        r = self.client.get(reverse("urban_heat:solweig_person"), {"person_preset": "office"})
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["person"]["clo"], 0.43)
        self.assertIn("activities", body["options"])

    def test_bad_person_is_400(self):
        r = self.client.get(reverse("urban_heat:solweig_person"), {"person_age": "-1"})
        self.assertEqual(r.status_code, 400)


class BaselinePersonTests(TestCase):
    """A scenario's comparison run must be for the same person."""

    def test_find_baseline_skips_runs_for_another_person(self):
        from datetime import datetime, timezone

        from django.contrib.gis.geos import Polygon

        from urban_heat.models import MeanRadiantTemperature, ThermalComfortRun
        from urban_heat.solweig.scenario import find_baseline

        when = datetime(2025, 7, 1, 13, tzinfo=timezone.utc)
        area = Polygon.from_bbox((0, 0, 100, 100))
        area.srid = 28992
        mrt = MeanRadiantTemperature.objects.create(date_time=when)
        common = dict(area=area, bbox_wgs84=[0, 0, 1, 1], date_time=when, met={}, resolution=1.0,
                      status="done", mrt=mrt)
        reference = ThermalComfortRun.objects.create(**common)   # empty person = the reference person
        child = ThermalComfortRun.objects.create(**common, person=person.resolve({"preset": "child"}))

        class Run:
            pass

        scenario = Run()
        scenario.area, scenario.analysis_datetime = area, when
        scenario.parameters = {"person": person.resolve({"preset": "child"})}
        self.assertEqual(find_baseline(scenario).pk, child.pk)
        scenario.parameters = {"person": person.resolve()}
        self.assertEqual(find_baseline(scenario).pk, reference.pk)
        scenario.parameters = {"person": person.resolve({"preset": "winter"})}
        self.assertIsNone(find_baseline(scenario))
