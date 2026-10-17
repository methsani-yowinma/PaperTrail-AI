"""Private file storage for uploaded PDFs.

* ``LocalFileStorage`` — files under ``LOCAL_STORAGE_DIR`` (development only).
* ``SupabaseStorage`` — private Supabase Storage bucket via its REST API, authenticated with
  the service-role key, which never leaves the backend.

Object keys are always ``<owner_id>/<document_id>.pdf`` and both parts are validated as
UUIDs, so user input can never form a path.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Protocol

import httpx

from app.core.errors import StorageError


def object_key(owner_id: str, document_id: str) -> str:
    # Raises ValueError for anything that is not a UUID.
    return f"{uuid.UUID(owner_id)}/{uuid.UUID(document_id)}.pdf"


class FileStorage(Protocol):
    backend: str

    def save(self, key: str, data: bytes) -> None: ...

    def load(self, key: str) -> bytes: ...

    def delete(self, key: str) -> None: ...


class LocalFileStorage:
    backend = "local"

    def __init__(self, root: Path):
        self._root = root.resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        path = (self._root / key).resolve()
        if self._root not in path.parents:
            raise StorageError("Invalid storage key.")
        return path

    def save(self, key: str, data: bytes) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_bytes(data)
        tmp.replace(path)

    def load(self, key: str) -> bytes:
        path = self._path(key)
        if not path.exists():
            raise StorageError("The stored file could not be found.", code="file_missing")
        return path.read_bytes()

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)


class SupabaseStorage:
    backend = "supabase"

    def __init__(self, supabase_url: str, service_role_key: str, bucket: str, *, client: httpx.Client | None = None):
        self._base = f"{supabase_url.rstrip('/')}/storage/v1"
        self._bucket = bucket
        self._headers = {"Authorization": f"Bearer {service_role_key}", "apikey": service_role_key}
        self._client = client or httpx.Client(timeout=httpx.Timeout(60.0, connect=10.0))

    def _check(self, response: httpx.Response, action: str) -> None:
        if response.status_code >= 400:
            # Never echo the response body: it may contain request details.
            raise StorageError(f"Supabase Storage could not {action} the file (HTTP {response.status_code}).")

    def save(self, key: str, data: bytes) -> None:
        try:
            response = self._client.post(
                f"{self._base}/object/{self._bucket}/{key}",
                content=data,
                headers={**self._headers, "Content-Type": "application/pdf", "x-upsert": "true"},
            )
        except httpx.HTTPError as exc:
            raise StorageError("Supabase Storage is unreachable.") from exc
        self._check(response, "store")

    def load(self, key: str) -> bytes:
        try:
            response = self._client.get(f"{self._base}/object/authenticated/{self._bucket}/{key}", headers=self._headers)
        except httpx.HTTPError as exc:
            raise StorageError("Supabase Storage is unreachable.") from exc
        if response.status_code in (400, 404):
            raise StorageError("The stored file could not be found.", code="file_missing")
        self._check(response, "read")
        return response.content

    def delete(self, key: str) -> None:
        try:
            response = self._client.request(
                "DELETE", f"{self._base}/object/{self._bucket}", json={"prefixes": [key]}, headers=self._headers
            )
        except httpx.HTTPError as exc:
            raise StorageError("Supabase Storage is unreachable.") from exc
        self._check(response, "delete")
