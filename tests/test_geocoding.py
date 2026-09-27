"""Google response handling, with mocked HTTP and no real API key required."""

import unittest
from unittest.mock import patch
from urllib.error import URLError

from django.test import override_settings

from yoolink.ycms.applications.shop import geocoding


def result(street="Dr.-Kiefl-Straße", number="35", postcode="94447", lat=48.785, precision="ROOFTOP"):
    return {
        "address_components": [
            {"long_name": value, "types": [kind]}
            for kind, value in (("route", street), ("street_number", number), ("postal_code", postcode))
        ],
        "geometry": {"location_type": precision, "location": {"lat": lat, "lng": 12.868}},
    }


class GeocodingTests(unittest.TestCase):
    def setUp(self):
        from django.conf import settings

        if not settings.configured:
            settings.configure(GEOCODING_ENABLED=True, GOOGLE_MAPS_GEOCODING_API_KEY="test-only")
        self.config = override_settings(GEOCODING_ENABLED=True, GOOGLE_MAPS_GEOCODING_API_KEY="test-only")
        self.config.enable()
        self.addCleanup(self.config.disable)

    def test_new_addresses_and_house_number_formats_are_dynamic(self):
        for street, number, postcode, city in (
            ("Dr.-Kiefl-Straße", "35", "94447", "Plattling"),
            ("Dr.-Kiefl-Straße", "37", "94447", "Plattling"),
            ("Andere Straße", "12 a", "90402", "Nürnberg"),
            ("Hauptstraße", "10-12", "10115", "Berlin"),
            ("Straße des 17. Juni", "9", "10623", "Berlin"),
        ):
            for separator in (", ", " "):
                address = f"{street} {number}{separator}{postcode} {city}"
                payload = {"status": "OK", "results": [result(street, number.replace(" ", ""), postcode)]}
                with self.subTest(address=address), patch.object(geocoding, "_fetch_json", return_value=payload) as fetch:
                    self.assertEqual(geocoding.geocode_address(address), (48.785, 12.868))
                    self.assertEqual(fetch.call_args.args[1]["address"], address)

    def test_old_addresses_have_no_built_in_coordinates(self):
        for number in ("31", "33", "33a", "33b"):
            with patch.object(geocoding, "_fetch_json", return_value={"status": "ZERO_RESULTS"}) as fetch:
                self.assertIsNone(geocoding.geocode_address(f"Dr.-Kiefl-Straße {number}, 94447 Plattling"))
                fetch.assert_called_once()

    def test_rejects_wrong_house_postcode_street_and_street_centres(self):
        for invalid in (
            result(number="37"), result(postcode="10115"), result(street="Falsche Straße"),
            result(precision="APPROXIMATE"), result(precision="GEOMETRIC_CENTER"), result(lat=float("nan")),
        ):
            with patch.object(geocoding, "_fetch_json", return_value={"status": "OK", "results": [invalid]}):
                self.assertIsNone(geocoding.geocode_address("Dr.-Kiefl-Straße 35, 94447 Plattling"))

    def test_rooftop_preferred_and_district_suffix_retry(self):
        responses = [
            {"status": "ZERO_RESULTS"},
            {"status": "OK", "results": [result(lat=48.7, precision="RANGE_INTERPOLATED"), result()]},
        ]
        with patch.object(geocoding, "_fetch_json", side_effect=responses) as fetch:
            self.assertEqual(geocoding.geocode_address("Dr.-Kiefl-Straße 35, 94447 Plattling-Höhenrain"), (48.785, 12.868))
            self.assertEqual(fetch.call_args.args[1]["address"], "Dr.-Kiefl-Straße 35, 94447 Plattling")

    def test_interpolated_house_match_is_usable(self):
        with patch.object(geocoding, "_fetch_json", return_value={"status": "OK", "results": [result(precision="RANGE_INTERPOLATED")]}):
            self.assertEqual(geocoding.geocode_address("Dr.-Kiefl-Str. 35, 94447 Plattling"), (48.785, 12.868))

    def test_api_errors_are_distinct_and_not_retried_as_unknown_addresses(self):
        for status in ("REQUEST_DENIED", "OVER_QUERY_LIMIT", "OVER_DAILY_LIMIT", "UNKNOWN_ERROR"):
            with patch.object(geocoding, "_fetch_json", return_value={"status": status, "error_message": "secret"}) as fetch:
                with self.assertRaises(geocoding.GeocodingError) as raised:
                    geocoding.geocode_address("Dr.-Kiefl-Straße 35, 94447 Plattling-Höhenrain")
                self.assertEqual(raised.exception.code, status)
                self.assertNotIn("secret", str(raised.exception))
                fetch.assert_called_once()

    def test_configuration_errors_and_network_failure(self):
        for override, code in (({"GOOGLE_MAPS_GEOCODING_API_KEY": ""}, "MISSING_KEY"), ({"GEOCODING_ENABLED": False}, "DISABLED")):
            with override_settings(**override), patch.object(geocoding, "_fetch_json") as fetch:
                with self.assertRaises(geocoding.GeocodingError) as raised:
                    geocoding.geocode_address("Neue Straße 8, 94447 Plattling")
                self.assertEqual(raised.exception.code, code)
                fetch.assert_not_called()
        with patch.object(geocoding, "_fetch_json", side_effect=URLError("https://example/?key=secret")):
            with self.assertRaises(geocoding.GeocodingError) as raised:
                geocoding.geocode_address("Neue Straße 8, 94447 Plattling")
            self.assertEqual(raised.exception.code, "SERVICE_UNAVAILABLE")
            self.assertNotIn("secret", str(raised.exception))
