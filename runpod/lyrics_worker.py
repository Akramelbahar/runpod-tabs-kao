"""RunPod lyrics handler: Demucs vocals, then WhisperX word alignment."""
from __future__ import annotations

import gc
import os
import subprocess
import sys
from pathlib import Path

from common import MAX_AUDIO_BYTES, audio_suffix, download, model_revision, require_input, upload_json, workdir

_model = None
_aligners = {}
DEMUCS_MODEL = "htdemucs"
DEMUCS_TIMEOUT_SECONDS = 20 * 60


def model():
    global _model
    if _model is None:
        import whisperx
        _model = whisperx.load_model(model_revision("WHISPERX_MODEL"), "cuda", compute_type="float16")
    return _model


def release_asr_gpu_memory() -> None:
    """A reused worker must free WhisperX VRAM before Demucs starts."""
    global _model
    if _model is None and not _aligners:
        return
    _model = None
    _aligners.clear()
    gc.collect()
    import torch
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


def demucs_vocals(audio_path: Path, directory: Path) -> tuple[Path | None, str | None]:
    """Separate vocals in a child process so its CUDA memory is released."""
    if os.getenv("LYRICS_USE_DEMUCS", "1") == "0":
        return None, "disabled"
    release_asr_gpu_memory()
    output_dir = directory / "separated"
    command = [sys.executable, "-m", "demucs", "--two-stems=vocals", "-n", DEMUCS_MODEL,
               "-d", "cuda", "--out", str(output_dir), str(audio_path)]
    try:
        result = subprocess.run(command, capture_output=True, text=True,
                                timeout=DEMUCS_TIMEOUT_SECONDS, check=False)
    except subprocess.TimeoutExpired:
        return None, "timeout"
    except OSError:
        return None, "launch_failed"
    if result.returncode != 0:
        return None, "separation_failed"
    vocals = output_dir / DEMUCS_MODEL / audio_path.stem / "vocals.wav"
    if not vocals.is_file() or vocals.stat().st_size <= 44:
        return None, "empty_vocals"
    return vocals, None


def transcribe_words(audio_path: Path) -> tuple[str | None, list[dict], list[dict]]:
    import whisperx
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
    return language, words, lines


def handler(job: dict) -> dict:
    data = require_input(job, "lyrics")
    with workdir() as temporary:
        audio_path = Path(temporary) / f"audio{audio_suffix(data)}"
        source_sha = download(data.get("inputUrl"), audio_path, MAX_AUDIO_BYTES, data.get("inputSha256"))
        vocals, fallback_reason = demucs_vocals(audio_path, Path(temporary))
        selected = vocals or audio_path
        language, words, lines = transcribe_words(selected)
        if vocals and not words:
            language, words, lines = transcribe_words(audio_path)
            selected = audio_path
            fallback_reason = "no_words_in_vocals"
        audio_source = "demucs_vocals" if selected == vocals else "original_mix"
        reference = upload_json(data.get("outputUrl"), {"schemaVersion": 1, "sourceSha256": source_sha,
            "model": model_revision("WHISPERX_MODEL"), "language": language, "words": words, "lines": lines,
            "audioSource": audio_source, "separationModel": DEMUCS_MODEL if vocals else None,
            "fallbackReason": fallback_reason})
    return {"schemaVersion": 1, "stage": "lyrics", "jobId": data["jobId"],
            "status": "succeeded", "model": model_revision("WHISPERX_MODEL"), "result": reference,
            "wordCount": len(words), "diagnostics": [{"audioSource": audio_source,
            "fallbackReason": fallback_reason}]}


if __name__ == "__main__":
    import runpod
    runpod.serverless.start({"handler": handler})
