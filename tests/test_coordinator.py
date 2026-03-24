"""Tests for the MeteoAM coordinator."""

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.util import dt as dt_util

from custom_components.meteoam.coordinator import CannotConnectError, MeteoAMWeatherData


def _make_api_response(timeseries: list[str]) -> dict:
    """Build a minimal API response with the given UTC timeseries timestamps."""
    n = len(timeseries)
    paramlist = ["2t", "r", "pmsl", "wkmh", "wdir", "icon", "tpp"]
    datasets: dict = {
        str(pidx): {str(tidx): float(tidx + pidx) for tidx in range(n)}
        for pidx in range(len(paramlist))
    }
    # Make the icon param return a valid condition code string
    datasets[str(paramlist.index("icon"))] = {str(tidx): "01" for tidx in range(n)}
    return {
        "timeseries": timeseries,
        "paramlist": paramlist,
        "datasets": {"0": datasets},
        "extrainfo": {
            "stats": [
                {
                    "localDate": "2024-01-01T00:00:00+00:00",
                    "maxCelsius": 20.0,
                    "minCelsius": 10.0,
                    "icon": "01",
                }
            ]
        },
    }


@pytest.fixture
def weather_data(hass):
    """Create a MeteoAMWeatherData instance with mocked coordinates and session."""
    config = {"latitude": 41.9, "longitude": 12.5}
    data = MeteoAMWeatherData(hass, config)
    data._coordinates = {"lat": "41.9", "lon": "12.5"}
    data._session = MagicMock()
    return data


async def test_current_weather_set_from_past_entry(weather_data):
    """Current weather data is set from the most recent past timeseries entry."""
    now = dt_util.utcnow()
    past1 = (now - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    past2 = (now - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    future = (now + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")

    api_response = _make_api_response([past1, past2, future])

    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.json = AsyncMock(return_value=api_response)
    weather_data._session.get = AsyncMock(return_value=mock_resp)

    result = await weather_data.fetch_data()

    # Current conditions must be populated (from the most recent past entry)
    assert result.current_weather_data
    assert "2t" in result.current_weather_data
    # Hourly forecast should contain only the future entry
    assert len(result.hourly_forecast) == 1


async def test_current_weather_falls_back_to_first_future_entry(weather_data):
    """When all timeseries entries are future, fall back to the nearest one."""
    now = dt_util.utcnow()
    future1 = (now + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    future2 = (now + timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")

    api_response = _make_api_response([future1, future2])

    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.json = AsyncMock(return_value=api_response)
    weather_data._session.get = AsyncMock(return_value=mock_resp)

    result = await weather_data.fetch_data()

    # Current conditions must still be populated even with all-future timeseries
    assert result.current_weather_data, "current_weather_data should not be empty"
    assert "2t" in result.current_weather_data
    # The fallback should be the first (nearest) future entry
    assert result.current_weather_data == result.hourly_forecast[0]
    # All future entries end up in the hourly forecast
    assert len(result.hourly_forecast) == 2


async def test_current_weather_near_future_fallback(weather_data):
    """Near-future entries are used as fallback for current conditions."""
    now = dt_util.utcnow()
    # Use a timestamp that is clearly in the future but very close to now
    near_future = (now + timedelta(seconds=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    further_future = (now + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")

    api_response = _make_api_response([near_future, further_future])

    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.json = AsyncMock(return_value=api_response)
    weather_data._session.get = AsyncMock(return_value=mock_resp)

    result = await weather_data.fetch_data()

    # Both entries are in the future, so fallback is used for current conditions
    assert result.current_weather_data
    assert "2t" in result.current_weather_data
    # Both future entries appear in hourly forecast
    assert len(result.hourly_forecast) == 2
    # Fallback selects the first (nearest) entry
    assert result.current_weather_data == result.hourly_forecast[0]


async def test_empty_timeseries_leaves_current_weather_unchanged(weather_data):
    """Empty timeseries does not overwrite existing current_weather_data."""
    initial_data = {"localDateTime": "2024-01-01T10:00:00", "2t": 22.0}
    weather_data.current_weather_data = initial_data

    api_response = _make_api_response([])

    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.json = AsyncMock(return_value=api_response)
    weather_data._session.get = AsyncMock(return_value=mock_resp)

    result = await weather_data.fetch_data()

    # Old data is preserved when no new data is available
    assert result.current_weather_data == initial_data


async def test_http_error_raises_cannot_connect(weather_data):
    """HTTP non-200 response raises CannotConnectError."""
    mock_resp = AsyncMock()
    mock_resp.status = 500
    weather_data._session.get = AsyncMock(return_value=mock_resp)

    with pytest.raises(CannotConnectError):
        await weather_data.fetch_data()


async def test_empty_api_response_raises_cannot_connect(weather_data):
    """Empty API response raises CannotConnectError."""
    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.json = AsyncMock(return_value=None)
    weather_data._session.get = AsyncMock(return_value=mock_resp)

    with pytest.raises(CannotConnectError):
        await weather_data.fetch_data()
