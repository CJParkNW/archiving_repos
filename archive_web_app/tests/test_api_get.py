"""
Tests for _api_get() in transform_data.py.

Covers:
  - Immediate success (no retry)
  - No retry on client errors (4xx other than 429)
  - Retry on HTTP 429 and 5xx, then eventual success
  - Correct backoff schedule across multiple retries
  - Retry on network-level Timeout and ConnectionError
  - Re-raise after all retries exhausted (network errors)
  - Return of last bad response after all retries exhausted (HTTP errors)
  - Correct forwarding of headers and params

All tests patch time.sleep to avoid real delays and to assert backoff values.
"""
from unittest.mock import MagicMock, call, patch
import pytest
import requests

from transform_data import _api_get, _MAX_RETRIES, _RETRY_BACKOFF

TEST_URL = "https://api.github.com/test"
HEADERS = {"Authorization": "token fake"}


def _resp(status_code: int) -> MagicMock:
    """Return a mock requests.Response with the given status code."""
    r = MagicMock(spec=requests.Response)
    r.status_code = status_code
    return r


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

class TestApiGetSuccess:
    def test_returns_response_on_200(self):
        ok = _resp(200)
        with patch("transform_data.requests.get", return_value=ok) as mock_get, \
             patch("transform_data.time.sleep") as mock_sleep:
            result = _api_get(TEST_URL, HEADERS)
        assert result.status_code == 200
        mock_get.assert_called_once()
        mock_sleep.assert_not_called()

    def test_passes_headers_to_requests(self):
        with patch("transform_data.requests.get", return_value=_resp(200)) as mock_get, \
             patch("transform_data.time.sleep"):
            _api_get(TEST_URL, HEADERS)
        _, kwargs = mock_get.call_args
        assert kwargs["headers"] == HEADERS

    def test_passes_params_to_requests(self):
        params = {"per_page": 10, "state": "open"}
        with patch("transform_data.requests.get", return_value=_resp(200)) as mock_get, \
             patch("transform_data.time.sleep"):
            _api_get(TEST_URL, HEADERS, params=params)
        _, kwargs = mock_get.call_args
        assert kwargs["params"] == params

    def test_params_defaults_to_none(self):
        with patch("transform_data.requests.get", return_value=_resp(200)) as mock_get, \
             patch("transform_data.time.sleep"):
            _api_get(TEST_URL, HEADERS)
        _, kwargs = mock_get.call_args
        assert kwargs["params"] is None


# ---------------------------------------------------------------------------
# No retry on client errors (4xx except 429)
# ---------------------------------------------------------------------------

class TestApiGetNoRetryOnClientError:
    @pytest.mark.parametrize("status_code", [400, 401, 403, 404, 422])
    def test_returns_immediately_without_retry(self, status_code):
        bad = _resp(status_code)
        with patch("transform_data.requests.get", return_value=bad) as mock_get, \
             patch("transform_data.time.sleep") as mock_sleep:
            result = _api_get(TEST_URL, HEADERS)
        assert result.status_code == status_code
        mock_get.assert_called_once()
        mock_sleep.assert_not_called()


# ---------------------------------------------------------------------------
# HTTP retry behavior (429 and 5xx)
# ---------------------------------------------------------------------------

class TestApiGetHttpRetries:
    def test_retries_on_429_then_succeeds(self):
        with patch("transform_data.requests.get",
                   side_effect=[_resp(429), _resp(200)]) as mock_get, \
             patch("transform_data.time.sleep") as mock_sleep:
            result = _api_get(TEST_URL, HEADERS)
        assert result.status_code == 200
        assert mock_get.call_count == 2
        mock_sleep.assert_called_once_with(_RETRY_BACKOFF[0])

    def test_retries_on_500_then_succeeds(self):
        with patch("transform_data.requests.get",
                   side_effect=[_resp(500), _resp(200)]) as mock_get, \
             patch("transform_data.time.sleep") as mock_sleep:
            result = _api_get(TEST_URL, HEADERS)
        assert result.status_code == 200
        assert mock_get.call_count == 2
        mock_sleep.assert_called_once_with(_RETRY_BACKOFF[0])

    def test_retries_on_503_then_succeeds(self):
        with patch("transform_data.requests.get",
                   side_effect=[_resp(503), _resp(200)]) as mock_get, \
             patch("transform_data.time.sleep") as mock_sleep:
            result = _api_get(TEST_URL, HEADERS)
        assert result.status_code == 200
        assert mock_get.call_count == 2
        mock_sleep.assert_called_once_with(_RETRY_BACKOFF[0])

    def test_uses_correct_backoff_across_multiple_retries(self):
        # Three 429s then success — sleep should use each backoff value in order.
        with patch("transform_data.requests.get",
                   side_effect=[_resp(429), _resp(429), _resp(429), _resp(200)]),\
             patch("transform_data.time.sleep") as mock_sleep:
            result = _api_get(TEST_URL, HEADERS)
        assert result.status_code == 200
        assert mock_sleep.call_args_list == [
            call(_RETRY_BACKOFF[0]),
            call(_RETRY_BACKOFF[1]),
            call(_RETRY_BACKOFF[2]),
        ]

    def test_returns_last_bad_response_after_all_retries_exhausted(self):
        # Persistent 429: all _MAX_RETRIES + 1 attempts fail.
        responses = [_resp(429)] * (_MAX_RETRIES + 1)
        with patch("transform_data.requests.get", side_effect=responses) as mock_get, \
             patch("transform_data.time.sleep") as mock_sleep:
            result = _api_get(TEST_URL, HEADERS)
        assert result.status_code == 429
        assert mock_get.call_count == _MAX_RETRIES + 1
        assert mock_sleep.call_count == _MAX_RETRIES


# ---------------------------------------------------------------------------
# Network-level retry behavior (Timeout, ConnectionError)
# ---------------------------------------------------------------------------

class TestApiGetNetworkRetries:
    def test_retries_on_timeout_then_succeeds(self):
        with patch("transform_data.requests.get",
                   side_effect=[requests.exceptions.Timeout, _resp(200)]) as mock_get, \
             patch("transform_data.time.sleep") as mock_sleep:
            result = _api_get(TEST_URL, HEADERS)
        assert result.status_code == 200
        assert mock_get.call_count == 2
        mock_sleep.assert_called_once_with(_RETRY_BACKOFF[0])

    def test_retries_on_connection_error_then_succeeds(self):
        with patch("transform_data.requests.get",
                   side_effect=[requests.exceptions.ConnectionError, _resp(200)]) \
             as mock_get, \
             patch("transform_data.time.sleep") as mock_sleep:
            result = _api_get(TEST_URL, HEADERS)
        assert result.status_code == 200
        assert mock_get.call_count == 2
        mock_sleep.assert_called_once_with(_RETRY_BACKOFF[0])

    def test_raises_timeout_after_all_retries_exhausted(self):
        with patch("transform_data.requests.get",
                   side_effect=requests.exceptions.Timeout), \
             patch("transform_data.time.sleep"):
            with pytest.raises(requests.exceptions.Timeout):
                _api_get(TEST_URL, HEADERS)

    def test_raises_connection_error_after_all_retries_exhausted(self):
        with patch("transform_data.requests.get",
                   side_effect=requests.exceptions.ConnectionError), \
             patch("transform_data.time.sleep"):
            with pytest.raises(requests.exceptions.ConnectionError):
                _api_get(TEST_URL, HEADERS)

    def test_correct_retry_count_on_persistent_network_error(self):
        with patch("transform_data.requests.get",
                   side_effect=requests.exceptions.Timeout) as mock_get, \
             patch("transform_data.time.sleep") as mock_sleep:
            with pytest.raises(requests.exceptions.Timeout):
                _api_get(TEST_URL, HEADERS)
        assert mock_get.call_count == _MAX_RETRIES + 1
        assert mock_sleep.call_count == _MAX_RETRIES
