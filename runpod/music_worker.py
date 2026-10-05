"""RunPod GPU handler for MuScriptor. Raw MIDI remains the source artifact."""
from __future__ import annotations

from pathlib import Path

from common import MAX_AUDIO_BYTES, audio_suffix, download, model_revision, require_input, upload_bytes, workdir

_model = None


def model():
    global _model
    if _model is None:
        from muscriptor import TranscriptionModel
        _model = TranscriptionModel.load_model(model_revision("MUSCRIPTOR_MODEL"))
    return _model


def handler(job: dict) -> dict:
    data = require_input(job, "music")
    with workdir() as temporary:
        audio = Path(temporary) / f"audio{audio_suffix(data)}"
        source_sha = download(data.get("inputUrl"), audio, MAX_AUDIO_BYTES, data.get("inputSha256"))
        midi = model().transcribe_to_midi(str(audio))
        if not isinstance(midi, bytes) or not midi:
            raise RuntimeError("MuScriptor returned no MIDI")
        # The coordinator imports this MIDI into typed tracks. Keep the raw
        # MIDI so later beat/track corrections never require another GPU run.
        reference = upload_bytes(data.get("outputUrl"), midi, "audio/midi")
    return {"schemaVersion": 1, "stage": "music", "jobId": data["jobId"],
            "status": "succeeded", "model": model_revision("MUSCRIPTOR_MODEL"),
            "sourceSha256": source_sha, "result": reference}


if __name__ == "__main__":
    import runpod
    runpod.serverless.start({"handler": handler})
