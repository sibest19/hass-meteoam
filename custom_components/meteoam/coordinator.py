"""DataUpdateCoordinator for MeteoAM integration."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Mapping
from datetime import timedelta
from random import randrange
from typing import Any, Self

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_LATITUDE,
    CONF_LONGITUDE,
    EVENT_CORE_CONFIG_UPDATE,
)
from homeassistant.core import Event, HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import CONF_TRACK_HOME, DOMAIN

_MAX_ATTEMPTS = 3
_RETRY_DELAY_S = 2

# Dedicated Home Assistant endpoint - do not change!
URL = "https://api.meteoam.it/deda-meteograms/api/GetMeteogram/preset1/{lat},{lon}"

_LOGGER = logging.getLogger(__name__)

type MeteoAMConfigEntry = ConfigEntry[MeteoAMDataUpdateCoordinator]


class CannotConnectError(HomeAssistantError):
    """Unable to connect to the web site."""


class TransientAPIError(CannotConnectError):
    """Transient API error (network/5xx), safe to retry."""


class MeteoAMDataUpdateCoordinator(DataUpdateCoordinator["MeteoAMWeatherData"]):
    """Class to manage fetching MeteoAM data."""

    config_entry: MeteoAMConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: MeteoAMConfigEntry) -> None:
        """Initialize global MeteoAM data updater."""
        self._unsub_track_home: Callable[[], None] | None = None
        self.weather = MeteoAMWeatherData(hass, config_entry.data)
        self.weather.set_coordinates()

        update_interval = timedelta(minutes=randrange(55, 65))  # noqa: S311

        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=update_interval,
        )

    async def _async_update_data(self) -> MeteoAMWeatherData:
        """Fetch data from MeteoAM with retry on transient errors."""
        for attempt in range(_MAX_ATTEMPTS):
            try:
                return await self.weather.fetch_data()
            except TransientAPIError as err:
                if attempt < _MAX_ATTEMPTS - 1:
                    _LOGGER.warning(
                        "MeteoAM API transient error (attempt %d/%d), "
                        "retrying in %ds: %s",
                        attempt + 1,
                        _MAX_ATTEMPTS,
                        _RETRY_DELAY_S,
                        err,
                    )
                    await asyncio.sleep(_RETRY_DELAY_S)
                else:
                    raise UpdateFailed(
                        translation_domain=DOMAIN,
                        translation_key="update_failed",
                        translation_placeholders={"error": str(err)},
                    ) from err
            except CannotConnectError as err:
                raise UpdateFailed(
                    translation_domain=DOMAIN,
                    translation_key="update_failed",
                    translation_placeholders={"error": str(err)},
                ) from err

    def track_home(self) -> None:
        """Start tracking changes to HA home setting."""
        if self._unsub_track_home:
            return

        async def _async_update_weather_data(_event: Event | None = None) -> None:
            """Update weather data."""
            if self.weather.set_coordinates():
                await self.async_refresh()

        self._unsub_track_home = self.hass.bus.async_listen(
            EVENT_CORE_CONFIG_UPDATE, _async_update_weather_data
        )

    def untrack_home(self) -> None:
        """Stop tracking changes to HA home setting."""
        if self._unsub_track_home:
            self._unsub_track_home()
            self._unsub_track_home = None


class MeteoAMWeatherData:
    """Keep data for MeteoAM weather entities."""

    def __init__(self, hass: HomeAssistant, config: Mapping[str, Any]) -> None:
        """Initialise the weather entity data."""
        self.hass = hass
        self._config = config
        self._session: aiohttp.ClientSession | None = None
        self.current_weather_data: dict = {}
        self.daily_forecast: list[dict] = []
        self.hourly_forecast: list[dict] = []
        self._coordinates: dict[str, str] | None = None

    def set_coordinates(self) -> bool:
        """Weather data initialization - set the coordinates."""
        if self._config.get(CONF_TRACK_HOME, False):
            latitude = self.hass.config.latitude
            longitude = self.hass.config.longitude
        else:
            latitude = self._config[CONF_LATITUDE]
            longitude = self._config[CONF_LONGITUDE]

        coordinates = {
            "lat": str(latitude),
            "lon": str(longitude),
        }
        if coordinates == self._coordinates:
            return False
        self._coordinates = coordinates

        self._session = async_get_clientsession(self.hass)
        return True

    async def fetch_data(self) -> Self:
        """Fetch data from API - (current weather and forecast)."""
        if self._coordinates is None:
            msg = "Coordinates not set"
            raise RuntimeError(msg)
        if self._session is None:
            msg = "Session not initialized"
            raise RuntimeError(msg)

        url = URL.format(
            lat=self._coordinates["lat"],
            lon=self._coordinates["lon"],
        )
        _LOGGER.debug("Fetching MeteoAM data from %s", url)

        timeout = aiohttp.ClientTimeout(total=60)
        try:
            resp = await self._session.get(url, timeout=timeout)
        except (aiohttp.ClientError, TimeoutError) as err:
            raise TransientAPIError(f"Error connecting to MeteoAM API: {err}") from err

        if resp.status >= 500:
            raise TransientAPIError(f"API returned status {resp.status}")
        if resp.status != 200:
            raise CannotConnectError(f"API returned status {resp.status}")

        try:
            data = await resp.json()
        except (aiohttp.ContentTypeError, ValueError) as err:
            raise CannotConnectError(
                f"Error parsing MeteoAM API response: {err}"
            ) from err

        if not data:
            raise CannotConnectError("API returned empty response")

        try:
            self._parse_data(data)
        except (KeyError, IndexError, TypeError) as err:
            raise CannotConnectError(
                f"Error processing MeteoAM API data: {err}"
            ) from err

        return self

    def _parse_data(self, data: dict[str, Any]) -> None:
        """Parse the API response data."""
        # Parse daily forecast from stats
        self.daily_forecast = []
        for item in data["extrainfo"]["stats"]:
            parsed_dt = dt_util.parse_datetime(item["localDate"])
            if parsed_dt is None:
                continue
            element = {
                "localDateTime": parsed_dt.isoformat(),
                "2t": item["maxCelsius"],
                "2t_min": item["minCelsius"],
                "icon": item["icon"],
            }
            self.daily_forecast.append(element)

        # Parse hourly forecast from timeseries
        hourly_forecast: list[dict] = []
        timeseries_data = data["timeseries"]
        paramlist_data = data["paramlist"]
        datasets = data["datasets"]["0"]
        now = dt_util.now()

        current_weather_data: dict[str, Any] = {}

        for tidx, t in enumerate(timeseries_data):
            parsed_dt = dt_util.parse_datetime(t)
            if parsed_dt is None:
                continue
            local_dt = dt_util.as_local(parsed_dt)
            tidx_str = str(tidx)

            element: dict[str, Any] = {"localDateTime": local_dt.isoformat()}
            for pidx, p in enumerate(paramlist_data):
                element[p] = datasets[str(pidx)][tidx_str]

            if local_dt <= now:
                current_weather_data = element
            if local_dt >= now:
                hourly_forecast.append(element)

        # Fall back to the nearest future entry if no current weather data
        if not current_weather_data and hourly_forecast:
            current_weather_data = hourly_forecast[0]

        self.current_weather_data = current_weather_data
        self.hourly_forecast = hourly_forecast
