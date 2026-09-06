import unittest
from unittest import mock

from contact.utilities.telemetry_beautifier import get_chunks, humanize_wind_direction


class TelemetryBeautifierTests(unittest.TestCase):
    def test_humanize_wind_direction_handles_boundaries(self) -> None:
        self.assertEqual(humanize_wind_direction(0), "N")
        self.assertEqual(humanize_wind_direction(90), "E")
        self.assertEqual(humanize_wind_direction(225), "SW")
        self.assertIsNone(humanize_wind_direction(-1))

    def test_get_chunks_formats_known_and_unknown_values(self) -> None:
        rendered = get_chunks("uptime_seconds:7200\nwind_direction:90\nlatitude_i:123456789\nunknown:abc\n")

        self.assertIn("🆙 2.0h", rendered)
        self.assertIn("⮆ E", rendered)
        self.assertIn("🌍 12.345679", rendered)
        self.assertIn("unknown:abc", rendered)

    def test_get_chunks_formats_time_values(self) -> None:
        with mock.patch("contact.utilities.telemetry_beautifier.datetime.datetime") as mocked_datetime:
            mocked_datetime.fromtimestamp.return_value.strftime.return_value = "01.01.1970 00:00"
            rendered = get_chunks("time:0\n")

        self.assertIn("🕔 01.01.1970 00:00", rendered)

    def test_get_chunks_normalizes_keys_and_preserves_unknown_strings(self) -> None:
        rendered = get_chunks('  uptime_seconds: 7200\nunknown: "v1.2:ok"\n')

        self.assertIn("🆙 2.0h", rendered)
        self.assertIn('unknown:"v1.2:ok"', rendered)
