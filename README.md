# Meteo Aeronautica Militare (MeteoAM) Integration for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg?&style=plastic)](https://github.com/hacs/integration)
![GitHub Release](https://img.shields.io/github/v/release/sibest19/hass-meteoam?sort=semver&display_name=release&style=plastic&link=https%3A%2F%2Fgithub.com%2Fsibest19%2Fhass-meteoam%2Freleases%2Flatest)
![Installation Count](https://img.shields.io/badge/dynamic/json?color=41BDF5&logo=home-assistant&style=plastic&label=integration%20usage&suffix=%20installs&cacheSeconds=15600&url=https://analytics.home-assistant.io/custom_integrations.json&query=$.meteoam.total)

A Home Assistant custom component that provides weather data from the Italian Air Force meteorological service ([Aeronautica Militare](https://www.meteoam.it)).

## Features

- **Current weather conditions**: temperature, humidity, pressure, wind speed & bearing, precipitation probability
- **Daily forecast** with high/low temperatures, condition icons, and precipitation probability
- **Hourly forecast** with full weather details including precipitation probability
- **Track home location**: automatically updates when your Home Assistant home location changes
- **Multiple locations**: configure as many weather entities as you need
- **20 weather condition icons** mapped to Home Assistant states, including day and night variants

### Supported Weather Conditions

| Icon Code | Condition | Description |
|-----------|-----------|-------------|
| 01, 02 | Sunny | Clear sky / mostly clear |
| 03, 13, 14 | Fog | Fog / mist / haze |
| 04, 05 | Partly cloudy | Partially covered sky / mostly cloudy |
| 06, 07 | Cloudy | Overcast |
| 08 | Rainy | Rain |
| 09, 15 | Pouring | Heavy rain |
| 10 | Lightning & rain | Thunderstorm with rain |
| 11, 12 | Snowy & rainy | Sleet / mixed precipitation |
| 16 | Snowy | Snow |
| 17, 19 | Exceptional | Storm / sand storm |
| 18 | Windy | Strong wind |
| 31 | Clear night | Clear sky at night |
| 32, 33 | Fog (night) | Slight fog / fog at night |
| 34, 35 | Partly cloudy (night) | Partially covered sky at night |
| 36 | Cloudy (night) | Overcast at night |

## Requirements

- Home Assistant **2025.2** or newer
- A supported Home Assistant installation supplies its own Python runtime. For development, Python **3.13** tests the minimum HA version; current HA releases require Python **3.14.2** or newer.

## Installation

### Home Assistant 2026.11 or newer

1. Open **Settings → Marketplace**, accept the community software notice, and find **Meteo Aeronautica Militare (MeteoAM)**.
2. Select **Install**. On a first installation, Home Assistant opens the setup flow without requiring a restart.
3. Enter the location details and save. If you closed setup, open **Settings → Devices & services → Add integration** and search for **MeteoAM**.

Updates to an already loaded integration still require a Home Assistant restart; follow the Marketplace prompt.

### Home Assistant 2025.2 through 2026.10

1. Install MeteoAM using [HACS](https://github.com/hacs/integration).
2. Restart Home Assistant.
3. Open **Settings → Devices & services → Add integration**, search for **MeteoAM**, and enter the location details.

### Upgrading from HACS to Marketplace

Home Assistant 2026.11 automatically migrates HACS installations to Marketplace. Keep MeteoAM installed and configured: do not uninstall it or recreate its entries. The migration is intended to retain installed repositories and their update entities. See the [official migration guide](https://next.home-assistant.io/integrations/marketplace/#coming-from-hacs).

### Manual installation

Copy `custom_components/meteoam` into `<config_dir>/custom_components`, restart Home Assistant, then add **MeteoAM** under **Settings → Devices & services**. Restart after replacing the integration files to update it.

## Configuration

During setup you can provide:

| Option | Description |
|--------|-------------|
| **Name** | A friendly name for the weather entity |
| **Latitude** | Latitude of the location (defaults to your home) |
| **Longitude** | Longitude of the location (defaults to your home) |

You can reconfigure latitude and longitude later via the integration's **Options** flow.

### Exposed Attributes

| Attribute | Source | Unit |
|-----------|--------|------|
| Temperature | `2t` | °C |
| Humidity | `r` | % |
| Pressure | `pmsl` | hPa |
| Wind speed | `wkmh` | km/h |
| Wind bearing | `wdir` | ° |
| Precipitation probability | `tpp` | % |
| Condition | `icon` | — |

## Data Source

Weather forecast data is fetched from the MeteoAM API (`api.meteoam.it`), which provides ECMWF-based model output:

- **Hourly forecast**: up to ~4 days ahead (hourly for 3 days, then 3-hourly)
- **Daily forecast**: up to 5 days ahead with min/max temperatures and precipitation probability (derived as the max hourly value per day, since the API only provides it hourly)
- **Update interval**: approximately every 60 minutes (randomized 55–65 min)

## Development

### Prerequisites

- [uv](https://docs.astral.sh/uv/) — fast Python package manager
- [Docker](https://www.docker.com/) — for running Home Assistant locally

### Quick Start

```bash
# 1. Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh
# or: brew install uv

# 2. Clone the repo
git clone https://github.com/sibest19/hass-meteoam.git
cd hass-meteoam

# 3. Install dependencies and pre-commit hooks
make setup

# 4. Start Home Assistant
make ha
# Open http://localhost:8123 and set up your instance
# The meteoam integration is already available under Settings → Devices & Services
```

### Project Structure

```
hass-meteoam/
├── custom_components/
│   └── meteoam/            # The integration source code
│       ├── __init__.py      # Integration setup & teardown
│       ├── config_flow.py   # Config & options flow UI
│       ├── const.py         # Constants, condition maps
│       ├── coordinator.py   # Data update coordinator (API calls)
│       ├── manifest.json    # Integration metadata
│       ├── weather.py       # Weather entity platform
│       └── translations/    # Finished UI strings (en.json)
├── config/                  # HA runtime config (gitignored, except seed)
│   └── configuration.yaml   # Seed HA configuration
├── scripts/
│   └── setup                # One-command dev environment setup
├── .devcontainer/
│   └── devcontainer.json    # VS Code devcontainer config
├── docker-compose.yml       # Runs HA with custom_components mounted
├── pyproject.toml           # Project config: deps, ruff, pytest
├── Makefile                 # Dev workflow commands
└── .pre-commit-config.yaml  # Pre-commit hooks (ruff)
```

### Make Commands

| Command | Description |
|---------|-------------|
| `make help` | Show all available commands |
| `make setup` | Install dev dependencies and pre-commit hooks |
| `make lint` | Run ruff linter on source code |
| `make format` | Auto-format code with ruff |
| `make test` | Run tests with pytest |
| `make ha` | Start Home Assistant via Docker (http://localhost:8123) |
| `make ha-stop` | Stop the Home Assistant container |
| `make ha-restart` | Restart HA to pick up code changes |
| `make ha-logs` | Follow Home Assistant logs |
| `make clean` | Remove caches and build artifacts |

### Development Workflow

1. **Start HA** — `make ha` launches a Home Assistant instance with your `custom_components/` directory mounted. Any file changes to your integration are immediately available inside the container.

2. **Edit code** — Make changes to files in `custom_components/meteoam/`.

3. **Restart to apply** — Run `make ha-restart` to restart Home Assistant and load your changes. Check `make ha-logs` for errors.

4. **Lint & format** — Run `make lint` to check for issues, `make format` to auto-fix formatting. Pre-commit hooks run these automatically on `git commit`.

5. **Test** — Run `make test` to execute the test suite.

### Compatibility tests

CI tests **HA 2025.2.0 / Python 3.13**, **HA 2026.10.4 / Python 3.14**, and **HA 2026.11.0 / Python 3.14** on pull requests and daily. Tests use real Home Assistant setup, registries, weather services, options changes, home-location tracking, reloads, unloads, and English translations. Weather responses are mocked.

The local `.python-version` remains at 3.13 for older-version development. To reproduce one exact CI target in a separate environment:

```bash
uv venv --python 3.14 /tmp/meteoam-test
uv export --locked --only-group test --no-hashes --no-emit-project --output-file /tmp/meteoam-test-requirements.txt
uv pip install --python /tmp/meteoam-test/bin/python -r /tmp/meteoam-test-requirements.txt 'homeassistant==2026.11.0'
uv pip check --python /tmp/meteoam-test/bin/python
/tmp/meteoam-test/bin/python -m pytest tests/
```

Use Python 3.13 and `homeassistant==2025.2.0` to check the minimum. CI verifies the installed HA version explicitly. These runtime tests do not replace a complete HACS-to-Marketplace upgrade rehearsal.

### Tooling

| Tool | Purpose |
|------|---------|
| [uv](https://docs.astral.sh/uv/) | Python dependency management (replaces pip/poetry) |
| [Ruff](https://docs.astral.sh/ruff/) | Linting & formatting (replaces flake8, black, isort) |
| [pytest](https://docs.pytest.org/) | Test framework |
| [pytest-asyncio](https://pytest-asyncio.readthedocs.io/) | Async tests and disposable Home Assistant fixtures |
| [pre-commit](https://pre-commit.com/) | Git hook manager for automated checks |

### VS Code Devcontainer

This repo includes a [devcontainer](.devcontainer/devcontainer.json) configuration. When you open the project in VS Code (or GitHub Codespaces), you'll be prompted to **Reopen in Container** — this gives you a fully configured Python environment with Ruff, Pylance, and all dependencies pre-installed.

### Docker Setup Details

The `docker-compose.yml` runs the official Home Assistant container with two volume mounts:

- `./config` → `/config` — HA configuration directory (persisted locally)
- `./custom_components` → `/config/custom_components` — your integration code (live-mounted)

The `config/` directory is gitignored except for the seed `configuration.yaml`. After first run, HA will create its database, auth, and other files there.

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
