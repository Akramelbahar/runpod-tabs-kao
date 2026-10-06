"""Offline checks for the volume-backed model loader."""
from __future__ import annotations

import hashlib
import os
import tempfile
import types
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

import frets_worker


class FretsVolumeTests(unittest.TestCase):
    def test_verified_volume_archive_is_extracted(self):
        with tempfile.TemporaryDirectory() as temporary:
            archive = Path(temporary) / "handoff.zip"
            with zipfile.ZipFile(archive, "w") as package:
                package.writestr("app_backend.py", "# test")
            digest = hashlib.sha256(archive.read_bytes()).hexdigest()
            with patch.dict(os.environ, {"MIDI2FRETS_HANDOFF_ZIP": str(archive)}), \
                 patch.object(frets_worker, "HANDOFF_SHA256", digest):
                extracted = frets_worker.package_dir()
            self.assertEqual((extracted / "app_backend.py").read_text(), "# test")

    def test_wrong_archive_hash_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            archive = Path(temporary) / "handoff.zip"
            archive.write_bytes(b"wrong model")
            with patch.dict(os.environ, {"MIDI2FRETS_HANDOFF_ZIP": str(archive)}):
                with self.assertRaisesRegex(ValueError, "SHA256 mismatch"):
                    frets_worker.package_dir()

    def test_private_hf_repo_uses_pinned_revision_and_token(self):
        calls = {}

        def fake_download(**kwargs):
            calls.update(kwargs)
            return "C:/test/handoff.zip"

        with patch.dict(os.environ, {"MIDI2FRETS_HF_REPO": "owner/private-model",
                                  "MIDI2FRETS_HF_REVISION": "a" * 40, "HF_TOKEN": "test-token"}), \
             patch.dict("sys.modules", {"huggingface_hub": types.SimpleNamespace(hf_hub_download=fake_download)}):
            archive = frets_worker.handoff_archive()
        self.assertEqual(archive, Path("C:/test/handoff.zip"))
        self.assertEqual(calls["repo_id"], "owner/private-model")
        self.assertEqual(calls["revision"], "a" * 40)
        self.assertEqual(calls["token"], "test-token")

    def test_private_hf_repo_requires_revision(self):
        with patch.dict(os.environ, {"MIDI2FRETS_HF_REPO": "owner/private-model", "HF_TOKEN": "test-token"}):
            os.environ.pop("MIDI2FRETS_HF_REVISION", None)
            with self.assertRaisesRegex(RuntimeError, "REVISION must be pinned"):
                frets_worker.handoff_archive()

    def test_check_model_loads_backend_without_artifact_urls(self):
        with patch.object(frets_worker, "backend") as load_backend:
            result = frets_worker.handler({"input": {"schemaVersion": 1, "stage": "frets",
                                                       "jobId": "check-1", "action": "check_model"}})
        load_backend.assert_called_once_with()
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["jobId"], "check-1")


if __name__ == "__main__":
    unittest.main()
