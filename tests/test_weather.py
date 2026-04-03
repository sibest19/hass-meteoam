"""Tests for the MeteoAM weather entity."""

from __future__ import annotations

import pytest

from custom_components.meteoam.weather import format_condition


class TestFormatCondition:
    """Tests for format_condition."""

    @pytest.mark.parametrize(
        ("icon_code", "expected"),
        [
            ("01", "sunny"),
            ("02", "sunny"),
            ("31", "clear-night"),
            ("06", "cloudy"),
            ("09", "pouring"),
            ("16", "snowy"),
            ("18", "windy"),
        ],
    )
    def test_known_codes_map_to_ha_condition(self, icon_code, expected):
        """Known MeteoAM icon codes should map to the correct HA condition."""
        assert format_condition(icon_code) == expected

    def test_unknown_code_returns_none(self):
        """An unrecognised icon code should return None, not the raw code."""
        result = format_condition("99")
        assert result is None, f"Expected None for unknown code, got {result!r}"

    def test_empty_string_returns_none(self):
        """An empty string should return None."""
        assert format_condition("") is None
