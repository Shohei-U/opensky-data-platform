import json

import pytest
import requests

from opensky_ingest import cli
from opensky_ingest.auth import Credentials
from opensky_ingest.retry import call_with_retry


@pytest.fixture(autouse=True)
def fake_credentials(monkeypatch):
    monkeypatch.setattr(cli, "load_credentials", lambda: Credentials("id", "secret"))


def last_log(capsys) -> dict:
    lines = capsys.readouterr().out.strip().splitlines()
    assert len(lines) == 1, f"expected one log line, got {len(lines)}"
    return json.loads(lines[0])


def test_unreachable_api_ends_with_one_error_line(monkeypatch, capsys):
    # What happened on Cloud Run: the token endpoint never answered.
    def unreachable(creds):
        raise requests.ConnectTimeout("auth.opensky-network.org timed out")

    monkeypatch.setattr(cli, "fetch_token", unreachable)
    monkeypatch.setattr(
        cli, "call_with_retry", lambda call: call_with_retry(call, sleep=lambda s: None)
    )

    assert cli.main(["--dest", "unused", "--count", "1"]) == 1
    log = last_log(capsys)
    assert log["severity"] == "ERROR"
    assert log["error_type"] == "ConnectTimeout"
    assert "timed out" in log["error"]


def test_token_request_is_retried(monkeypatch):
    calls = {"n": 0}

    def flaky(creds):
        calls["n"] += 1
        if calls["n"] == 1:
            resp = requests.Response()
            resp.status_code = 503
            raise requests.HTTPError("503", response=resp)
        return "tok"

    monkeypatch.setattr(cli, "fetch_token", flaky)
    monkeypatch.setattr(
        cli, "call_with_retry", lambda call: call_with_retry(call, sleep=lambda s: None)
    )
    assert cli.get_token() == "tok"
    assert calls["n"] == 2


def test_wrong_credentials_are_not_retried(monkeypatch):
    calls = {"n": 0}

    def unauthorized(creds):
        calls["n"] += 1
        resp = requests.Response()
        resp.status_code = 401
        raise requests.HTTPError("401", response=resp)

    monkeypatch.setattr(cli, "fetch_token", unauthorized)
    with pytest.raises(requests.HTTPError):
        cli.get_token()
    assert calls["n"] == 1
