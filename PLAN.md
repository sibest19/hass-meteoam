# Modernization Plan: MeteoAM Custom Component

> **Status**: Complete  
> **Target HA version**: 2025.1+  
> **Current version**: 1.0.0 → **Target version**: 2.0.0  
> **Reference**: [Met.no official integration](https://github.com/home-assistant/core/tree/1c19ddba55bec667228463b73358cb66e92c5d75/homeassistant/components/met)

This component fetches weather data from the Italian Air Force (Aeronautica Militare) API at `api.meteoam.it`. It hadn't been updated in ~3 years and needed modernization to align with current Home Assistant best practices.

---

## Steps

### 1. Update project metadata

**Files**: `hacs.json`, `manifest.json`, `requirements-dev.txt`

- [x] `hacs.json`: bump `homeassistant` to `"2025.1.0"`
- [x] `manifest.json`:
  - Change `iot_class` from `"local_polling"` to `"cloud_polling"`
  - Add `"integration_type": "service"`
  - Update `codeowners` to `["@sibest19"]`
  - Update `documentation` to `"https://github.com/sibest19/hass-meteoam"`
  - Update `issue_tracker` to `"https://github.com/sibest19/hass-meteoam/issues"`
  - Bump `version` to `"2.0.0"`
  - Remove empty `"dependencies": []`
- [x] `requirements-dev.txt`: update to modern dev tooling (`pre-commit>=4.0`, `ruff`, `pytest`, `pytest-homeassistant-custom-component`)

### 2. Extract coordinator into `coordinator.py`

**Files**: NEW `custom_components/meteoam/coordinator.py`, `custom_components/meteoam/__init__.py`

- [x] Create `coordinator.py` with `MeteoAMDataUpdateCoordinator`, `MeteoAMWeatherData`, `CannotConnect`
- [x] Add typed config entry alias: `type MeteoAMConfigEntry = ConfigEntry[MeteoAMDataUpdateCoordinator]`
- [x] Pass `config_entry=config_entry` to `DataUpdateCoordinator.__init__()`
- [x] Fix `self._weather_data: None` → `self._session: ClientSession | None = None`
- [x] Replace `dateutil.parser.parser()` with `dt_util.parse_datetime()` (removes undeclared dependency)
- [x] Fix timezone handling: stop stripping tzinfo and re-localizing manually
- [x] Use `aiohttp.ClientTimeout(total=60)` instead of bare `timeout=60`
- [x] Use `UpdateFailed` with `translation_domain`/`translation_key` for translatable errors
- [x] Remove bare `except Exception` catch-and-rethrow

### 3. Slim down `__init__.py`

**File**: `custom_components/meteoam/__init__.py`

- [x] Use `config_entry.runtime_data = coordinator` instead of `hass.data[DOMAIN]`
- [x] Remove `hass.data.setdefault(DOMAIN, {})` and all `hass.data[DOMAIN]` references
- [x] Remove `async_update_entry()` listener (replaced by `OptionsFlowWithReload`)
- [x] Use `MeteoAMConfigEntry` type alias
- [x] Fix log: `"met.no integration"` → `"MeteoAM integration"`
- [x] Simplify `async_unload_entry` to use `config_entry.runtime_data`
- [x] Add `_cleanup_old_device()` to remove devices with broken `(DOMAIN,)` identifiers from v1

### 4. Modernize `config_flow.py`

**File**: `custom_components/meteoam/config_flow.py`

- [x] Replace deprecated `FlowResult` with `ConfigFlowResult`
- [x] Replace `MeteoAMOptionsFlowHandler(OptionsFlow)` with `OptionsFlowWithReload`
- [x] Use `self.config_entry` (from base class) instead of manual `self._config_entry`
- [x] Remove unnecessary `__init__` from `MeteoAMConfigFlowHandler`
- [x] Keep `configured_instances()` dedup approach (consistent with Met.no)

### 5. Modernize `weather.py`

**File**: `custom_components/meteoam/weather.py`

- [x] Use `MeteoAMConfigEntry` type alias
- [x] Replace `AddEntitiesCallback` with `AddConfigEntryEntitiesCallback`
- [x] Get coordinator from `config_entry.runtime_data`
- [x] Remove deprecated `forecast` property (entity already has `_async_forecast_daily`/`_async_forecast_hourly`)
- [x] Remove legacy hourly entity handling; add cleanup for legacy `-hourly` entity IDs
- [x] Fix `device_info` identifiers: `(DOMAIN,)` → `(DOMAIN, config_entry.entry_id)`
- [x] Fix `name` / `_attr_has_entity_name` — set `_attr_name` in `__init__`
- [x] Replace `MappingProxyType` with `Mapping` from `collections.abc`
- [x] Remove unused `_is_metric` parameter

### 6. Fix `const.py`

**File**: `custom_components/meteoam/const.py`

- [x] Change default coordinates from Amsterdam → Rome (41.9028, 12.4964)
- [x] Map icon codes `"17"`, `"19"` → `ATTR_CONDITION_EXCEPTIONAL`, `"18"` → `ATTR_CONDITION_WINDY`
- [x] Remove unused imports (`ATTR_WEATHER_VISIBILITY`, `WEATHER_DOMAIN`)
- [x] Remove unused `ENTITY_ID_SENSOR_FORMAT_HOME` constant

### 7. Update `strings.json`

**File**: `custom_components/meteoam/strings.json`

- [x] Add `"exceptions"` section with `"update_failed"` translation key
- [x] Fix typo: "Aereonautica" → "Aeronautica"

### 8. Update README

**File**: `README.md`

- [x] Update links/badges to `sibest19/hass-meteoam`
- [x] Note minimum HA version 2025.1
- [x] Add feature description and configuration docs

---

## Verification

- `python -m py_compile custom_components/meteoam/*.py` — no syntax errors
- Install in HA dev environment and verify:
  - Config flow creates entry successfully
  - Options flow updates location and reloads
  - Weather entity shows current conditions + daily/hourly forecasts
  - Multiple locations get separate devices
  - Removing integration cleans up properly
- HACS validation passes

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Min HA version | 2025.1+ | Enables all modern APIs (`OptionsFlowWithReload`, `ConfigFlowResult`, `runtime_data`, type alias) |
| Coordinator file | Separate `coordinator.py` | Matches official integration pattern, cleaner separation |
| `dateutil` dependency | Remove entirely | Replace with built-in `dt_util.parse_datetime()` — zero external deps |
| Default coordinates | Rome (41.9028, 12.4964) | Italian weather service, Amsterdam was a copy-paste artifact |
| Version | 2.0.0 | Breaking: device identifiers change (old devices auto-cleaned) |
| Hourly legacy entity | Remove + cleanup | Modern forecast service makes separate hourly entity unnecessary |