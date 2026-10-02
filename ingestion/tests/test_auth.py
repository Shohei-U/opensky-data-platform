import json

import pytest

from opensky_ingest.auth import load_credentials


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for key in ("OPENSKY_CLIENT_ID", "OPENSKY_CLIENT_SECRET", "OPENSKY_CREDENTIALS_PATH"):
        monkeypatch.delenv(key, raising=False)


def test_reads_mounted_secret_from_env_path(tmp_path, monkeypatch):
    # Cloud Run mounts the secret as a file and points OPENSKY_CREDENTIALS_PATH at it.
    secret = tmp_path / "credentials.json"
    secret.write_text(json.dumps({"clientId": "id-1", "clientSecret": "s-1"}))
    monkeypatch.setenv("OPENSKY_CREDENTIALS_PATH", str(secret))
    creds = load_credentials()
    assert (creds.client_id, creds.client_secret) == ("id-1", "s-1")


def test_env_vars_take_precedence(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENSKY_CLIENT_ID", "env-id")
    monkeypatch.setenv("OPENSKY_CLIENT_SECRET", "env-secret")
    monkeypatch.setenv("OPENSKY_CREDENTIALS_PATH", str(tmp_path / "missing.json"))
    assert load_credentials().client_id == "env-id"


def test_missing_file_explains_what_to_set(tmp_path):
    with pytest.raises(FileNotFoundError, match="OPENSKY_CLIENT_ID"):
        load_credentials(tmp_path / "missing.json")
