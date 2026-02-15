"""Exercise the integration with the actual Home Assistant runtime."""

from __future__ import annotations

import json
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


@pytest.mark.parametrize(
    ("language", "latitude", "name"),
    [("en", "Latitude", "Name"), ("it", "Latitudine", "Nome")],
)
async def test_translations(hass, language, latitude, name):
    """HA loads literal form labels and the translated update error."""
    for category, key, expected in (
        ("config", "step.user.data.latitude", latitude),
        ("options", "step.init.data.name", name),
        ("exceptions", "update_failed.message", "{error}"),
    ):
        translations = await async_get_translations(
            hass, language, category, {"meteoam"}
        )
        value = translations[f"component.meteoam.{category}.{key}"]
        assert expected in value
        assert all("[%key:" not in text for text in translations.values())


def test_translation_keys_match():
    """Every language defines exactly the English keys."""
    folder = Path(__file__).parent.parent / "custom_components/meteoam/translations"

    def keys(data, prefix=""):
        return {
            k
            for key, value in data.items()
            for k in (
                keys(value, f"{prefix}{key}.")
                if isinstance(value, dict)
                else [prefix + key]
            )
        }

    english = keys(json.loads((folder / "en.json").read_text()))
    for path in folder.glob("*.json"):
        assert keys(json.loads(path.read_text())) == english, path.name


@pytest.mark.parametrize("source", ["user", "onboarding"])
async def test_observation_lifecycle(hass, source):
    """Observation options create sensors, track home, and unload independently."""
    from custom_components.meteoam.coordinator import MeteoAMStationData

    async def fetch(data):
        data.current_weather_data = {
            "2t": 16,
            "r": 76,
            "pmsl": 1022,
            "wkmh": 4,
            "wdir": None,
            "wcar": "VRB",
        }
        data.station_attributes = {"station_icao": "LIRU"}
        return data

    with patch.object(MeteoAMStationData, "fetch_data", fetch):
        flow = await hass.config_entries.flow.async_init(
            "meteoam", context={"source": source}
        )
        if source == "user":
            flow = await hass.config_entries.flow.async_configure(
                flow["flow_id"],
                {
                    "name": "Rome",
                    "latitude": 41.9,
                    "longitude": 12.5,
                    "station_observations": True,
                },
            )
        entry = flow["result"]
        if source == "onboarding":
            hass.config_entries.async_update_entry(
                entry, data={**entry.data, "station_observations": True}
            )
            await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()
        station = entry.runtime_data.station
        registry = er.async_get(hass)
        entities = er.async_entries_for_config_entry(registry, entry.entry_id)
        assert len(entities) == 7
        states = {
            entity.translation_key: hass.states.get(entity.entity_id)
            for entity in entities
            if entity.domain == "sensor"
        }
        assert states["observed_temperature"].state == "16"
        assert states["observed_temperature"].attributes["station_icao"] == "LIRU"
        assert states["observed_wind_bearing"].state == "unknown"
        if source == "onboarding":
            await hass.config.async_update(latitude=45.0, longitude=9.0)
            await hass.async_block_till_done()
            assert station.weather._coordinates == {"lat": "45.0", "lon": "9.0"}
        identities = {(entity.entity_id, entity.unique_id) for entity in entities}
        assert await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()
        assert station._unsub_track_home is None
        assert identities == {
            (entity.entity_id, entity.unique_id)
            for entity in er.async_entries_for_config_entry(registry, entry.entry_id)
        }
        station = entry.runtime_data.station
        options = await hass.config_entries.options.async_init(entry.entry_id)
        await hass.config_entries.options.async_configure(
            options["flow_id"],
            {
                "name": "Rome",
                "latitude": 41.9,
                "longitude": 12.5,
                "station_observations": False,
            },
        )
        await hass.async_block_till_done()
        assert entry.runtime_data.station is None
        assert station._unsub_track_home is None
        assert all(
            state.state == "unavailable" for state in hass.states.async_all("sensor")
        )
        assert (
            sum(state.state == "sunny" for state in hass.states.async_all("weather"))
            == 1
        )


async def test_station_outage_does_not_block_forecast(hass, caplog):
    """An optional API outage leaves forecasts loaded; sensors recover on refresh."""
    from custom_components.meteoam.coordinator import (
        CannotConnectError,
        MeteoAMStationData,
    )

    with patch.object(
        MeteoAMStationData, "fetch_data", side_effect=CannotConnectError("offline")
    ):
        flow = await hass.config_entries.flow.async_init(
            "meteoam", context={"source": "user"}
        )
        flow = await hass.config_entries.flow.async_configure(
            flow["flow_id"],
            {
                "name": "Rome",
                "latitude": 41.9,
                "longitude": 12.5,
                "station_observations": True,
            },
        )
        await hass.async_block_till_done()
    entry = flow["result"]
    assert entry.state.value == "loaded"
    assert hass.states.async_all("weather")[0].state == "sunny"
    assert len(hass.states.async_all("sensor")) == 6
    assert all(
        state.state == "unavailable" for state in hass.states.async_all("sensor")
    )
    assert "offline" in caplog.text
    caplog.clear()  # The fixture rejects unexpected HA errors; this one is intentional.
    station = entry.runtime_data.station
    data = station.weather
    data.current_weather_data = {"2t": 18}
    data.station_attributes = {"station_icao": "LIRU"}
    with patch.object(MeteoAMStationData, "fetch_data", return_value=data):
        await station.async_refresh()
        await hass.async_block_till_done()
    assert any(state.state == "18" for state in hass.states.async_all("sensor"))
    assert await hass.config_entries.async_unload(entry.entry_id)
