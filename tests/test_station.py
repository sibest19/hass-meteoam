"""Observation tests using a trimmed response captured from MeteoAM."""

import json
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from custom_components.meteoam.coordinator import CannotConnectError, MeteoAMStationData
from tests.test_coordinator import _mock_response, _mock_session_get


@pytest.fixture
def observation():
    data = MeteoAMStationData(MagicMock(), {})
    data._coordinates = {"lat": "41.9", "lon": "12.5"}
    data._session = MagicMock()
    return data


@pytest.fixture
def payload():
    return json.loads((Path(__file__).parent / "fixtures/stations.json").read_text())


@pytest.fixture(autouse=True)
def report_time():
    with patch(
        "custom_components.meteoam.coordinator.dt_util.utcnow",
        return_value=datetime(2026, 11, 5, 18, tzinfo=UTC),
    ):
        yield


async def test_nearest_report_and_endpoint(observation, payload):
    observation._session.get = _mock_session_get(_mock_response(json_data=payload))
    await observation.fetch_data()
    assert observation.current_weather_data["2t"] == 16
    assert observation.station_attributes == {
        "station_name": "Roma - Urbe",
        "station_icao": "LIRU",
        "station_distance_km": 5.8,
        "observed_at": "2026-11-05T16:00:00+00:00",
    }
    assert observation._session.get.call_args.args[0].endswith(
        "GetStationRadius/41.9/12.5"
    )


@pytest.mark.parametrize("unusable", ["stale", "missing", "future", "empty"])
def test_skip_unusable_nearest_station(observation, payload, unusable):
    if unusable == "missing":
        payload["datasets"]["0"]["0"] = {"0": "-", "1": None}
    else:
        payload["timeseries"][0] = {
            "stale": ["2026-11-04T16:00:00Z"],
            "future": ["2026-11-06T16:00:00Z"],
            "empty": [],
        }[unusable]
    observation._parse_data(payload)
    assert observation.station_attributes["station_icao"] == "LIRA"


def test_distance_selection_does_not_assume_api_order(observation, payload):
    observation._coordinates = {"lat": "41.808", "lon": "12.584"}
    observation._parse_data(payload)
    assert observation.station_attributes["station_icao"] == "LIRA"


@pytest.mark.parametrize("value", [None, "-", "VRB", "nan", "inf"])
def test_missing_numeric_values_are_unknown(observation, payload, value):
    for index in ("1", "2", "3", "6"):
        payload["datasets"]["0"][index]["0"] = value
    observation._parse_data(payload)
    assert observation.current_weather_data["2t"] == 16
    for param in ("r", "pmsl", "wdir", "wkmh"):
        assert observation.current_weather_data[param] is None


@pytest.mark.parametrize("payload", [{}, [], {"pointlist": None}, {"pointlist": []}])
async def test_invalid_or_empty_response_is_controlled(observation, payload):
    observation._session.get = _mock_session_get(_mock_response(json_data=payload))
    with pytest.raises(CannotConnectError):
        await observation.fetch_data()


def test_no_recent_reports_does_not_replace_last_good_data(observation, payload):
    observation._parse_data(payload)
    previous = observation.current_weather_data
    payload["timeseries"] = [["2026-11-04T16:00:00Z"]] * 2
    with pytest.raises(CannotConnectError, match="last 3 hours"):
        observation._parse_data(payload)
    assert observation.current_weather_data is previous


def test_zero_temperature_is_usable(observation, payload):
    payload["datasets"]["0"]["0"]["0"] = 0
    observation._parse_data(payload)
    assert observation.current_weather_data["2t"] == 0
    assert observation.station_attributes["station_icao"] == "LIRU"


@pytest.mark.parametrize("field", ["datasets", "extrainfo", "timeseries"])
async def test_malformed_nested_data_is_controlled(observation, payload, field):
    payload[field] = None
    observation._session.get = _mock_session_get(_mock_response(json_data=payload))
    with pytest.raises(CannotConnectError):
        await observation.fetch_data()
