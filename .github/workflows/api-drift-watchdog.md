---
# API drift watchdog: detects when the undocumented MeteoAM API changes shape
# in a way that would break custom_components/meteoam/coordinator.py parsing.
#
# Engine: uses the repo default (GitHub Copilot). To use Claude or Codex instead,
# add e.g. `engine: claude` and provide the matching secret (ANTHROPIC_API_KEY).
on:
  schedule: daily # fuzzy daily schedule (scattered execution time)
  workflow_dispatch: # allow manual runs

# Read-only against the repo. Issue creation is handled by the safe-outputs job
# below with its own scoped permissions.
permissions:
  contents: read
  issues: read

# The agent must reach the live MeteoAM API in addition to the defaults.
network:
  allowed:
    - defaults
    - "api.meteoam.it"

tools:
  bash: ["curl", "jq"]

safe-outputs:
  create-issue:
    title-prefix: "[api-drift] "
    labels: [api-drift, automated, upstream]
    max: 1

timeout-minutes: 15
---

# MeteoAM API drift watchdog

The `meteoam` Home Assistant integration parses an **undocumented** upstream API.
When that API changes shape, `custom_components/meteoam/coordinator.py` breaks
silently for every user at once. Your job is to detect such drift *before* users
report it, and open a single issue describing exactly what changed.

## What to fetch

Query the live meteogram endpoint for two fixed locations (Rome and Milan):

```bash
curl -sS -H 'Origin: https://www.meteoam.it' -H 'Referer: https://www.meteoam.it/' \
  'https://api.meteoam.it/deda-meteograms/api/GetMeteogram/preset1/41.9027835,12.4963655'
curl -sS -H 'Origin: https://www.meteoam.it' -H 'Referer: https://www.meteoam.it/' \
  'https://api.meteoam.it/deda-meteograms/api/GetMeteogram/preset1/45.4642,9.1900'
```

Use `jq` to inspect structure. Do **not** assume the response shape — read it.

## The contract the integration depends on

`coordinator.py::_parse_data` reads exactly these, so verify each one is present
and has the expected type in the live responses:

1. `.timeseries` — a non-empty **array of ISO datetime strings**.
2. `.paramlist` — an **array of parameter-name strings**. It MUST contain every
   parameter the integration maps (see `custom_components/meteoam/const.py`):
   `2t`, `tpp`, `icon`, `wdir`, `wkmh`, `r`, `pmsl`.
3. `.datasets["0"]` — an **object keyed by param index** (`"0"`, `"1"`, …), each
   value an object keyed by time index (`"0"`, `"1"`, …). The number of param
   keys must match `paramlist` length; each series must cover the `timeseries`
   indices.
4. `.extrainfo.stats` — a **non-empty array** of daily objects, each with keys
   `localDate`, `maxCelsius`, `minCelsius`, `icon`. (The `"-"` placeholder for
   trailing days with no model data is expected and NOT drift.)
5. **Icon codes**: collect every distinct value of the `icon` param (hourly) and
   of `.extrainfo.stats[].icon` (daily). Flag any code that is **not** one of the
   codes handled in `const.py` `CONDITIONS_MAP`:
   `01 02 03 04 05 06 07 08 09 10 11 12 13 14 15 16 17 18 19 31 32 33 34 35 36`.
   An unmapped code silently produces no weather condition, so it is worth an issue.

Before flagging, open and read `custom_components/meteoam/coordinator.py` and
`custom_components/meteoam/const.py` in the repo to confirm the current contract —
the lists above are a guide, the code is the source of truth.

## When to open an issue — and when NOT to

Open **one** issue **only if** you find a genuine deviation, i.e. any of:

- a required top-level key (`timeseries`, `paramlist`, `datasets`, `extrainfo`)
  missing or the wrong type;
- a required parameter absent from `paramlist`;
- `datasets["0"]` param/time indices not lining up with `paramlist`/`timeseries`;
- a required `extrainfo.stats` key missing on days that DO have data;
- one or more icon codes not in the known set above.

Do **NOT** open an issue for: transient network errors or non-200 responses
(mention them only if BOTH locations fail — that itself is worth reporting);
`"-"` placeholders in trailing stats days; extra/new parameters that the
integration simply ignores (report those as an informational note within an
issue only if you are already opening one for another reason).

If everything matches the contract, do nothing (no issue). Silence means healthy.

## Issue content

If you open an issue:

- **Title**: a short, specific summary (e.g. `paramlist missing "tpp" for Rome`).
- **Body** must include:
  - which location(s) exhibited the drift and the date (UTC) of the check;
  - the specific expectation that failed and the actual observed value/shape;
  - the exact `coordinator.py` / `const.py` lines that rely on the changed field,
    so a maintainer can jump straight to the fix;
  - a minimal `jq` snippet reproducing the observation;
  - for unmapped icon codes: the code(s), which location/time exhibited them, and
    a suggested Home Assistant condition mapping if you can infer it.
