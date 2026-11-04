# Contributing

Report bugs and propose changes through [GitHub issues](https://github.com/sibest19/hass-meteoam/issues), or open a pull request. Include Home Assistant and MeteoAM versions, reproduction steps and relevant logs when reporting a bug. Remove credentials and personal information from logs.

## Development setup

Install [uv](https://docs.astral.sh/uv/) and, to run Home Assistant locally, Docker with Compose. The repository’s `.python-version` selects Python 3.13 for older-version development; current HA test targets use Python 3.14.2 or newer.

```bash
git clone https://github.com/sibest19/hass-meteoam.git
cd hass-meteoam
make setup
```

`make setup` installs development dependencies and pre-commit hooks. A VS Code devcontainer is also available.

## Run Home Assistant locally

```bash
make ha
```

Open http://localhost:8123, complete onboarding, and add **MeteoAM** under **Settings → Devices & services**. The integration source is mounted into the container. After editing it, run `make ha-restart` to load the changes.

Local HA configuration is stored in `config/` and is ignored by Git, apart from the seed configuration. The development container uses the official stable HA image; it does not replace testing against the minimum supported version.

| Command | Purpose |
|---------|---------|
| `make ha-logs` | Follow Home Assistant logs |
| `make ha-restart` | Restart after integration changes |
| `make ha-stop` | Stop the development container |
| `make lint` | Run Ruff |
| `make format` | Apply formatting and lint fixes |
| `make test` | Run tests in the local uv environment |
| `make help` | List available commands |

## Compatibility tests

Keep compatibility with **Home Assistant 2025.2.0**. CI runs on pull requests, daily and manually against:

| Home Assistant | Python | Coverage |
|----------------|--------|----------|
| 2025.2.0 | 3.13 | Minimum supported version |
| 2026.10.4 | 3.14 | HACS before the Marketplace transition |
| 2026.11.0 | 3.14 | Built-in Marketplace |

Tests use real Home Assistant setup, config flows, registries and weather services. They cover options changes, home tracking, reload/unload, ID and custom-name retention, and English translations. External weather responses are mocked, and network discovery is disabled.

To reproduce an exact target in a separate environment:

```bash
uv venv --python 3.14 /tmp/meteoam-test
uv export --locked --only-group test --no-hashes --no-emit-project --output-file /tmp/meteoam-test-requirements.txt
uv pip install --python /tmp/meteoam-test/bin/python -r /tmp/meteoam-test-requirements.txt 'homeassistant==2026.11.0'
uv pip check --python /tmp/meteoam-test/bin/python
/tmp/meteoam-test/bin/python -m pytest tests/
```

Use Python 3.13 and `homeassistant==2025.2.0` for the minimum version. CI asserts the installed HA version explicitly; `make test` alone uses whichever version the local lockfile and Python select.

Runtime tests do not replace a full HACS-to-Marketplace migration rehearsal. In the disposable upgrade check, Marketplace adopted seeded legacy HACS storage, retained IDs and names, and successfully downloaded a published release through its real installer. This did not exercise a signed-in HACS account or a household configuration.

## Code and pull requests

Integration code lives in `custom_components/meteoam/`; tests live in `tests/`. Weather condition and API field mappings are in `const.py`, API fetching and parsing are in `coordinator.py`, and finished English UI strings belong in `translations/en.json`.

1. Keep changes focused and preserve existing entity IDs and configuration unless a migration is necessary.
2. Add tests for changed behavior, including the minimum HA version when using new HA APIs.
3. Run `make lint` and `make test` before opening a PR. Pre-commit hooks check formatting and file validity.
4. Explain the user-visible change, how it was verified, and any remaining limitations in the PR description.

CI also runs hassfest and HACS validation. The HACS validator remains relevant for Marketplace because it uses the same catalog and `hacs.json`.
