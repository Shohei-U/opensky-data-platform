"""Poll /states/all several times per run and gather records plus per-fetch metadata."""

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import requests

from opensky_ingest.fetch import BBox, FetchResult, state_to_record
from opensky_ingest.retry import fetch_with_retry

FetchFn = Callable[[str, BBox], FetchResult]


@dataclass
class CollectResult:
    records: list[dict[str, Any]] = field(default_factory=list)
    fetch_logs: list[dict[str, Any]] = field(default_factory=list)


def collect(
    fetch: FetchFn,
    token: Callable[[], str],
    bbox: BBox,
    count: int,
    interval: float,
    sleep: Callable[[float], None] = time.sleep,
    monotonic: Callable[[], float] = time.monotonic,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
    invalidate_token: Callable[[], None] = lambda: None,
) -> CollectResult:
    """Fetch `count` times, starting each fetch `interval` seconds after the previous start.

    Each fetch is retried (see retry.py). A fetch that still fails is logged and skipped so
    the other snapshots in the run are kept. A 429 that retry gave up on means credits are
    gone, so the rest of the run is skipped instead of hitting the API again.

    `token` is called before every fetch so a long run can swap in a fresh token. A 401
    means the token expired; `invalidate_token` makes the next call fetch a new one.
    """
    result = CollectResult()
    start = monotonic()
    for i in range(count):
        if i > 0:
            sleep(max(0.0, start + i * interval - monotonic()))
        fetched_at = now().isoformat(timespec="seconds")
        log: dict[str, Any] = {"seq": i, "fetched_at": fetched_at}
        try:
            tok = token()
        except requests.RequestException as e:
            # Token refresh failed: log this fetch as failed and try again next interval.
            log |= {
                "attempts": 0,
                "status_code": None,
                "api_time": None,
                "row_count": 0,
                "rate_limit_remaining": None,
                "error": f"token: {type(e).__name__}: {e}",
            }
            result.fetch_logs.append(log)
            continue
        out = fetch_with_retry(fetch, tok, bbox, sleep=sleep)
        log["attempts"] = out.attempts
        if out.result is None:
            resp = getattr(out.error, "response", None)
            status = resp.status_code if resp is not None else None
            if status == 401:
                invalidate_token()
            log |= {
                "status_code": status,
                "api_time": None,
                "row_count": 0,
                "rate_limit_remaining": None,
                "error": f"{type(out.error).__name__}: {out.error}",
            }
            result.fetch_logs.append(log)
            if status == 429:
                break
            continue
        r = out.result
        rows = [state_to_record(s, r.api_time, fetched_at) for s in r.states]
        result.records.extend(rows)
        log |= {
            "status_code": r.status_code,
            "api_time": r.api_time,
            "row_count": len(rows),
            "rate_limit_remaining": r.rate_limit_remaining,
            "error": None,
        }
        result.fetch_logs.append(log)
    return result
