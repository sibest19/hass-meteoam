# Meteo Aeronautica Militare (MeteoAM) Integration for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg?&style=plastic)](https://github.com/hacs/integration)
![GitHub Release](https://img.shields.io/github/v/release/sibest19/hass-meteoam?sort=semver&display_name=release&style=plastic&link=https%3A%2F%2Fgithub.com%2Fsibest19%2Fhass-meteoam%2Freleases%2Flatest)
![Installation Count](https://img.shields.io/badge/dynamic/json?color=41BDF5&logo=home-assistant&style=plastic&label=integration%20usage&suffix=%20installs&cacheSeconds=15600&url=https://analytics.home-assistant.io/custom_integrations.json&query=$.meteoam.total)

Weather conditions and forecasts from the Italian Air Force meteorological service ([Aeronautica Militare](https://www.meteoam.it)) for Home Assistant **2025.2 or newer**.

## Features

- Current conditions, temperature, humidity, pressure, wind speed and direction.
- Daily and hourly forecasts with precipitation probability.
- Multiple locations and support for tracking your Home Assistant home location.
- Updates approximately every hour, with forecasts up to four days hourly and five days daily.

## Installation

[![Open MeteoAM in HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=sibest19&repository=hass-meteoam&category=integration)

### Home Assistant 2026.11 or newer

Open **Settings → Marketplace**, accept the community software notice, and install **Meteo Aeronautica Militare (MeteoAM)**. First installation opens setup directly; updates to an already loaded integration require a restart.

### Home Assistant 2025.2 through 2026.10

Install MeteoAM through [HACS](https://github.com/hacs/integration), then restart Home Assistant.

### Manual installation

Copy `custom_components/meteoam` into `<config_dir>/custom_components` and restart Home Assistant. Restart after replacing the files for an update, too.

When upgrading Home Assistant to 2026.11, HACS migrates to Marketplace automatically. Keep MeteoAM installed and configured; there is no need to recreate its entries. See the [official migration guide](https://next.home-assistant.io/integrations/marketplace/#coming-from-hacs).

## Setup and use

1. If setup did not open automatically, go to **Settings → Devices & services → Add integration** and search for **MeteoAM**.
2. Enter a name, latitude and longitude. Coordinates default to your home location. Add the integration again for each additional location.
3. Add the resulting weather entity to a dashboard weather card. Use the integration’s **Configure** button to change the name or coordinates later.

Temperature is reported in °C, pressure in hPa, wind speed in km/h and precipitation probability in percent. Home Assistant handles display-unit conversion. Daily precipitation probability is the highest hourly value available for that day.

## Contributing

Bug reports and pull requests are welcome. For bugs, include your Home Assistant version, MeteoAM version, relevant logs and steps to reproduce in a [GitHub issue](https://github.com/sibest19/hass-meteoam/issues).

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, tests and compatibility checks.

## Version Adoption

- [Current Distribution](https://github.com/sibest19/hass-meteoam/blob/version-history/versions.md)

## Star History

<a href="https://www.star-history.com/?repos=sibest19%2Fhass-meteoam&type=date&legend=top-left">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/chart?repos=sibest19/hass-meteoam&type=date&theme=dark&legend=top-left" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/chart?repos=sibest19/hass-meteoam&type=date&legend=top-left" />
   <img alt="Star History Chart" src="https://api.star-history.com/chart?repos=sibest19/hass-meteoam&type=date&legend=top-left" />
 </picture>
</a>

## Credits

This project is a fork of the original [hass-meteoam](https://github.com/wilds/hass-meteoam) by [@wilds](https://github.com/wilds). Huge thanks for building the foundation of this integration.

Weather data provided by [Aeronautica Militare](https://www.meteoam.it) — the Italian Air Force meteorological service.

## Disclaimer

This is an **unofficial** custom component and is **not affiliated with, endorsed by, or connected to** Aeronautica Militare, MeteoAM, or any related entity. All registered trademarks, service marks, and brand names are the property of their respective owners.
