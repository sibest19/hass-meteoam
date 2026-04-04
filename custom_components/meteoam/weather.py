"""Support for MeteoAM weather service."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from homeassistant.components.weather import (
    ATTR_FORECAST_CONDITION,
    ATTR_FORECAST_NATIVE_TEMP,
    ATTR_FORECAST_TIME,
    ATTR_WEATHER_HUMIDITY,
    ATTR_WEATHER_PRESSURE,
    ATTR_WEATHER_TEMPERATURE,
    ATTR_WEATHER_WIND_BEARING,
    ATTR_WEATHER_WIND_SPEED,
    Forecast,
    SingleCoordinatorWeatherEntity,
    WeatherEntityFeature,
)
from homeassistant.components.weather import (
    DOMAIN as WEATHER_DOMAIN,
)
from homeassistant.const import (
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_NAME,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import ATTR_MAP, CONDITION_MAP, CONF_TRACK_HOME, DOMAIN, FORECAST_MAP
from .coordinator import MeteoAMConfigEntry, MeteoAMDataUpdateCoordinator

DEFAULT_NAME = "MeteoAM"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: MeteoAMConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add a weather entity from a config_entry."""
    coordinator = config_entry.runtime_data
    entity_registry = er.async_get(hass)

    name: str | None
    if config_entry.data.get(CONF_TRACK_HOME, False):
        name = hass.config.location_name
    else:
        name = config_entry.data.get(CONF_NAME, DEFAULT_NAME)
        if TYPE_CHECKING:
            assert isinstance(name, str)

    entities = [MeteoAMWeather(coordinator, config_entry, name)]

    # Remove hourly entity from legacy config entries
    if hourly_entity_id := entity_registry.async_get_entity_id(
        WEATHER_DOMAIN,
        DOMAIN,
        _calculate_unique_id(config_entry.data, True),
    ):
        entity_registry.async_remove(hourly_entity_id)

    async_add_entities(entities)


def _calculate_unique_id(config: Mapping[str, Any], hourly: bool) -> str:
    """Calculate unique ID."""
    name_appendix = ""
    if hourly:
        name_appendix = "-hourly"
    if config.get(CONF_TRACK_HOME):
        return f"home{name_appendix}"

    return f"{config[CONF_LATITUDE]}-{config[CONF_LONGITUDE]}{name_appendix}"


def format_condition(condition: str) -> str | None:
    """Return condition from CONDITION_LOOKUP, or None if unrecognised."""
    return CONDITION_MAP.get(condition)


class MeteoAMWeather(SingleCoordinatorWeatherEntity[MeteoAMDataUpdateCoordinator]):
    """Implementation of a MeteoAM weather condition."""

    _attr_attribution = (
        "Weather forecast from meteoam.it, delivered by the Aeronautica Militare."
    )
    _attr_has_entity_name = True
    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_native_pressure_unit = UnitOfPressure.HPA
    _attr_native_wind_speed_unit = UnitOfSpeed.KILOMETERS_PER_HOUR
    _attr_supported_features = (
        WeatherEntityFeature.FORECAST_DAILY | WeatherEntityFeature.FORECAST_HOURLY
    )

    def __init__(
        self,
        coordinator: MeteoAMDataUpdateCoordinator,
        config_entry: MeteoAMConfigEntry,
        name: str,
    ) -> None:
        """Initialise the platform with a data instance and site."""
        super().__init__(coordinator)
        self._attr_unique_id = _calculate_unique_id(config_entry.data, False)
        self._attr_device_info = DeviceInfo(
            name="Forecast",
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, config_entry.entry_id)},
            manufacturer="MeteoAM",
            model="Forecast",
            configuration_url="https://www.meteoam.it",
        )
        self._attr_track_home = config_entry.data.get(CONF_TRACK_HOME, False)
        self._attr_name = name

    @property
    def condition(self) -> str | None:
        """Return the current condition."""
        condition = self.coordinator.data.current_weather_data.get("icon")
        if condition is None:
            return None
        return format_condition(condition)

    @property
    def native_temperature(self) -> float | None:
        """Return the temperature."""
        return self.coordinator.data.current_weather_data.get(
            ATTR_MAP[ATTR_WEATHER_TEMPERATURE]
        )

    @property
    def native_pressure(self) -> float | None:
        """Return the pressure."""
        return self.coordinator.data.current_weather_data.get(
            ATTR_MAP[ATTR_WEATHER_PRESSURE]
        )

    @property
    def humidity(self) -> float | None:
        """Return the humidity."""
        return self.coordinator.data.current_weather_data.get(
            ATTR_MAP[ATTR_WEATHER_HUMIDITY]
        )

    @property
    def native_wind_speed(self) -> float | None:
        """Return the wind speed."""
        return self.coordinator.data.current_weather_data.get(
            ATTR_MAP[ATTR_WEATHER_WIND_SPEED]
        )

    @property
    def wind_bearing(self) -> float | str | None:
        """Return the wind direction."""
        return self.coordinator.data.current_weather_data.get(
            ATTR_MAP[ATTR_WEATHER_WIND_BEARING]
        )

    def _forecast(self, hourly: bool) -> list[Forecast] | None:
        """Return the forecast array."""
        if hourly:
            raw_forecast = self.coordinator.data.hourly_forecast
        else:
            raw_forecast = self.coordinator.data.daily_forecast
        required_keys = {
            FORECAST_MAP[ATTR_FORECAST_NATIVE_TEMP],
            FORECAST_MAP[ATTR_FORECAST_TIME],
        }
        ha_forecast: list[Forecast] = []
        for raw_item in raw_forecast:
            if not required_keys.issubset(raw_item):
                continue
            ha_item = {
                k: raw_item[v]
                for k, v in FORECAST_MAP.items()
                if raw_item.get(v) is not None
            }
            condition = ha_item.get(ATTR_FORECAST_CONDITION)
            if condition is not None:
                formatted = format_condition(condition)
                if formatted is not None:
                    ha_item[ATTR_FORECAST_CONDITION] = formatted
                else:
                    del ha_item[ATTR_FORECAST_CONDITION]
            ha_forecast.append(ha_item)  # type: ignore[arg-type]
        return ha_forecast

    @callback
    def _async_forecast_daily(self) -> list[Forecast] | None:
        """Return the daily forecast in native units."""
        return self._forecast(False)

    @callback
    def _async_forecast_hourly(self) -> list[Forecast] | None:
        """Return the hourly forecast in native units."""
        return self._forecast(True)
