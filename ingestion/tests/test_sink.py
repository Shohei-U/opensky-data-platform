from datetime import UTC, datetime

import pytest

from opensky_ingest.cli import object_path, slot_start
from opensky_ingest.sink import GCSSink, LocalSink, make_sink


class FakeBlob:
    def __init__(self, store, name):
        self.store, self.name = store, name

    def upload_from_string(self, data, content_type):
        self.store[self.name] = (data, content_type)


class FakeBucket:
    def __init__(self, name):
        self.name = name
        self.objects: dict[str, tuple[bytes, str]] = {}

    def blob(self, name):
        return FakeBlob(self.objects, name)


class FakeClient:
    def __init__(self):
        self.buckets: dict[str, FakeBucket] = {}

    def bucket(self, name):
        return self.buckets.setdefault(name, FakeBucket(name))


def test_local_destination(tmp_path):
    sink = make_sink(str(tmp_path))
    assert isinstance(sink, LocalSink)
    uri = sink.write("raw/dt=2026-10-02/a.jsonl.gz", b"x", "application/gzip")
    assert (tmp_path / "raw/dt=2026-10-02/a.jsonl.gz").read_bytes() == b"x"
    assert uri.endswith("raw/dt=2026-10-02/a.jsonl.gz")


def test_gcs_destination_with_prefix():
    client = FakeClient()
    sink = make_sink("gs://opensky-raw/dev", client=client)
    assert isinstance(sink, GCSSink)
    uri = sink.write("raw/a.jsonl.gz", b"x", "application/gzip")
    assert uri == "gs://opensky-raw/dev/raw/a.jsonl.gz"
    assert client.buckets["opensky-raw"].objects["dev/raw/a.jsonl.gz"] == (b"x", "application/gzip")


def test_gcs_destination_without_prefix():
    client = FakeClient()
    uri = make_sink("gs://opensky-raw", client=client).write("raw/a", b"x", "text/plain")
    assert uri == "gs://opensky-raw/raw/a"


def test_same_path_overwrites():
    client = FakeClient()
    sink = make_sink("gs://b", client=client)
    sink.write("raw/a", b"first", "text/plain")
    sink.write("raw/a", b"second", "text/plain")
    assert client.buckets["b"].objects == {"raw/a": (b"second", "text/plain")}


def test_missing_bucket_name_is_rejected():
    with pytest.raises(ValueError):
        make_sink("gs://", client=FakeClient())


def test_runs_in_the_same_slot_share_an_object_name():
    a = slot_start(datetime(2026, 10, 2, 3, 5, 12, tzinfo=UTC), 5)
    b = slot_start(datetime(2026, 10, 2, 3, 9, 59, tzinfo=UTC), 5)
    c = slot_start(datetime(2026, 10, 2, 3, 10, 0, tzinfo=UTC), 5)
    assert a == b != c
    assert object_path("raw", a, "jsonl.gz") == "raw/dt=2026-10-02/hh=03/20261002T0305Z.jsonl.gz"
