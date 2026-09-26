"""Offline checks for the four building positions (no Django/API required)."""

import unittest

from yoolink.ycms.applications.shop.verified_locations import verified_position


class VerifiedLocationsTests(unittest.TestCase):
    def test_four_buildings_are_distinct_and_ordered_south_to_north(self):
        positions = [verified_position(f"Dr.-Kiefl-Straße {number}, 94447 Plattling-Höhenrain")
                     for number in ("31", "33", "33a", "33b")]
        self.assertEqual(len(set(positions)), 4)
        self.assertEqual(positions, sorted(positions))
        for lat, lng in positions:
            self.assertTrue(48.7836 < lat < 48.7846)
            self.assertTrue(12.8682 < lng < 12.8688)

    def test_address_variants(self):
        expected = verified_position("Dr.-Kiefl-Straße 33a, 94447 Plattling")
        for address in (
            "Doktor-Kiefl-Straße 33A, 94447 Plattling-Höhenrain",
            " Dr. Kiefl Str. 33a,  94447 Plattling, Deutschland ",
            "Dr.-Kiefl-Strasse 33a, 94447 Plattling",
        ):
            self.assertEqual(verified_position(address), expected)

    def test_requires_exact_house_street_postcode_and_town(self):
        for address in (
            "Dr.-Kiefl-Straße 33c, 94447 Plattling",
            "Dr.-Kiefl-Straße 133, 94447 Plattling",
            "Andere Straße 33, 94447 Plattling",
            "Dr.-Kiefl-Straße 33, 94448 Plattling",
            "Dr.-Kiefl-Straße 33, 94447 Anderer Ort",
            "Dr.-Kiefl-Straße 33", "", None,
        ):
            self.assertIsNone(verified_position(address))
