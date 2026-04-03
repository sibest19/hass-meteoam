"""Tests for the MeteoAM config flow."""

from __future__ import annotations

from unittest.mock import MagicMock, PropertyMock, patch

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


class TestOptionsFlow:
    """Tests for the options flow behavior, aligned with met.no."""

    async def test_options_edit_replaces_config_data(self, hass_mock):
        """Options edit replaces config data entirely with user_input (met.no pattern).

        Editing options converts a track_home entry to a fixed-location entry;
        track_home is intentionally removed (consistent with met.no).
        """
        original_data = {
            CONF_TRACK_HOME: True,
            "latitude": 41.9,
            "longitude": 12.5,
            "name": "Home",
        }
        config_entry = MagicMock()
        config_entry.data = original_data
        config_entry.title = "Home"

        handler = MeteoAMOptionsFlowHandler()
        handler.hass = hass_mock
        with patch.object(
            type(handler),
            "config_entry",
            new_callable=PropertyMock,
            return_value=config_entry,
        ):
            user_input = {"latitude": 48.85, "longitude": 2.35, "name": "Paris"}
            await handler.async_step_init(user_input=user_input)

            call_kwargs = hass_mock.config_entries.async_update_entry.call_args
            updated_data = call_kwargs.kwargs.get("data") or call_kwargs.args[1]
            assert updated_data == user_input, (
                "Config data must be replaced with exactly user_input (no merging)"
            )
            assert CONF_TRACK_HOME not in updated_data, (
                "track_home must be removed after options edit"
            )

    async def test_options_edit_uses_only_user_input(self, hass_mock):
        """Options edit must not carry over keys not present in the submitted form."""
        original_data = {
            "latitude": 41.9,
            "longitude": 12.5,
            "name": "Rome",
            "stale_key": "should_be_gone",
        }
        config_entry = MagicMock()
        config_entry.data = original_data
        config_entry.title = "Rome"

        handler = MeteoAMOptionsFlowHandler()
        handler.hass = hass_mock
        with patch.object(
            type(handler),
            "config_entry",
            new_callable=PropertyMock,
            return_value=config_entry,
        ):
            user_input = {"latitude": 51.5, "longitude": -0.12, "name": "London"}
            await handler.async_step_init(user_input=user_input)

            call_kwargs = hass_mock.config_entries.async_update_entry.call_args
            updated_data = call_kwargs.kwargs.get("data") or call_kwargs.args[1]
            assert updated_data == user_input
            assert "stale_key" not in updated_data
