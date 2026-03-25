"""DataUpdateCoordinator for MeteoAM integration."""

from __future__ import annotations

import logging
import secrets
from collections.abc import Callable, Mapping
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

from .const import CONF_TRACK_HOME, DOMAIN

# Dedicated Home Assistant endpoint - do not change!
URL = "https://api.meteoam.it/deda-meteograms/api/GetMeteogram/preset1/{lat},{lon}"

# Station observations endpoint — note the path uses separate segments (lat/lon)
STATION_URL = "https://api.meteoam.it/deda-ows/api/GetStationRadius/{lat}/{lon}"
STATION_HEADERS = {
    "Origin": "https://www.meteoam.it",
    "Referer": "https://www.meteoam.it/",
    "Accept": "application/json",
}

_LOGGER = logging.getLogger(__name__)

type MeteoAMConfigEntry = ConfigEntry[MeteoAMDataUpdateCoordinator]


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
        if not data:
            raise CannotConnectError("API returned empty response")

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
        new_current_weather_data: dict[str, Any] = {}
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
                # Build current weather data from latest past entry
                element: dict[str, Any] = {"localDateTime": local_dt.isoformat()}
                for pidx, p in enumerate(paramlist_data):
                    element[p] = datasets[str(pidx)][tidx_str]
                new_current_weather_data = element
            if local_dt >= now:
                element = {"localDateTime": local_dt.isoformat()}
                for pidx, p in enumerate(paramlist_data):
                    element[p] = datasets[str(pidx)][tidx_str]
                hourly_forecast.append(element)

        if new_current_weather_data:
            self.current_weather_data = new_current_weather_data
        elif hourly_forecast:
            # No past data available: fall back to the nearest future entry so
            # that current conditions remain available when the API only returns
            # future timestamps (e.g. query happens before the first data point).
            _LOGGER.debug(
                "No past timeseries entry found; using nearest future entry"
                " as current conditions"
            )
            self.current_weather_data = hourly_forecast[0]

        self.hourly_forecast = hourly_forecast

        # Enrich current conditions with real station observations when available.
        # Station observations are actual SYNOP/METAR measurements that reflect
        # real-time weather changes. Falls back to forecast-based current data
        # when the station API is unavailable. Station data does not include
        # condition codes (icon) or precipitation probability (tpp), so those
        # are merged from the nearest hourly forecast entry.
        station_obs = await self._fetch_station_observation(timeout)
        if station_obs:
            if hourly_forecast:
                for key in ("icon", "tpp"):
                    val = hourly_forecast[0].get(key)
                    if val is not None:
                        station_obs.setdefault(key, val)
            self.current_weather_data = station_obs

        return self

    async def _fetch_station_observation(
        self, timeout: aiohttp.ClientTimeout
    ) -> dict[str, Any] | None:
        """Fetch the latest real weather observation from GetStationRadius API."""
        if self._coordinates is None or self._session is None:
            return None

        url = STATION_URL.format(
            lat=self._coordinates["lat"],
            lon=self._coordinates["lon"],
        )
        _LOGGER.debug("Fetching MeteoAM station data from %s", url)

        try:
            resp = await self._session.get(
                url, timeout=timeout, headers=STATION_HEADERS
            )
            if resp.status != 200:
                _LOGGER.debug("Station API returned status %s", resp.status)
                return None

            data = await resp.json(content_type=None)
            if not data:
                return None

            # Station timeseries is a nested array [["ts1", "ts2", ...]] with
            # timestamps in reverse chronological order (newest first).
            timeseries = data["timeseries"][0]
            if not isinstance(timeseries, list) or not timeseries:
                return None

            paramlist = data["paramlist"]
            datasets = data["datasets"]["0"]

            # Index "0" → latest observation (reverse chronological order)
            obs: dict[str, Any] = {"localDateTime": timeseries[0]}
            for pidx, p in enumerate(paramlist):
                val = datasets.get(str(pidx), {}).get("0")
                if val is None:
                    continue
                # wdir can be "VRB" (variable wind) — skip non-numeric values
                if p == "wdir" and not isinstance(val, (int, float)):
                    continue
                obs[p] = val

            return obs if len(obs) > 1 else None
        except Exception:
            _LOGGER.debug("Failed to fetch station observation", exc_info=True)
            return None
