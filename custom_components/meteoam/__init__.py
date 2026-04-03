"""The MeteoAM component."""

from __future__ import annotations

import logging

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import (
    CONF_TRACK_HOME,
    DEFAULT_HOME_LATITUDE,
    DEFAULT_HOME_LONGITUDE,
    DOMAIN,
)
from .coordinator import MeteoAMConfigEntry, MeteoAMDataUpdateCoordinator

PLATFORMS = [Platform.WEATHER]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, config_entry: MeteoAMConfigEntry
) -> bool:
    """Set up MeteoAM as config entry."""
    # Don't setup if tracking home location and latitude or longitude isn't set.
    # Also, filters out our onboarding default location.
    if config_entry.data.get(CONF_TRACK_HOME, False) and (
        (hass.config.latitude == 0 and hass.config.longitude == 0)
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

    config_entry.runtime_data = coordinator

    if config_entry.data.get(CONF_TRACK_HOME, False):
        coordinator.track_home()

    config_entry.async_on_unload(coordinator.untrack_home)

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    await _cleanup_old_device(hass)

    return True


async def async_unload_entry(
    hass: HomeAssistant, config_entry: MeteoAMConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)


async def _cleanup_old_device(hass: HomeAssistant) -> None:
    """Cleanup device without proper device identifier."""
    device_reg = dr.async_get(hass)
    device = device_reg.async_get_device(identifiers={(DOMAIN,)})  # type: ignore[arg-type]
    if device:
        _LOGGER.debug("Removing improper device %s", device.name)
        device_reg.async_remove_device(device.id)
