"""DataUpdateCoordinator for MeteoAM integration."""

from __future__ import annotations

import logging
import secrets
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import timedelta
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

from .const import CONF_TRACK_HOME, DOMAIN, STATION_HEADERS, STATION_URL

# Dedicated Home Assistant endpoint - do not change!
URL = "https://api.meteoam.it/deda-meteograms/api/GetMeteogram/preset1/{lat},{lon}"

_LOGGER = logging.getLogger(__name__)


@dataclass
class MeteoAMRuntimeData:
    """Runtime data for MeteoAM integration."""

    forecast: MeteoAMDataUpdateCoordinator
    station: MeteoAMStationCoordinator | None


type MeteoAMConfigEntry = ConfigEntry[MeteoAMRuntimeData]


class CannotConnectError(HomeAssistantError):
    """Unable to connect to the web site."""


class MeteoAMDataUpdateCoordinator(DataUpdateCoordinator["MeteoAMWeatherData"]):
    """Class to manage fetching MeteoAM data."""

    config_entry: MeteoAMConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: MeteoAMConfigEntry) -> None:
        """Initialize global MeteoAM data updater."""
        self._unsub_track_home: Callable[[], None] | None = None
        self.weather = MeteoAMWeatherData(hass, config_entry.data)
        self.weather.set_coordinates()

        update_interval = timedelta(minutes=secrets.randbelow(10) + 55)

        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=update_interval,
        )

    async def _async_update_data(self) -> MeteoAMWeatherData:
        """Fetch data from MeteoAM."""
        try:
            return await self.weather.fetch_data()
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
        resp = await self._session.get(url, timeout=timeout)
        if resp.status != 200:
            raise CannotConnectError(f"API returned status {resp.status}")

        data = await resp.json()

        # Parse daily forecast from stats
        self.daily_forecast = []
        for item in data["extrainfo"]["stats"]:
            parsed_dt = dt_util.parse_datetime(item["localDate"])
            if parsed_dt is None:
                continue
            element = {
                "localDateTime": parsed_dt,
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

        for tidx, t in enumerate(timeseries_data):
            parsed_dt = dt_util.parse_datetime(t)
            if parsed_dt is None:
                continue
            local_dt = dt_util.as_local(parsed_dt)
            tidx_str = str(tidx)

            if local_dt <= now:
                # Build current weather data (no isoformat needed)
                element: dict[str, Any] = {"localDateTime": local_dt.isoformat()}
                for pidx, p in enumerate(paramlist_data):
                    element[p] = datasets[str(pidx)][tidx_str]
                self.current_weather_data = element
            if local_dt >= now:
                element = {"localDateTime": local_dt.isoformat()}
                for pidx, p in enumerate(paramlist_data):
                    element[p] = datasets[str(pidx)][tidx_str]
                hourly_forecast.append(element)

        self.hourly_forecast = hourly_forecast
        return self


class MeteoAMStationCoordinator(DataUpdateCoordinator["MeteoAMStationData"]):
    """Coordinator for fetching real-time station observations."""

    config_entry: MeteoAMConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: MeteoAMConfigEntry) -> None:
        """Initialize station data updater."""
        self._unsub_track_home: Callable[[], None] | None = None
        self.station = MeteoAMStationData(hass, config_entry.data)
        self.station.set_coordinates()

        update_interval = timedelta(minutes=secrets.randbelow(3) + 5)

        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN}_station",
            update_interval=update_interval,
        )

    async def _async_update_data(self) -> MeteoAMStationData:
        """Fetch data from MeteoAM station API."""
        try:
            return await self.station.fetch_data()
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

        async def _async_update_station_data(_event: Event | None = None) -> None:
            """Update station data."""
            if self.station.set_coordinates():
                await self.async_refresh()

        self._unsub_track_home = self.hass.bus.async_listen(
            EVENT_CORE_CONFIG_UPDATE, _async_update_station_data
        )

    def untrack_home(self) -> None:
        """Stop tracking changes to HA home setting."""
        if self._unsub_track_home:
            self._unsub_track_home()
            self._unsub_track_home = None


class MeteoAMStationData:
    """Keep data for MeteoAM station observation entities."""

    def __init__(self, hass: HomeAssistant, config: Mapping[str, Any]) -> None:
        """Initialise the station data."""
        self.hass = hass
        self._config = config
        self._session: aiohttp.ClientSession | None = None
        self.current_observation: dict[str, Any] = {}
        self.station_name: str | None = None
        self.station_icao: str | None = None
        self._coordinates: dict[str, str] | None = None

    def set_coordinates(self) -> bool:
        """Set the coordinates for the station API."""
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
        """Fetch real-time observation data from the nearest weather station."""
        if self._coordinates is None:
            msg = "Coordinates not set"
            raise RuntimeError(msg)
        if self._session is None:
            msg = "Session not initialized"
            raise RuntimeError(msg)

        url = STATION_URL.format(
            lat=self._coordinates["lat"],
            lon=self._coordinates["lon"],
        )
        _LOGGER.debug("Fetching MeteoAM station data from %s", url)

        timeout = aiohttp.ClientTimeout(total=60)
        resp = await self._session.get(url, timeout=timeout, headers=STATION_HEADERS)
        if resp.status != 200:
            raise CannotConnectError(f"Station API returned status {resp.status}")

        data = await resp.json()

        # Extract station metadata
        extrainfo = data.get("extrainfo", {})
        station_names = extrainfo.get("station_name", [])
        station_icaos = extrainfo.get("station_icao", [])
        self.station_name = station_names[0] if station_names else None
        self.station_icao = station_icaos[0] if station_icaos else None

        # Parse the latest observation (index 0 = newest, reverse chronological)
        paramlist = data.get("paramlist", [])
        datasets = data.get("datasets", {}).get("0", {})

        observation: dict[str, Any] = {}
        for pidx, param in enumerate(paramlist):
            param_data = datasets.get(str(pidx), {})
            value = param_data.get("0")  # index 0 = most recent
            if value is not None:
                observation[param] = value

        # Handle "VRB" (variable) wind direction — store None for numeric bearing
        wdir = observation.get("wdir")
        if isinstance(wdir, str) and wdir == "VRB":
            observation["wdir"] = None

        self.current_observation = observation
        return self
