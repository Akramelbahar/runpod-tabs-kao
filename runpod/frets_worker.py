"""RunPod CPU handler for the accepted, strict six-string guitar checkpoint."""
from __future__ import annotations

import json
import os
import hashlib
import tempfile
import zipfile
from pathlib import Path

from common import MAX_JSON_BYTES, download, require_input, upload_json, workdir

_backend = None
HANDOFF_SHA256 = "b4fcdb7a0c19b08b97fb5ab91d29bda47609ef2e60f4a4603bc8aac4453a932e"
HANDOFF_NAME = "accepted-core-app-handoff-v1-20261005.zip"


def package_dir() -> Path:
    baked = Path("/opt/midi2frets")
    if (baked / "app_backend.py").is_file():
        return baked
    archive = Path(os.getenv("MIDI2FRETS_HANDOFF_ZIP", f"/runpod-volume/midi2frets/{HANDOFF_NAME}"))
    if not archive.is_file():
        raise FileNotFoundError(f"midi2frets handoff ZIP is missing: {archive}")
    digest = hashlib.sha256()
    with archive.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    if digest.hexdigest() != HANDOFF_SHA256:
        raise ValueError("midi2frets handoff ZIP SHA256 mismatch")
    target = Path(tempfile.mkdtemp(prefix="midi2frets-"))
    with zipfile.ZipFile(archive) as package:
        package.extractall(target)
    return target


def backend():
    global _backend
    if _backend is None:
        import sys
        sys.path.insert(0, str(package_dir()))
        from app_backend import GuitarBackend

        _backend = GuitarBackend(device="cpu", cpu_threads=int(os.getenv("MIDI2FRETS_CPU_THREADS", "4")))
    return _backend


def handler(job: dict) -> dict:
    data = require_input(job, "frets")
    with workdir() as temporary:
        path = Path(temporary) / "request.json"
        download(data.get("inputUrl"), path, MAX_JSON_BYTES, data.get("inputSha256"))
        request = json.loads(path.read_text(encoding="utf-8"))
        if request.get("sourceTrack", {}).get("role") != "guitar":
            raise ValueError("Only a guitar source track is supported")
        result = backend().convert(request)
        reference = upload_json(data.get("outputUrl"), result)
    return {"schemaVersion": 1, "stage": "frets", "jobId": data["jobId"],
            "status": "succeeded" if result.get("ok") else "refused",
            "model": "accepted-core-52a178b6d3d5", "result": reference,
            "diagnostics": result.get("diagnostics", [])[:20]}


if __name__ == "__main__":
    import runpod

    runpod.serverless.start({"handler": handler})
