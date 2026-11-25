"""Accessibility equations (builtup/calculations/chain.py): pinned values and monotonicity."""
import math

from django.test import SimpleTestCase

from builtup.calculations import chain


class DistanceDecayTests(SimpleTestCase):
    def test_full_value_inside_d0(self):
        self.assertEqual(chain.distance_decay(0, "walk"), 1.0)
        self.assertEqual(chain.distance_decay(400, "walk"), 1.0)
        self.assertEqual(chain.distance_decay(1500, "bike"), 1.0)

    def test_value_at_cutoff_is_f_at_cutoff(self):
        self.assertAlmostEqual(chain.distance_decay(1600, "walk"), chain.F_AT_CUTOFF, places=12)
        self.assertAlmostEqual(chain.distance_decay(5000, "bike"), chain.F_AT_CUTOFF, places=12)

    def test_pinned_midpoint(self):
        # walk: D0 400, Dmax 1600, halfway (1000 m) -> exp(ln(0.05) * 0.5) = sqrt(0.05)
        self.assertAlmostEqual(chain.distance_decay(1000, "walk"), math.sqrt(0.05), places=12)

    def test_zero_beyond_cutoff_or_unreachable(self):
        self.assertEqual(chain.distance_decay(1600.01, "walk"), 0.0)
        self.assertEqual(chain.distance_decay(None, "walk"), 0.0)

    def test_monotone_non_increasing(self):
        values = [chain.distance_decay(d, "walk") for d in range(0, 2000, 50)]
        self.assertEqual(values, sorted(values, reverse=True))


class ScoreTests(SimpleTestCase):
    def test_no_amenities_scores_zero(self):
        self.assertEqual(chain.accessibility_score({}, "walk"), 0.0)

    def test_everything_next_door_scores_100(self):
        near = {name: [10.0] * len(omegas) for name, (_, omegas) in chain.CATEGORIES.items()}
        self.assertAlmostEqual(chain.accessibility_score(near, "walk"), 100.0, places=9)

    def test_single_category_pinned(self):
        # Only a supermarket at <= D0: that category's weight share of the total weight.
        weight_sum = sum(w for w, _ in chain.CATEGORIES.values())
        expected = 100.0 * chain.CATEGORIES["supermarket"][0] / weight_sum
        self.assertAlmostEqual(chain.accessibility_score({"supermarket": [250.0]}, "walk"), expected, places=9)

    def test_further_amenities_of_a_category_weigh_less(self):
        one = chain.category_value([100.0], "walk", (1.0, 0.5, 0.25))
        two = chain.category_value([100.0, 100.0], "walk", (1.0, 0.5, 0.25))
        three = chain.category_value([100.0, 100.0, 100.0], "walk", (1.0, 0.5, 0.25))
        self.assertAlmostEqual(one, 1.0 / 1.75)
        self.assertAlmostEqual(two, 1.5 / 1.75)
        self.assertAlmostEqual(three, 1.0)

    def test_adding_an_amenity_never_lowers_the_score(self):
        before = {"supermarket": [900.0], "park": [500.0]}
        after = {"supermarket": [300.0], "park": [500.0]}  # a new supermarket is nearer
        self.assertGreater(chain.accessibility_score(after, "walk"), chain.accessibility_score(before, "walk"))
        added = {"supermarket": [900.0], "park": [500.0], "pharmacy": [700.0]}
        self.assertGreater(chain.accessibility_score(added, "walk"), chain.accessibility_score(before, "walk"))

    def test_bike_reaches_further_than_walk(self):
        far = {"supermarket": [2500.0]}
        self.assertEqual(chain.accessibility_score(far, "walk"), 0.0)
        self.assertGreater(chain.accessibility_score(far, "bike"), 0.0)

    def test_minutes(self):
        self.assertAlmostEqual(chain.access_minutes(400, "walk"), 5.0, places=6)
        self.assertIsNone(chain.access_minutes(None, "bike"))
