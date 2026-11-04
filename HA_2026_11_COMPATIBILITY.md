# Home Assistant 2026.11 compatibility

Verified November 4, 2026. Minimum supported HA remains **2025.2.0**.

## Changes

- Replace APIs absent in HA 2025.2: use `OptionsFlow` with explicit reload when configuration data changes, and `AddEntitiesCallback` for the weather platform.
- Ship complete English strings in `custom_components/meteoam/translations/en.json`. Custom integrations do not receive the core compilation step for `strings.json`; unresolved references were replaced with literal strings.
- Test exact HA/Python targets in CI, using locked test dependencies and asserting the installed HA version. Run on PRs, daily, and manually.
- Remove the unused `pytest-homeassistant-custom-component` dependency. Its HA pins prevented current-version testing; tests use `pytest-asyncio` and a small disposable HA fixture.
- Document Marketplace for HA 2026.11+, HACS for older supported HA, automatic migration, manual installation and restarts after updates.

No config-entry migration, unique-ID change, or minimum-version increase is introduced.

## Local validation

All 45 tests passed on each of:

- HA 2025.2.0 / Python 3.13
- HA 2026.10.4 / Python 3.14
- HA 2026.11.0 / Python 3.14

The maintained tests exercise real HA loading, config flows, registries, current weather, daily/hourly forecast services, options changes, home-location tracking, reloads, unloads and English translations. Weather responses are mocked, and multicast DNS is replaced with a standard DNS resolver. Tests also reject unexpected error logs.

Ruff lint/format, lockfile validation, dependency consistency checks and hassfest passed. CI performs the exact-version checks independently of the HA version selected for local development by `.python-version`.

## Upgrade rehearsal

A disposable persisted HA 2026.10.4 configuration containing fixed and home-tracking MeteoAM entries was bootstrapped on HA 2026.11.0. Config-entry, device and entity IDs, a custom name and a template reference survived; current weather and both forecast services worked.

The actual Marketplace adopted seeded legacy HACS version-6 storage, retained MeteoAM as an installed repository, preserved its update entity ID/name, and removed the old HACS files. Its installer then downloaded the already published `v2.2.1-beta.1`, validated the manifest and created the expected restart repair. A new HA process loaded that downloaded version with IDs, names and forecasts preserved.

This exercised the public install path using an existing published release, not the unpublished fixes in this change. HACS storage was seeded rather than exported from a signed-in HACS account. No household configuration was touched. A full account-backed migration remains untested.

## Developer changes checked

- Boolean setup/unload return values remain supported for custom integrations in HA 2026.11.
- MeteoAM already constructs `DeviceInfo` using keyword arguments compatible with its new dataclass implementation.
- Both forms supply `step_id`.
- MeteoAM does not override the entity lifecycle hooks affected by in-place entity-ID changes.
- Manifest categories remain optional for custom integrations.
- HA's display-name changes may alter visible context; existing entity IDs are preserved according to the official announcement.

## Limits and adoption data

Public analytics lists MeteoAM release totals and global HA versions separately. It does not expose the HA-version distribution for MeteoAM installations. Counts are opt-in, grouped by the `meteoam` domain and may include other forks. They do not justify dropping older HA support. See [the implementation plan](HA_COMPATIBILITY_PLAN.md) for the sampled release counts and scope.

Weather API availability and schema changes remain independent external risks. Runtime checks use mocked weather responses. No compatibility below HA 2025.2 is claimed.

## Primary sources

- [HA 2026.11 stable release](https://github.com/home-assistant/core/releases/tag/2026.11.0)
- [Final release notes](https://www.home-assistant.io/blog/2026/11/04/release-202611/)
- [Marketplace migration and usage](https://next.home-assistant.io/integrations/marketplace/)
- [Publishing custom integrations](https://contributors.home-assistant.io/marketplace/guides/integrations/)
- [Marketplace validation](https://contributors.home-assistant.io/marketplace/reference/validation/)
- [Custom integration translations](https://contributors.home-assistant.io/core/integrations/translations/#custom-integrations)
- [Config-entry return values](https://contributors.home-assistant.io/blog/2026/10/23/config-entry-methods-return-none/)
- [DeviceInfo dataclass](https://contributors.home-assistant.io/blog/2026/10/13/device-info-class/)
- [Entity lifecycle changes](https://contributors.home-assistant.io/blog/2026/10/12/new-entity-lifecycle-hooks/)
- [Entity naming](https://www.home-assistant.io/blog/2026/11/03/naming-things-in-home-assistant/)
- [Public analytics datasets](https://contributors.home-assistant.io/data/guides/public-data/)
