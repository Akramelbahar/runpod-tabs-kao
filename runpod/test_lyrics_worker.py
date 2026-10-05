"""Offline transport tests; no CUDA weights or RunPod credentials required."""
from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import lyrics_worker


class LyricsWorkerTests(unittest.TestCase):
    def test_demucs_selects_the_vocal_stem(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            audio = root / "audio.mp3"
            audio.write_bytes(b"music")
            vocals = root / "separated" / "htdemucs" / "audio" / "vocals.wav"
            vocals.parent.mkdir(parents=True)
            vocals.write_bytes(b"v" * 100)
            with patch.dict(os.environ, {"LYRICS_USE_DEMUCS": "1"}), \
                 patch.object(lyrics_worker, "release_asr_gpu_memory"), \
                 patch.object(lyrics_worker.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)) as run:
                selected, reason = lyrics_worker.demucs_vocals(audio, root)
            self.assertEqual(selected, vocals)
            self.assertIsNone(reason)
            self.assertIn("--two-stems=vocals", run.call_args.args[0])
            self.assertIn("cuda", run.call_args.args[0])

    def test_demucs_failure_falls_back_to_original(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with patch.dict(os.environ, {"LYRICS_USE_DEMUCS": "1"}), \
                 patch.object(lyrics_worker, "release_asr_gpu_memory"), \
                 patch.object(lyrics_worker.subprocess, "run", return_value=subprocess.CompletedProcess([], 1)):
                self.assertEqual(lyrics_worker.demucs_vocals(root / "audio.mp3", root),
                                 (None, "separation_failed"))

    def test_no_words_in_vocals_retries_original_mix(self):
        source = Path("audio.mp3")
        vocal = Path("vocals.wav")
        stored = {}

        def fake_download(_url, destination, _limit, _digest):
            destination.write_bytes(b"music")
            return "a" * 64

        def fake_transcribe(audio):
            if audio.name == vocal.name:
                return "en", [], []
            self.assertEqual(audio.name, source.name)
            return "en", [{"id": "word-0", "text": "hello", "startSec": 1.0,
                           "endSec": 1.4, "lineId": "line-0"}], [{"id": "line-0", "wordIds": ["word-0"]}]

        def fake_upload(_url, payload):
            stored.update(payload)
            return {"sha256": "b" * 64, "bytes": 123}

        with patch.dict(os.environ, {"WHISPERX_MODEL": "small"}), \
             patch.object(lyrics_worker, "download", side_effect=fake_download), \
             patch.object(lyrics_worker, "demucs_vocals", return_value=(vocal, None)), \
             patch.object(lyrics_worker, "transcribe_words", side_effect=fake_transcribe) as transcribe, \
             patch.object(lyrics_worker, "upload_json", side_effect=fake_upload):
            result = lyrics_worker.handler({"input": {"schemaVersion": 1, "stage": "lyrics",
                "jobId": "job-1", "inputUrl": "https://example.test/audio", "inputSha256": "a" * 64,
                "outputUrl": "https://example.test/result", "audioSuffix": ".mp3"}})
        self.assertEqual(transcribe.call_count, 2)
        self.assertEqual(stored["audioSource"], "original_mix")
        self.assertEqual(stored["fallbackReason"], "no_words_in_vocals")
        self.assertEqual(result["wordCount"], 1)


if __name__ == "__main__":
    unittest.main()
