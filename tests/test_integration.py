"""Exercise the integration with the actual Home Assistant runtime."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import pytest
from aiohttp.resolver import ThreadedResolver
from homeassistant import bootstrap, loader
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.translation import async_get_translations

from custom_components.meteoam.coordinator import MeteoAMWeatherData


@pytest.fixture
async def hass(tmp_path, caplog):
    """Start a disposable HA instance, replacing only the weather API fetch."""
    (tmp_path / "custom_components").symlink_to(
        Path(__file__).resolve().parents[1] / "custom_components",
        target_is_directory=True,
    )
    hass = HomeAssistant(str(tmp_path))
    loader.async_setup(hass)
    resolver = ThreadedResolver()
    # Newer HA separates resolver ownership from connector cleanup.
    resolver.real_close = resolver.close

    async def fetch(data):
        data.current_weather_data = {"icon": "01", "2t": 20}
        forecast = {
            "localDateTime": datetime.now(UTC).isoformat(),
            "2t": 20,
            "2t_min": 10,
            "icon": "01",
            "tpp": 30,
        }
        data.daily_forecast = [forecast]
        data.hourly_forecast = [forecast]
        return data

    with (
        patch.object(MeteoAMWeatherData, "fetch_data", fetch),
        # These tests do not need multicast DNS or network discovery.
        patch(
            "homeassistant.helpers.aiohttp_client._async_make_resolver",
            return_value=resolver,
        ),
    ):
        try:
            assert await bootstrap.async_from_config_dict(
                {
                    "homeassistant": {
                        "latitude": 41.9,
                        "longitude": 12.5,
                        "time_zone": "Europe/Rome",
                    }
                },
                hass,
            )
            yield hass
        finally:
            await hass.async_stop(force=True)
            await hass.async_block_till_done()
        assert not [record for record in caplog.records if record.levelno >= 40]


@pytest.mark.parametrize("source", ["user", "onboarding"])
async def test_weather_lifecycle(hass, source):
    """Fixed/home locations publish forecasts and retain IDs on reload."""
    flow = await hass.config_entries.flow.async_init(
        "meteoam", context={"source": source}
    )
    if source == "user":
        assert flow["step_id"] == "user"
        flow = await hass.config_entries.flow.async_configure(
            flow["flow_id"],
            {"name": "Rome", "latitude": 41.9, "longitude": 12.5},
        )
    entry = flow["result"]
    await hass.async_block_till_done()
    assert entry.state.value == "loaded"
    registry = er.async_get(hass)
    entities = er.async_entries_for_config_entry(registry, entry.entry_id)
    assert len(entities) == 1
    entity_id = entities[0].entity_id
    unique_id = entities[0].unique_id
    assert hass.states.get(entity_id).state == "sunny"
    assert hass.states.get(entity_id).attributes["temperature"] == 20

    for kind in ("daily", "hourly"):
        result = await hass.services.async_call(
            "weather",
            "get_forecasts",
            {"entity_id": entity_id, "type": kind},
            blocking=True,
            return_response=True,
        )
        forecast = result[entity_id]["forecast"][0]
        assert forecast["temperature"] == 20
        assert forecast["condition"] == "sunny"
        assert forecast["precipitation_probability"] == 30

    registry.async_update_entity(entity_id, name="My weather")
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    entity = er.async_entries_for_config_entry(registry, entry.entry_id)[0]
    assert (entity.entity_id, entity.unique_id, entity.name) == (
        entity_id,
        unique_id,
        "My weather",
    )

    if source == "onboarding":
        await hass.config.async_update(latitude=45.0, longitude=9.0)
        await hass.async_block_till_done()
        assert entry.runtime_data.weather._coordinates == {"lat": "45.0", "lon": "9.0"}
        assert registry.async_get(entity_id).unique_id == unique_id
    else:
        options = await hass.config_entries.options.async_init(entry.entry_id)
        assert options["step_id"] == "init"
        with patch.object(
            hass.config_entries, "async_reload", wraps=hass.config_entries.async_reload
        ) as reload:
            await hass.config_entries.options.async_configure(
                options["flow_id"],
                {"name": "Rome renamed", "latitude": 41.9, "longitude": 12.5},
            )
            await hass.async_block_till_done()
            reload.assert_awaited_once_with(entry.entry_id)
        assert hass.states.get(entity_id).state == "sunny"
        assert entry.data["name"] == "Rome renamed"

    coordinator = entry.runtime_data
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert coordinator._unsub_track_home is None
    assert entry.state.value == "not_loaded"
    assert hass.states.get(entity_id).state == "unavailable"


async def test_translations(hass):
    """HA loads literal form labels and the translated update error."""
    for category, key, expected in (
        ("config", "step.user.data.latitude", "Latitude"),
        ("options", "step.init.data.name", "Name"),
        ("exceptions", "update_failed.message", "{error}"),
    ):
        translations = await async_get_translations(hass, "en", category, {"meteoam"})
        value = translations[f"component.meteoam.{category}.{key}"]
        assert expected in value
        assert all("[%key:" not in text for text in translations.values())
