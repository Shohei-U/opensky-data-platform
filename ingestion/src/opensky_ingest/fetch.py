"""Fetch /states/all for a bounding box and convert state vectors to dicts."""

from dataclasses import dataclass
from typing import Any

import requests

STATES_URL = "https://opensky-network.org/api/states/all"

# Order defined by the OpenSky REST API. Index 17 (category) only appears with extended=1.
STATE_FIELDS = (
    "icao24",
    "callsign",
    "origin_country",
    "time_position",
    "last_contact",
    "longitude",
    "latitude",
    "baro_altitude",
    "on_ground",
    "velocity",
    "true_track",
    "vertical_rate",
    "sensors",
    "geo_altitude",
    "squawk",
    "spi",
    "position_source",
    "category",
)


@dataclass(frozen=True)
class BBox:
    lamin: float
    lomin: float
    lamax: float
    lomax: float

    def area(self) -> float:
        return (self.lamax - self.lamin) * (self.lomax - self.lomin)


OKINAWA = BBox(lamin=24, lomin=123, lamax=28, lomax=129)


@dataclass(frozen=True)
class FetchResult:
    status_code: int
    api_time: int | None
    states: list[list[Any]]
    rate_limit_remaining: int | None


def fetch_states(token: str, bbox: BBox, timeout: float = 15.0) -> FetchResult:
    resp = requests.get(
        STATES_URL,
        params={
            "lamin": bbox.lamin,
            "lomin": bbox.lomin,
            "lamax": bbox.lamax,
            "lomax": bbox.lomax,
            "extended": 1,
        },
        headers={"Authorization": f"Bearer {token}"},
        timeout=timeout,
    )
    remaining = resp.headers.get("X-Rate-Limit-Remaining")
    resp.raise_for_status()
    body = resp.json()
    return FetchResult(
        status_code=resp.status_code,
        api_time=body.get("time"),
        # "states" is null when no aircraft are in the bbox.
        states=body.get("states") or [],
        rate_limit_remaining=int(remaining) if remaining is not None else None,
    )


def state_to_record(state: list[Any], api_time: int | None, fetched_at: str) -> dict[str, Any]:
    record = {name: (state[i] if i < len(state) else None) for i, name in enumerate(STATE_FIELDS)}
    if isinstance(record["callsign"], str):
        record["callsign"] = record["callsign"].strip() or None
    record["api_time"] = api_time
    record["fetched_at"] = fetched_at
    return record
