import requests

from opensky_ingest.fetch import OKINAWA, FetchResult
from opensky_ingest.retry import backoff_delay, classify, fetch_with_retry

OK = FetchResult(200, 1790737200, [], 390)


def http_error(status: int, headers: dict[str, str] | None = None) -> requests.HTTPError:
    resp = requests.Response()
    resp.status_code = status
    resp.headers.update(headers or {})
    return requests.HTTPError(f"{status}", response=resp)


# --- classify: the policy (本人が実装する部分の仕様) ---


def test_server_error_is_retried():
    assert classify(http_error(503), max_wait=30).action == "retry"


def test_timeout_is_retried():
    assert classify(requests.Timeout("timed out"), max_wait=30).action == "retry"


def test_client_error_gives_up():
    for status in (400, 401, 403, 404):
        assert classify(http_error(status), max_wait=30).action == "give_up"


def test_429_with_short_retry_after_waits_that_long():
    e = http_error(429, {"X-Rate-Limit-Retry-After-Seconds": "12"})
    d = classify(e, max_wait=30)
    assert d.action == "wait"
    assert d.wait_seconds == 12


def test_429_with_long_retry_after_gives_up():
    # Credits come back in an hour: waiting would blow past this 5-minute run.
    e = http_error(429, {"X-Rate-Limit-Retry-After-Seconds": "3600"})
    assert classify(e, max_wait=30).action == "give_up"


def test_429_without_header_gives_up():
    assert classify(http_error(429), max_wait=30).action == "give_up"


# --- fetch_with_retry: the loop ---


def run(errors, max_attempts=3):
    """Raise the given errors in order, then succeed."""
    queue = list(errors)
    sleeps: list[float] = []

    def fetch(token, bbox):
        if queue:
            raise queue.pop(0)
        return OK

    out = fetch_with_retry(
        fetch, "tok", OKINAWA, max_attempts=max_attempts, base_delay=1.0, sleep=sleeps.append
    )
    return out, sleeps


def test_backoff_doubles():
    assert [backoff_delay(n, 1.0) for n in (1, 2, 3)] == [1.0, 2.0, 4.0]


def test_success_after_transient_errors():
    out, sleeps = run([http_error(503), requests.Timeout()])
    assert out.result == OK
    assert out.attempts == 3
    assert sleeps == [1.0, 2.0]


def test_stops_at_max_attempts():
    out, sleeps = run([http_error(503)] * 5, max_attempts=3)
    assert out.result is None
    assert out.attempts == 3
    assert sleeps == [1.0, 2.0]


def test_gives_up_immediately_on_auth_error():
    out, sleeps = run([http_error(401)])
    assert out.result is None
    assert out.attempts == 1
    assert sleeps == []


def test_429_waits_retry_after():
    out, sleeps = run([http_error(429, {"X-Rate-Limit-Retry-After-Seconds": "5"})])
    assert out.result == OK
    assert sleeps == [5.0]
