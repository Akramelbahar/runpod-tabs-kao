"""Offline checks for the volume-backed model loader."""
from __future__ import annotations

import hashlib
import os
import tempfile
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


if __name__ == "__main__":
    unittest.main()
