"""Poll the Okinawa bbox for most of an hour and write one raw file + one meta file.

    raw/dt=YYYY-MM-DD/hh=HH/<slot>.jsonl.gz   state vectors from every fetch in the run
    meta/dt=YYYY-MM-DD/hh=HH/<slot>.jsonl     one line per fetch (status, rows, credits, ...)

<slot> is the run start floored to --slot-minutes, so re-running the same slot overwrites
the same objects instead of adding duplicates.

One run per hour (108 fetches x 30s, ~54 minutes) keeps GCS writes at 2 per hour, inside
the free tier of 5,000 Class A operations a month (ADR 0006).

Usage (from repo root):
    uv run --project ingestion python -m opensky_ingest.cli [--dest data | gs://bucket]
        [--count 108] [--interval 30] [--slot-minutes 60]
"""

import argparse
import gzip
import json
import os
import sys
from datetime import UTC, datetime

from opensky_ingest.auth import TokenCache, fetch_token, load_credentials
from opensky_ingest.collect import collect
from opensky_ingest.fetch import OKINAWA, fetch_states
from opensky_ingest.retry import call_with_retry
from opensky_ingest.sink import make_sink


def slot_start(ts: datetime, minutes: int) -> datetime:
    return ts.replace(minute=ts.minute - ts.minute % minutes, second=0, microsecond=0)


def object_path(layer: str, slot: datetime, ext: str) -> str:
    return f"{layer}/dt={slot:%Y-%m-%d}/hh={slot:%H}/{slot:%Y%m%dT%H%MZ}.{ext}"


def to_jsonl(rows: list[dict]) -> bytes:
    return "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows).encode()


def log_line(entry: dict) -> None:
    # One JSON line per run: Cloud Logging and the Actions log keep it as a single entry.
    print(json.dumps(entry, ensure_ascii=False), flush=True)


def get_token() -> str:
    creds = load_credentials()
    out = call_with_retry(lambda: fetch_token(creds))
    if out.result is None:
        raise out.error  # type: ignore[misc]
    return out.result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dest",
        default=os.environ.get("OPENSKY_DEST", "data"),
        help="local directory or gs://bucket[/prefix] (env: OPENSKY_DEST)",
    )
    parser.add_argument("--count", type=int, default=108, help="fetches per run")
    parser.add_argument("--interval", type=float, default=30.0, help="seconds between fetches")
    parser.add_argument("--slot-minutes", type=int, default=60, help="run schedule granularity")
    args = parser.parse_args(argv)
    if args.count < 1 or args.interval < 0 or not 1 <= args.slot_minutes <= 60:
        parser.error("need --count >= 1, --interval >= 0, 1 <= --slot-minutes <= 60")

    try:
        run(args)
    except Exception as e:  # noqa: BLE001 - top-level handler: any failure becomes one log line
        # Anything that stops the run: report it as one ERROR line instead of a traceback.
        log_line(
            {
                "severity": "ERROR",
                "message": f"run failed: {type(e).__name__}",
                "error_type": type(e).__name__,
                "error": str(e)[:500],
            }
        )
        return 1
    return 0


def run(args: argparse.Namespace) -> None:
    sink = make_sink(args.dest)
    run_started = datetime.now(UTC)
    slot = slot_start(run_started, args.slot_minutes)

    token = TokenCache(get_token)
    token()  # fail the run up front if OpenSky can't be reached at all
    result = collect(
        fetch_states, token, OKINAWA, args.count, args.interval, invalidate_token=token.invalidate
    )

    raw_uri = sink.write(
        object_path("raw", slot, "jsonl.gz"),
        gzip.compress(to_jsonl(result.records)),
        "application/gzip",
    )
    run = {
        "slot": slot.isoformat(timespec="minutes"),
        "run_started_at": run_started.isoformat(timespec="seconds"),
        "bbox": OKINAWA.__dict__,
        "bbox_area_sq_deg": OKINAWA.area(),
        "output": raw_uri,
    }
    meta_uri = sink.write(
        object_path("meta", slot, "jsonl"),
        to_jsonl([run | log for log in result.fetch_logs]),
        "application/x-ndjson",
    )

    failed = sum(1 for log in result.fetch_logs if log["error"])
    summary = (
        {
            "severity": "WARNING" if failed else "INFO",
            "message": f"fetched {len(result.records)} rows in {len(result.fetch_logs)} fetches",
        }
        | run
        | {
            "meta": meta_uri,
            "fetches": len(result.fetch_logs),
            "failed": failed,
            "row_count": len(result.records),
            "rate_limit_remaining": result.fetch_logs[-1]["rate_limit_remaining"],
        }
    )
    log_line(summary)


if __name__ == "__main__":
    sys.exit(main())
