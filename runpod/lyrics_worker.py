"""RunPod GPU handler for the initial WhisperX lyrics evaluation provider."""
from __future__ import annotations

from pathlib import Path

from common import MAX_AUDIO_BYTES, audio_suffix, download, model_revision, require_input, upload_json, workdir

_model = None
_aligners = {}


def model():
    global _model
    if _model is None:
        import whisperx
        _model = whisperx.load_model(model_revision("WHISPERX_MODEL"), "cuda", compute_type="float16")
    return _model


def handler(job: dict) -> dict:
    data = require_input(job, "lyrics")
    import whisperx
    with workdir() as temporary:
        audio_path = Path(temporary) / f"audio{audio_suffix(data)}"
        source_sha = download(data.get("inputUrl"), audio_path, MAX_AUDIO_BYTES, data.get("inputSha256"))
        audio = whisperx.load_audio(str(audio_path))
        transcription = model().transcribe(audio, batch_size=8)
        language = transcription.get("language")
        segments = transcription.get("segments", [])
        if segments and language:
            if language not in _aligners:
                _aligners[language] = whisperx.load_align_model(language_code=language, device="cuda")
            aligner, metadata = _aligners[language]
            segments = whisperx.align(segments, aligner, metadata, audio, "cuda").get("segments", [])
        words = []
        lines = []
        for line_index, segment in enumerate(segments):
            line_id = f"line-{line_index}"
            ids = []
            for item in segment.get("words", []):
                if not isinstance(item.get("start"), (int, float)) or not isinstance(item.get("end"), (int, float)):
                    continue
                word_id = f"word-{len(words)}"
                words.append({"id": word_id, "text": item.get("word", "").strip(),
                              "startSec": item["start"], "endSec": item["end"], "lineId": line_id})
                ids.append(word_id)
            if ids:
                lines.append({"id": line_id, "wordIds": ids})
        reference = upload_json(data.get("outputUrl"), {"schemaVersion": 1, "sourceSha256": source_sha,
            "model": model_revision("WHISPERX_MODEL"), "language": language, "words": words, "lines": lines})
    return {"schemaVersion": 1, "stage": "lyrics", "jobId": data["jobId"],
            "status": "succeeded", "model": model_revision("WHISPERX_MODEL"), "result": reference,
            "wordCount": len(words)}


if __name__ == "__main__":
    import runpod
    runpod.serverless.start({"handler": handler})
