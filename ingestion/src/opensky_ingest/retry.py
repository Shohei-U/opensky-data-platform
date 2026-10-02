"""Retry a single fetch: exponential backoff for transient errors, honor 429 retry-after."""

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

import requests

from opensky_ingest.fetch import BBox, FetchResult

Action = Literal["retry", "wait", "give_up"]


@dataclass(frozen=True)
class Decision:
    action: Action
    # Seconds to wait before the next attempt. Only used when action == "wait".
    wait_seconds: float = 0.0


def classify(error: requests.RequestException, max_wait: float) -> Decision:
    """Decide what to do with a failed fetch.

    - "retry":   transient error; the caller waits with exponential backoff and tries again
    - "wait":    wait exactly `wait_seconds`, then try again
    - "give_up": trying again will not help (or would take too long)

    Useful facts:
    - `error.response` is None for timeouts / connection errors, otherwise has `.status_code`
      and `.headers`
    - On 429, OpenSky sends `X-Rate-Limit-Retry-After-Seconds` (seconds until credits return)
    - `max_wait` is the longest pause that still fits in this run (a run lasts ~5 minutes)
    """
    resp = error.response
    if resp is None:
        # Timeout / connection reset: nothing reached us, so trying again may work.
        return Decision("retry")
    if resp.status_code >= 500:
        return Decision("retry")
    if resp.status_code == 429:
        after = resp.headers.get("X-Rate-Limit-Retry-After-Seconds")
        if after is not None and float(after) <= max_wait:
            return Decision("wait", float(after))
        # Credits are gone for longer than this run lasts (or we can't tell): stop spending.
        return Decision("give_up")
    # 4xx: the request itself is wrong (bad params, expired token). Same answer every time.
    return Decision("give_up")


def backoff_delay(attempt: int, base: float) -> float:
    """1st retry waits `base`, then 2x, 4x, ..."""
    return base * 2 ** (attempt - 1)


@dataclass(frozen=True)
class RetryOutcome:
    result: FetchResult | None
    attempts: int
    error: requests.RequestException | None


def fetch_with_retry(
    fetch: Callable[[str, BBox], FetchResult],
    token: str,
    bbox: BBox,
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_wait: float = 30.0,
    sleep: Callable[[float], None] = time.sleep,
) -> RetryOutcome:
    for attempt in range(1, max_attempts + 1):
        try:
            return RetryOutcome(fetch(token, bbox), attempt, None)
        except requests.RequestException as e:
            if attempt == max_attempts:
                return RetryOutcome(None, attempt, e)
            decision = classify(e, max_wait)
            if decision.action == "give_up":
                return RetryOutcome(None, attempt, e)
            if decision.action == "wait":
                sleep(decision.wait_seconds)
            else:
                sleep(backoff_delay(attempt, base_delay))
    raise AssertionError("unreachable")
