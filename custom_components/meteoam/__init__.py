"""The MeteoAM component."""

from __future__ import annotations

import logging

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import (
    CONF_STATION_OBSERVATIONS,
    CONF_TRACK_HOME,
    DEFAULT_HOME_LATITUDE,
    DEFAULT_HOME_LONGITUDE,
    DOMAIN,
)
from .coordinator import (
    MeteoAMConfigEntry,
    MeteoAMDataUpdateCoordinator,
    MeteoAMRuntimeData,
    MeteoAMStationCoordinator,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, config_entry: MeteoAMConfigEntry
) -> bool:
    """Set up MeteoAM as config entry."""
    # Don't setup if tracking home location and latitude or longitude isn't set.
    # Also, filters out our onboarding default location.
    if config_entry.data.get(CONF_TRACK_HOME, False) and (
        (not hass.config.latitude and not hass.config.longitude)
        or (
            hass.config.latitude == DEFAULT_HOME_LATITUDE
            and hass.config.longitude == DEFAULT_HOME_LONGITUDE
        )
    ):
        _LOGGER.warning(
            "Skip setting up MeteoAM integration; No Home location has been set"
        )
        return False

    coordinator = MeteoAMDataUpdateCoordinator(hass, config_entry)
    await coordinator.async_config_entry_first_refresh()

    if config_entry.data.get(CONF_TRACK_HOME, False):
        coordinator.track_home()

    config_entry.async_on_unload(coordinator.untrack_home)

    # Conditionally set up station observations
    station_coordinator: MeteoAMStationCoordinator | None = None
    if config_entry.data.get(CONF_STATION_OBSERVATIONS, False):
        station_coordinator = MeteoAMStationCoordinator(hass, config_entry)
        await station_coordinator.async_config_entry_first_refresh()

        if config_entry.data.get(CONF_TRACK_HOME, False):
            station_coordinator.track_home()

        config_entry.async_on_unload(station_coordinator.untrack_home)

    config_entry.runtime_data = MeteoAMRuntimeData(
        forecast=coordinator,
        station=station_coordinator,
    )

    # Build platform list dynamically
    platforms: list[Platform] = [Platform.WEATHER]
    if station_coordinator is not None:
        platforms.append(Platform.SENSOR)

    await hass.config_entries.async_forward_entry_setups(config_entry, platforms)

    await _cleanup_old_device(hass)

    return True


async def async_unload_entry(
    hass: HomeAssistant, config_entry: MeteoAMConfigEntry
) -> bool:
    """Unload a config entry."""
    platforms: list[Platform] = [Platform.WEATHER]
    if config_entry.runtime_data.station is not None:
        platforms.append(Platform.SENSOR)
    return await hass.config_entries.async_unload_platforms(config_entry, platforms)


async def async_migrate_entry(
    hass: HomeAssistant, config_entry: MeteoAMConfigEntry
) -> bool:
    """Migrate old config entry to new version."""
    _LOGGER.debug("Migrating from version %s", config_entry.version)

    if config_entry.version < 2:
        new_data = {**config_entry.data, CONF_STATION_OBSERVATIONS: False}
        hass.config_entries.async_update_entry(
            config_entry, data=new_data, version=2
        )
        _LOGGER.info("Migration to version 2 successful")

    return True


async def _cleanup_old_device(hass: HomeAssistant) -> None:
    """Cleanup device without proper device identifier."""
    device_reg = dr.async_get(hass)
    device = device_reg.async_get_device(identifiers={(DOMAIN,)})  # type: ignore[arg-type]
    if device:
        _LOGGER.debug("Removing improper device %s", device.name)
        device_reg.async_remove_device(device.id)
