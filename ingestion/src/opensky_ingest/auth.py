"""OpenSky OAuth2 (client credentials) token handling."""

import json
import os
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import requests

TOKEN_URL = (
    "https://auth.opensky-network.org/auth/realms/opensky-network/protocol/openid-connect/token"
)
DEFAULT_CREDENTIALS_PATH = Path.home() / ".config" / "opensky" / "credentials.json"


@dataclass(frozen=True)
class Credentials:
    client_id: str
    client_secret: str


def load_credentials(path: Path | None = None) -> Credentials:
    """Env vars take precedence; otherwise read credentials.json.

    The file is `path`, else $OPENSKY_CREDENTIALS_PATH (Cloud Run mounts the secret there),
    else ~/.config/opensky/credentials.json.
    """
    client_id = os.environ.get("OPENSKY_CLIENT_ID")
    client_secret = os.environ.get("OPENSKY_CLIENT_SECRET")
    if client_id and client_secret:
        return Credentials(client_id, client_secret)

    if path is None:
        env_path = os.environ.get("OPENSKY_CREDENTIALS_PATH")
        path = Path(env_path) if env_path else DEFAULT_CREDENTIALS_PATH
    if not path.exists():
        raise FileNotFoundError(
            f"Set OPENSKY_CLIENT_ID / OPENSKY_CLIENT_SECRET or place credentials at {path}"
        )
    data = json.loads(path.read_text())
    # Accept both camelCase (OpenSky download) and snake_case keys.
    return Credentials(
        client_id=data.get("clientId") or data["client_id"],
        client_secret=data.get("clientSecret") or data["client_secret"],
    )


def fetch_token(creds: Credentials, timeout: float = 10.0) -> str:
    resp = requests.post(
        TOKEN_URL,
        data={
            "grant_type": "client_credentials",
            "client_id": creds.client_id,
            "client_secret": creds.client_secret,
        },
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


class TokenCache:
    """Reuse one access token and get a new one before it expires.

    OpenSky tokens expire after 30 minutes and a run lasts ~55 minutes, so the token is
    refreshed once it is `max_age` seconds old. `invalidate()` forces a refresh on the next
    call (used after a 401, which means the token expired early).
    """

    def __init__(
        self,
        fetch: Callable[[], str],
        max_age: float = 25 * 60,
        monotonic: Callable[[], float] = time.monotonic,
    ):
        self._fetch = fetch
        self._max_age = max_age
        self._monotonic = monotonic
        self._token: str | None = None
        self._fetched_at = 0.0

    def __call__(self) -> str:
        if self._token is None or self._monotonic() - self._fetched_at >= self._max_age:
            self._token = self._fetch()
            self._fetched_at = self._monotonic()
        return self._token

    def invalidate(self) -> None:
        self._token = None
