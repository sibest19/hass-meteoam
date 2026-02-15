# MeteoAM GetStationRadius API

Reference documentation for the `GetStationRadius` endpoint, to be used in a future iteration to add real-time weather station observations.

## Endpoint

```
GET https://api.meteoam.it/deda-ows/api/GetStationRadius/{lat}/{lon}
```

Note the path uses `/lat/lon` (separate segments), unlike the meteogram endpoint which uses `lat,lon` (comma-separated).

## Headers

- `Origin: https://www.meteoam.it`
- `Referer: https://www.meteoam.it/`
- `Accept: application/json`

## Response Structure

```jsonc
{
  // Coordinates of the matched weather station (NOT the requested coords)
  "pointlist": [[43.61666667, 13.36027778]],

  // Parameters available (same meaning as preset1, minus tpp/2tf)
  "paramlist": ["2t", "r", "pmsl", "wdir", "wcar", "wspd", "wkmh", "2tf", "icon"],

  "extrainfo": {
    "elapsed": 0.000012,
    "station_name": ["Ancona - Falconara"],   // Human-readable station name
    "station_icao": ["LIPY"],                  // ICAO airport code
    "station_min_max": [[                      // Daily min/max for last 3 days
      {
        "localDate": "2026-02-14T00:00:00+01:00",
        "maxCelsius": 13, "minCelsius": 7,
        "maxFahrenheit": 55, "minFahrenheit": 45
      },
      // ... 2 more days
    ]],
    "timezone": "Europe/Rome"
  },

  // Observation timestamps — REVERSE chronological order (newest first)
  // Goes back ~5 days, hourly resolution
  "timeseries": [["2026-02-15T09:00:00Z", "2026-02-15T08:00:00Z", ...]],

  // Observation data — same indexed structure as preset1
  "datasets": {
    "0": {
      "0": {"0": 12, "1": 10, ...},  // 2t  — temperature (°C)
      "1": {"0": 66, "1": 100, ...}, // r   — relative humidity (%)
      "2": {"0": 1004, ...},         // pmsl — pressure (hPa)
      "3": {"0": 20, "1": 320, ...}, // wdir — wind direction (degrees, or "VRB")
      "4": {"0": "N-NE", ...},       // wcar — wind cardinal direction
      "5": {"0": 18, ...},           // wspd — wind speed (knots)
      "6": {"0": 33, ...}            // wkmh — wind speed (km/h)
      // Note: NO icon or 2tf in datasets despite being in paramlist
    }
  }
}
```

## Key Differences from GetMeteogram/preset1

| Aspect | preset1 (Forecast) | GetStationRadius (Observations) |
|--------|-------------------|--------------------------------|
| Data type | Model forecast | Actual SYNOP/METAR observations |
| Time direction | Forward (future) | Backward (past ~5 days) |
| Time order | Chronological | Reverse chronological |
| Location | Exact lat/lon requested | Nearest weather station |
| `tpp` (precip prob.) | Yes | No |
| `2tf` (temp °F) | In data | In paramlist but not in datasets |
| `icon` | In data | In paramlist but not in datasets |
| `wdir` values | Numeric degrees only | Numeric degrees or `"VRB"` (variable) |
| Station metadata | No | Yes (name, ICAO code) |
| Update frequency | ~1h model runs | Real-time hourly obs |
| Cache-Control | None | `max-age=300` (5 min) |

## Potential Integration Use Cases

1. **Current conditions sensor**: Use the latest observation as "current" weather instead of/alongside the forecast value. Real measurements are more accurate for "right now."

2. **Station info attributes**: Expose `station_name` and `station_icao` as device attributes.

3. **Historical min/max**: The `station_min_max` provides actual recorded daily highs/lows for the past 3 days.

4. **Observation vs forecast comparison**: Could show how the forecast performed vs. actual readings.

## Notes

- The `wdir` field can return the string `"VRB"` (variable wind) instead of a numeric degree — any parser must handle this.
- The station coordinates in `pointlist` differ from the requested coordinates — the API finds the nearest METAR/SYNOP station.
- The `timeseries` is wrapped in an extra array `[["...", "..."]]` (array of arrays), unlike preset1 which is a flat array `["...", "..."]`.
- Response is cached server-side for 5 minutes (`Cache-Control: max-age=300`).
- CORS restricted to `https://www.meteoam.it` origin (unlike preset1 which allows `*`).
