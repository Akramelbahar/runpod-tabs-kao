"""Small, versioned transport shared by IdealChords RunPod workers."""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

SCHEMA_VERSION = 1
MAX_AUDIO_BYTES = 250 * 1024 * 1024
MAX_JSON_BYTES = 32 * 1024 * 1024


def require_input(job: dict, stage: str) -> dict:
    data = job.get("input")
    if not isinstance(data, dict) or data.get("schemaVersion") != SCHEMA_VERSION:
        raise ValueError("Expected input schemaVersion 1")
    if data.get("stage") != stage:
        raise ValueError(f"Expected stage {stage}")
    if not isinstance(data.get("jobId"), str) or not data["jobId"]:
        raise ValueError("jobId is required")
    return data


def _https_url(value: object) -> str:
    if not isinstance(value, str) or urlparse(value).scheme != "https":
        raise ValueError("A signed HTTPS URL is required")
    return value


def download(url: object, destination: Path, max_bytes: int, expected_sha256: str | None = None) -> str:
    request = Request(_https_url(url), method="GET")
    digest = hashlib.sha256()
    size = 0
    with urlopen(request, timeout=120) as source, destination.open("wb") as target:
        while chunk := source.read(1024 * 1024):
            size += len(chunk)
            if size > max_bytes:
                raise ValueError("Input exceeds size limit")
            digest.update(chunk)
            target.write(chunk)
    actual = digest.hexdigest()
    if expected_sha256 and actual != expected_sha256:
        raise ValueError("Input SHA256 mismatch")
    return actual


def upload_json(url: object, result: dict) -> dict:
    payload = json.dumps(result, allow_nan=False, separators=(",", ":")).encode("utf-8")
    if len(payload) > MAX_JSON_BYTES:
        raise ValueError("Result exceeds JSON size limit")
    return upload_bytes(url, payload, "application/json")


def upload_bytes(url: object, payload: bytes, content_type: str) -> dict:
    digest = hashlib.sha256(payload).hexdigest()
    request = Request(_https_url(url), data=payload, headers={"Content-Type": content_type}, method="PUT")
    with urlopen(request, timeout=120) as response:
        if response.status // 100 != 2:
            raise RuntimeError("Artifact upload failed")
    return {"sha256": digest, "bytes": len(payload)}


def workdir():
    return tempfile.TemporaryDirectory(prefix="idealchords-")


def model_revision(name: str) -> str:
    revision = os.getenv(name, "").strip()
    if not revision:
        raise RuntimeError(f"{name} must be pinned")
    return revision


def audio_suffix(data: dict) -> str:
    suffix = data.get("audioSuffix")
    if suffix not in {".mp3", ".wav", ".flac", ".m4a", ".ogg", ".opus", ".webm"}:
        raise ValueError("audioSuffix must be a supported extension")
    return suffix
