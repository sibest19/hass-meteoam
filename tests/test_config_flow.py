"""Tests for the MeteoAM config flow."""

from __future__ import annotations

from unittest.mock import MagicMock, PropertyMock

import pytest

from custom_components.meteoam.config_flow import MeteoAMOptionsFlowHandler
from custom_components.meteoam.const import CONF_TRACK_HOME


@pytest.fixture
def hass_mock():
    """Return a minimal HomeAssistant mock."""
    hass = MagicMock()
    hass.config.latitude = 41.9
    hass.config.longitude = 12.5
    hass.config.location_name = "Home"
    hass.config_entries.async_update_entry = MagicMock()
    return hass


def _make_handler(hass_mock: MagicMock, config_data: dict) -> MeteoAMOptionsFlowHandler:
    """Build an OptionsFlowHandler with a mocked config_entry property."""
    config_entry = MagicMock()
    config_entry.data = config_data
    config_entry.title = config_data.get("name", "Test")

    handler = MeteoAMOptionsFlowHandler()
    handler.hass = hass_mock
    # config_entry is a read-only property on OptionsFlowWithReload; patch it.
    type(handler).config_entry = PropertyMock(return_value=config_entry)
    return handler


class TestOptionsFlowPreservesTrackHome:
    """Tests that the options flow preserves config flags not present in the form."""

    async def test_track_home_preserved_after_options_edit(self, hass_mock):
        """Submitting options must not drop track_home from config data."""
        original_data = {
            CONF_TRACK_HOME: True,
            "latitude": 41.9,
            "longitude": 12.5,
            "name": "Home",
        }
        handler = _make_handler(hass_mock, original_data)

        user_input = {"latitude": 48.85, "longitude": 2.35, "name": "Paris"}
        await handler.async_step_init(user_input=user_input)

        call_kwargs = hass_mock.config_entries.async_update_entry.call_args
        updated_data = call_kwargs.kwargs.get("data") or call_kwargs.args[1]
        assert updated_data.get(CONF_TRACK_HOME) is True, (
            "track_home must be preserved after options edit"
        )

    async def test_fixed_location_data_preserved_after_options_edit(self, hass_mock):
        """Existing config keys not in the form schema must be preserved."""
        original_data = {
            "latitude": 41.9,
            "longitude": 12.5,
            "name": "Rome",
            "extra_flag": "keep_me",
        }
        handler = _make_handler(hass_mock, original_data)

        user_input = {"latitude": 51.5, "longitude": -0.12, "name": "London"}
        await handler.async_step_init(user_input=user_input)

        call_kwargs = hass_mock.config_entries.async_update_entry.call_args
        updated_data = call_kwargs.kwargs.get("data") or call_kwargs.args[1]
        assert updated_data.get("extra_flag") == "keep_me"
        assert updated_data["latitude"] == 51.5
        assert updated_data["name"] == "London"
