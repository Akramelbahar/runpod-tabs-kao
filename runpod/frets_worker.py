"""RunPod CPU handler for the accepted, strict six-string guitar checkpoint."""
from __future__ import annotations

import json
import os
from pathlib import Path

from common import MAX_JSON_BYTES, download, require_input, upload_json, workdir

_backend = None


def backend():
    global _backend
    if _backend is None:
        import sys
        sys.path.insert(0, "/opt/midi2frets")
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
