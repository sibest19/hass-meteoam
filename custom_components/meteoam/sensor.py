"""Support for MeteoAM station observation sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    DEGREE,
    PERCENTAGE,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import MeteoAMConfigEntry, MeteoAMStationCoordinator


@dataclass(frozen=True, kw_only=True)
class MeteoAMSensorEntityDescription(SensorEntityDescription):
    """Describe a MeteoAM station observation sensor."""

    value_fn: Callable[[dict[str, Any]], float | str | None]


SENSOR_TYPES: tuple[MeteoAMSensorEntityDescription, ...] = (
    MeteoAMSensorEntityDescription(
        key="observed_temperature",
        translation_key="observed_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda data: data.get("2t"),
    ),
    MeteoAMSensorEntityDescription(
        key="observed_humidity",
        translation_key="observed_humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda data: data.get("r"),
    ),
    MeteoAMSensorEntityDescription(
        key="observed_pressure",
        translation_key="observed_pressure",
        device_class=SensorDeviceClass.ATMOSPHERIC_PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPressure.HPA,
        value_fn=lambda data: data.get("pmsl"),
    ),
    MeteoAMSensorEntityDescription(
        key="observed_wind_speed",
        translation_key="observed_wind_speed",
        device_class=SensorDeviceClass.WIND_SPEED,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        value_fn=lambda data: data.get("wkmh"),
    ),
    MeteoAMSensorEntityDescription(
        key="observed_wind_bearing",
        translation_key="observed_wind_bearing",
        native_unit_of_measurement=DEGREE,
        value_fn=lambda data: data.get("wdir"),
    ),
    MeteoAMSensorEntityDescription(
        key="observed_wind_cardinal",
        translation_key="observed_wind_cardinal",
        value_fn=lambda data: data.get("wcar"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: MeteoAMConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up MeteoAM station observation sensors."""
    station_coordinator = config_entry.runtime_data.station
    assert station_coordinator is not None  # noqa: S101

    async_add_entities(
        MeteoAMObservationSensor(station_coordinator, config_entry, description)
        for description in SENSOR_TYPES
    )


class MeteoAMObservationSensor(
    CoordinatorEntity[MeteoAMStationCoordinator], SensorEntity
):
    """Representation of a MeteoAM station observation sensor."""

    entity_description: MeteoAMSensorEntityDescription

    _attr_attribution = (
        "Weather observations from meteoam.it, "
        "delivered by the Aeronautica Militare."
    )
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MeteoAMStationCoordinator,
        config_entry: MeteoAMConfigEntry,
        description: MeteoAMSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{config_entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            name="Forecast",
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, config_entry.entry_id)},
            manufacturer="MeteoAM",
            model="Forecast",
            configuration_url="https://www.meteoam.it",
        )

    @property
    def native_value(self) -> float | str | None:
        """Return the sensor value."""
        if self.coordinator.data is None:
            return None
        return self.entity_description.value_fn(
            self.coordinator.data.current_observation
        )
