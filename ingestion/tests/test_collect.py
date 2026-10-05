from datetime import UTC, datetime

import requests

from opensky_ingest.collect import collect
from opensky_ingest.fetch import OKINAWA, FetchResult

STATE = ["8699a1", "JAL915  ", "Japan"]


class FakeClock:
    """Fake monotonic clock: sleep advances time, each fetch takes `fetch_cost` seconds."""

    def __init__(self, fetch_cost: float = 0.0):
        self.t = 0.0
        self.fetch_cost = fetch_cost
        self.sleeps: list[float] = []

    def sleep(self, s: float) -> None:
        self.sleeps.append(s)
        self.t += s

    def monotonic(self) -> float:
        return self.t


def run(fetch, count=3, interval=30.0, clock=None, token=lambda: "tok", invalidate=None):
    clock = clock or FakeClock()

    def timed_fetch(token, bbox):
        clock.t += clock.fetch_cost
        return fetch(token, bbox)

    result = collect(
        timed_fetch,
        token,
        OKINAWA,
        count,
        interval,
        sleep=clock.sleep,
        monotonic=clock.monotonic,
        now=lambda: datetime(2026, 9, 30, 3, 0, tzinfo=UTC),
        invalidate_token=invalidate or (lambda: None),
    )
    return result, clock


def ok(n_states=2, remaining=390):
    return lambda token, bbox: FetchResult(200, 1790737200, [STATE] * n_states, remaining)


def test_fetches_count_times_and_concatenates_records():
    result, _ = run(ok(n_states=2), count=3)
    assert len(result.records) == 6
    assert [log["seq"] for log in result.fetch_logs] == [0, 1, 2]
    assert all(log["row_count"] == 2 and log["error"] is None for log in result.fetch_logs)
    assert result.fetch_logs[0]["rate_limit_remaining"] == 390


def test_interval_is_measured_from_run_start():
    # Each fetch takes 2s, so the sleep between starts shrinks to 28s instead of drifting.
    _, clock = run(ok(), count=3, interval=30.0, clock=FakeClock(fetch_cost=2.0))
    assert clock.sleeps == [28.0, 28.0]


def test_single_fetch_does_not_sleep():
    _, clock = run(ok(), count=1)
    assert clock.sleeps == []


def failing_at(index: int, status: int):
    """Succeed on every call except call number `index`, which raises `status`."""
    calls = {"n": 0}

    def fetch(token, bbox):
        n = calls["n"]
        calls["n"] += 1
        if n == index:
            resp = requests.Response()
            resp.status_code = status
            raise requests.HTTPError(f"{status}", response=resp)
        return ok()(token, bbox)

    return fetch


def test_failed_fetch_is_logged_and_others_are_kept():
    result, _ = run(failing_at(1, 401), count=3)
    assert len(result.records) == 4
    failed = result.fetch_logs[1]
    assert failed["status_code"] == 401
    assert failed["row_count"] == 0
    assert failed["attempts"] == 1
    assert failed["error"].startswith("HTTPError")


def test_retried_fetch_records_attempts():
    # 1st call fails with 503, the retry succeeds.
    result, clock = run(failing_at(0, 503), count=1)
    assert result.fetch_logs[0]["attempts"] == 2
    assert result.fetch_logs[0]["error"] is None
    assert clock.sleeps == [1.0]


def test_rate_limited_run_stops_early():
    # 429 without retry-after: credits are gone, so fetches 2 and 3 are not attempted.
    result, _ = run(failing_at(1, 429), count=3)
    assert [log["seq"] for log in result.fetch_logs] == [0, 1]
    assert result.fetch_logs[1]["status_code"] == 429


def test_token_is_asked_for_before_every_fetch():
    seen = []

    def fetch(token, bbox):
        seen.append(token)
        return ok()(token, bbox)

    tokens = iter(["t1", "t2", "t3"])
    run(fetch, count=3, token=lambda: next(tokens))
    assert seen == ["t1", "t2", "t3"]


def test_unauthorized_fetch_invalidates_the_token():
    invalidated = []
    run(failing_at(1, 401), count=3, invalidate=lambda: invalidated.append(True))
    assert invalidated == [True]


def test_failed_token_refresh_is_logged_and_the_run_continues():
    calls = {"n": 0}

    def token():
        calls["n"] += 1
        if calls["n"] == 2:
            raise requests.ConnectionError("auth down")
        return "tok"

    result, _ = run(ok(n_states=1), count=3, token=token)
    assert len(result.records) == 2
    assert result.fetch_logs[1]["error"].startswith("token: ConnectionError")
    assert result.fetch_logs[1]["attempts"] == 0
