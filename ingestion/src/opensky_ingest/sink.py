"""Write output files to a local directory or a GCS bucket, chosen by the destination string.

    "data"                     -> data/<path>
    "gs://bucket"              -> gs://bucket/<path>
    "gs://bucket/some/prefix"  -> gs://bucket/some/prefix/<path>

Writing the same path twice overwrites it (GCS objects are replaced whole; nothing appends).
"""

from pathlib import Path
from typing import Any, Protocol


class Sink(Protocol):
    def write(self, path: str, data: bytes, content_type: str) -> str:
        """Write `data` to `path` (relative) and return the full location written."""
        ...


class LocalSink:
    def __init__(self, root: Path):
        self.root = root

    def write(self, path: str, data: bytes, content_type: str) -> str:
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return str(target)


class GCSSink:
    def __init__(self, bucket: str, prefix: str = "", client: Any = None):
        if client is None:
            # Imported lazily so local runs and tests don't need GCP credentials.
            from google.cloud import storage

            client = storage.Client()
        self.bucket = client.bucket(bucket)
        self.prefix = prefix.strip("/")

    def write(self, path: str, data: bytes, content_type: str) -> str:
        name = f"{self.prefix}/{path}" if self.prefix else path
        self.bucket.blob(name).upload_from_string(data, content_type=content_type)
        return f"gs://{self.bucket.name}/{name}"


def make_sink(dest: str, client: Any = None) -> Sink:
    if dest.startswith("gs://"):
        bucket, _, prefix = dest.removeprefix("gs://").partition("/")
        if not bucket:
            raise ValueError(f"bucket name missing in {dest!r}")
        return GCSSink(bucket, prefix, client)
    return LocalSink(Path(dest))
