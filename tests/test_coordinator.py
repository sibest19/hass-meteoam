"""Tests for the MeteoAM coordinator."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest
from homeassistant.util import dt as dt_util

from custom_components.meteoam.coordinator import (
    CannotConnectError,
    MeteoAMWeatherData,
)

# --- Helpers for building fake API responses ---


def _build_api_response(
    timeseries: list[str],
    paramlist: list[str] | None = None,
    datasets: dict | None = None,
    stats: list[dict] | None = None,
) -> dict:
    """Build a minimal fake API response matching the MeteoAM schema."""
    if paramlist is None:
        paramlist = ["2t", "r", "pmsl", "wdir", "wkmh", "tpp", "icon"]
    if datasets is None:
        # Default: one dataset per param, one value per timeseries entry
        datasets = {
            "0": {
                str(pidx): {str(tidx): pidx + tidx for tidx in range(len(timeseries))}
                for pidx in range(len(paramlist))
            }
        }
    if stats is None:
        stats = [
            {
                "localDate": (
                    timeseries[0] if timeseries else "2026-03-26T12:00:00+00:00"
                ),
                "maxCelsius": 20,
                "minCelsius": 10,
                "icon": "01",
            }
        ]
    return {
        "timeseries": timeseries,
        "paramlist": paramlist,
        "datasets": datasets,
        "extrainfo": {"stats": stats},
    }


def _make_weather_data(hass_mock: MagicMock) -> MeteoAMWeatherData:
    """Create a MeteoAMWeatherData with mocked hass and session."""
    config = {"latitude": "41.9", "longitude": "12.5"}
    wd = MeteoAMWeatherData(hass_mock, config)
    wd._coordinates = {"lat": "41.9", "lon": "12.5"}
    wd._session = MagicMock(spec=aiohttp.ClientSession)
    return wd


def _mock_response(status: int = 200, json_data: dict | None = None) -> AsyncMock:
    """Create a mock aiohttp response."""
    resp = AsyncMock()
    resp.status = status
    resp.json = AsyncMock(return_value=json_data)
    return resp


# --- Tests ---


@pytest.fixture
def hass_mock():
    """Return a minimal HomeAssistant mock."""
    hass = MagicMock()
    hass.config.latitude = 41.9
    hass.config.longitude = 12.5
    return hass


class TestFetchDataNetworkErrors:
    """Tests for network error handling in fetch_data."""

    async def test_aiohttp_client_error_raises_cannot_connect(self, hass_mock):
        """aiohttp.ClientError should be caught and re-raised as CannotConnectError."""
        wd = _make_weather_data(hass_mock)
        wd._session.get = AsyncMock(
            side_effect=aiohttp.ClientConnectionError("connection refused")
        )

        with pytest.raises(CannotConnectError, match="Error connecting"):
            await wd.fetch_data()

    async def test_timeout_error_raises_cannot_connect(self, hass_mock):
        """TimeoutError should be caught and re-raised as CannotConnectError."""
        wd = _make_weather_data(hass_mock)
        wd._session.get = AsyncMock(side_effect=TimeoutError("timed out"))

        with pytest.raises(CannotConnectError, match="Error connecting"):
            await wd.fetch_data()

    async def test_non_200_status_raises_cannot_connect(self, hass_mock):
        """Non-200 HTTP status should raise CannotConnectError."""
        wd = _make_weather_data(hass_mock)
        wd._session.get = AsyncMock(return_value=_mock_response(status=503))

        with pytest.raises(CannotConnectError, match="API returned status 503"):
            await wd.fetch_data()

    async def test_json_decode_error_raises_cannot_connect(self, hass_mock):
        """Invalid JSON response should be caught as CannotConnectError."""
        wd = _make_weather_data(hass_mock)
        resp = _mock_response(status=200)
        resp.json = AsyncMock(
            side_effect=aiohttp.ContentTypeError(
                MagicMock(), MagicMock(), message="not json"
            )
        )
        wd._session.get = AsyncMock(return_value=resp)

        with pytest.raises(CannotConnectError, match="Error parsing"):
            await wd.fetch_data()

    async def test_value_error_on_json_raises_cannot_connect(self, hass_mock):
        """ValueError during JSON decoding should raise CannotConnectError."""
        wd = _make_weather_data(hass_mock)
        resp = _mock_response(status=200)
        resp.json = AsyncMock(side_effect=ValueError("bad json"))
        wd._session.get = AsyncMock(return_value=resp)

        with pytest.raises(CannotConnectError, match="Error parsing"):
            await wd.fetch_data()

    async def test_empty_response_raises_cannot_connect(self, hass_mock):
        """Empty API response should raise CannotConnectError."""
        wd = _make_weather_data(hass_mock)
        wd._session.get = AsyncMock(
            return_value=_mock_response(status=200, json_data={})
        )

        with pytest.raises(CannotConnectError, match="empty response"):
            await wd.fetch_data()


class TestFetchDataParsingErrors:
    """Tests for data parsing error handling."""

    async def test_missing_extrainfo_key_raises_cannot_connect(self, hass_mock):
        """Missing 'extrainfo' key should raise CannotConnectError."""
        wd = _make_weather_data(hass_mock)
        bad_data = {"timeseries": [], "paramlist": [], "datasets": {"0": {}}}
        wd._session.get = AsyncMock(
            return_value=_mock_response(status=200, json_data=bad_data)
        )

        with pytest.raises(CannotConnectError, match="Error processing"):
            await wd.fetch_data()

    async def test_missing_datasets_key_raises_cannot_connect(self, hass_mock):
        """Missing 'datasets' key should raise CannotConnectError."""
        wd = _make_weather_data(hass_mock)
        bad_data = {
            "timeseries": ["2026-03-26T12:00:00+00:00"],
            "paramlist": ["2t"],
            "extrainfo": {"stats": []},
        }
        wd._session.get = AsyncMock(
            return_value=_mock_response(status=200, json_data=bad_data)
        )

        with pytest.raises(CannotConnectError, match="Error processing"):
            await wd.fetch_data()


class TestCurrentWeatherFallback:
    """Tests for current weather data fallback behavior."""

    async def test_current_weather_populated_from_past_entry(self, hass_mock):
        """Current weather data should come from the latest timeseries entry <= now."""
        now = dt_util.now()
        past = (now - timedelta(hours=1)).isoformat()
        future = (now + timedelta(hours=1)).isoformat()

        data = _build_api_response(timeseries=[past, future])
        wd = _make_weather_data(hass_mock)
        wd._session.get = AsyncMock(
            return_value=_mock_response(status=200, json_data=data)
        )

        await wd.fetch_data()

        assert wd.current_weather_data
        assert "2t" in wd.current_weather_data

    async def test_fallback_to_first_hourly_when_no_past_entries(self, hass_mock):
        """When all entries are in the future, fall back to first hourly."""
        now = dt_util.now()
        future1 = (now + timedelta(hours=1)).isoformat()
        future2 = (now + timedelta(hours=2)).isoformat()

        data = _build_api_response(timeseries=[future1, future2])
        wd = _make_weather_data(hass_mock)
        wd._session.get = AsyncMock(
            return_value=_mock_response(status=200, json_data=data)
        )

        await wd.fetch_data()

        # Should fall back to first hourly forecast entry
        assert wd.current_weather_data
        assert "2t" in wd.current_weather_data
        assert wd.current_weather_data == wd.hourly_forecast[0]

    async def test_current_weather_reset_between_fetches(self, hass_mock):
        """Current weather data should not persist stale data across fetches."""
        now = dt_util.now()
        past = (now - timedelta(hours=1)).isoformat()
        future = (now + timedelta(hours=1)).isoformat()

        # First fetch: has a past entry → current weather populated
        data1 = _build_api_response(timeseries=[past, future])
        wd = _make_weather_data(hass_mock)
        wd._session.get = AsyncMock(
            return_value=_mock_response(status=200, json_data=data1)
        )
        await wd.fetch_data()
        first_current = wd.current_weather_data.copy()
        assert first_current

        # Second fetch: only future entries → should fall back, not keep stale data
        future1 = (now + timedelta(hours=1)).isoformat()
        future2 = (now + timedelta(hours=2)).isoformat()
        data2 = _build_api_response(timeseries=[future1, future2])
        wd._session.get = AsyncMock(
            return_value=_mock_response(status=200, json_data=data2)
        )
        await wd.fetch_data()

        # Should be the fallback (first hourly entry), not the stale past data
        assert wd.current_weather_data == wd.hourly_forecast[0]

    async def test_hourly_forecast_populated(self, hass_mock):
        """Hourly forecast should contain entries >= now."""
        now = dt_util.now()
        past = (now - timedelta(hours=1)).isoformat()
        future1 = (now + timedelta(hours=1)).isoformat()
        future2 = (now + timedelta(hours=2)).isoformat()

        data = _build_api_response(timeseries=[past, future1, future2])
        wd = _make_weather_data(hass_mock)
        wd._session.get = AsyncMock(
            return_value=_mock_response(status=200, json_data=data)
        )

        await wd.fetch_data()

        assert len(wd.hourly_forecast) == 2
        assert len(wd.daily_forecast) == 1


class TestFetchDataPreconditions:
    """Tests for fetch_data precondition checks."""

    async def test_coordinates_not_set_raises_runtime_error(self, hass_mock):
        """fetch_data should raise RuntimeError if coordinates are not set."""
        wd = _make_weather_data(hass_mock)
        wd._coordinates = None

        with pytest.raises(RuntimeError, match="Coordinates not set"):
            await wd.fetch_data()

    async def test_session_not_set_raises_runtime_error(self, hass_mock):
        """fetch_data should raise RuntimeError if session is not initialized."""
        wd = _make_weather_data(hass_mock)
        wd._session = None

        with pytest.raises(RuntimeError, match="Session not initialized"):
            await wd.fetch_data()


class TestSetCoordinates:
    """Tests for set_coordinates change detection."""

    def test_returns_true_on_first_call(self, hass_mock):
        """set_coordinates should return True when coordinates are first set."""
        config = {"latitude": 41.9, "longitude": 12.5}
        wd = MeteoAMWeatherData(hass_mock, config)
        with patch(
            "custom_components.meteoam.coordinator.async_get_clientsession",
            return_value=MagicMock(),
        ):
            assert wd.set_coordinates() is True

    def test_returns_false_when_coordinates_unchanged(self, hass_mock):
        """set_coordinates should return False if coordinates have not changed."""
        config = {"latitude": 41.9, "longitude": 12.5}
        wd = MeteoAMWeatherData(hass_mock, config)
        with patch(
            "custom_components.meteoam.coordinator.async_get_clientsession",
            return_value=MagicMock(),
        ):
            wd.set_coordinates()
            assert wd.set_coordinates() is False

    def test_returns_true_when_coordinates_change(self, hass_mock):
        """set_coordinates should return True when coordinates change."""
        hass_mock.config.latitude = 48.85
        hass_mock.config.longitude = 2.35
        config = {"track_home": True}
        wd = MeteoAMWeatherData(hass_mock, config)
        wd._coordinates = {"lat": "41.9", "lon": "12.5"}  # stale coordinates
        with patch(
            "custom_components.meteoam.coordinator.async_get_clientsession",
            return_value=MagicMock(),
        ):
            assert wd.set_coordinates() is True

    def test_track_home_uses_hass_config(self, hass_mock):
        """set_coordinates with track_home should read from hass.config."""
        hass_mock.config.latitude = 48.85
        hass_mock.config.longitude = 2.35
        config = {"track_home": True}
        wd = MeteoAMWeatherData(hass_mock, config)
        with patch(
            "custom_components.meteoam.coordinator.async_get_clientsession",
            return_value=MagicMock(),
        ):
            wd.set_coordinates()
        assert wd._coordinates == {"lat": "48.85", "lon": "2.35"}

    def test_fixed_location_uses_config(self, hass_mock):
        """set_coordinates without track_home should read from config entry."""
        config = {"latitude": 51.5, "longitude": -0.12}
        wd = MeteoAMWeatherData(hass_mock, config)
        with patch(
            "custom_components.meteoam.coordinator.async_get_clientsession",
            return_value=MagicMock(),
        ):
            wd.set_coordinates()
        assert wd._coordinates == {"lat": "51.5", "lon": "-0.12"}


class TestDailyForecastDatetime:
    """Tests that daily forecast stores ISO strings, not datetime objects."""

    async def test_daily_forecast_datetime_is_string(self, hass_mock):
        """localDateTime in daily_forecast must be an ISO string, not a datetime."""
        now = dt_util.now()
        ts = now.isoformat()
        data = _build_api_response(timeseries=[ts])
        wd = _make_weather_data(hass_mock)
        wd._session.get = AsyncMock(
            return_value=_mock_response(status=200, json_data=data)
        )

        await wd.fetch_data()

        assert wd.daily_forecast, "Expected at least one daily forecast entry"
        for entry in wd.daily_forecast:
            assert isinstance(entry["localDateTime"], str), (
                f"Expected str, got {type(entry['localDateTime'])}"
            )
