"""Integrity and fail-closed tests for the offline environment probe."""
import gzip
import hashlib
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from zipfile import ZipFile
import verify_offline_environment as probe


class EnvironmentTests(unittest.TestCase):
    def archive(self, root, *, rows=26304, frozen=probe.COMMIT, duplicate=False, malformed=False):
        path = Path(root) / "fixture.zip"
        summary = {"frozen_product": probe.COMMIT, "source_sha256": probe.SOURCE_SHA,
                   "original_input_contract_sha256": probe.INPUT_SHA,
                   "native_source_sha256": probe.PORTFOLIO_SHA}
        names = {"C0-native-hourly.json.gz": gzip.compress(
                 json.dumps({"frozen": frozen, "rows": [None] * rows}).encode()),
                 "S01-native-hourly.json.gz": gzip.compress(b"{}"),
                 "C0-native-summary.json": json.dumps(summary).encode(),
                 "S01-native-summary.json": b"{}",
                 "S02-DIAG-002-Report.json": b"{}"}
        if malformed:
            names["C0-native-hourly.json.gz"] = b"invalid gzip"
        with ZipFile(path, "w") as archive:
            for name, value in names.items():
                archive.writestr(name, value)
            if duplicate:
                archive.writestr("unexpected.txt", b"unexpected")
        return path

    def test_valid_fixture(self):
        with TemporaryDirectory() as root:
            path = self.archive(root)
            result = probe.verify_archive(path, probe.sha(path))
            self.assertEqual(result["c0_hours_read"], 26304)

    def test_tampered_sha_rejected(self):
        with TemporaryDirectory() as root:
            path = self.archive(root)
            with self.assertRaisesRegex(ValueError, "SHA256"):
                probe.verify_archive(path, "0" * 64)

    def test_unexpected_member_rejected(self):
        with TemporaryDirectory() as root:
            path = self.archive(root, duplicate=True)
            with self.assertRaisesRegex(ValueError, "members"):
                probe.verify_archive(path, probe.sha(path))

    def test_wrong_commit_rejected(self):
        with TemporaryDirectory() as root:
            path = self.archive(root, frozen="wrong")
            with self.assertRaisesRegex(ValueError, "commit"):
                probe.verify_archive(path, probe.sha(path))

    def test_missing_rows_rejected(self):
        with TemporaryDirectory() as root:
            path = self.archive(root, rows=26303)
            with self.assertRaisesRegex(ValueError, "row count"):
                probe.verify_archive(path, probe.sha(path))

    def test_expansion_bound(self):
        with TemporaryDirectory() as root:
            path = self.archive(root)
            with patch.object(probe, "MAX_MEMBER", 1000):
                with self.assertRaisesRegex(ValueError, "Oversized"):
                    probe.verify_archive(path, probe.sha(path))

    def test_malformed_compression_rejected(self):
        with TemporaryDirectory() as root:
            path = self.archive(root, malformed=True)
            with self.assertRaises(gzip.BadGzipFile):
                probe.verify_archive(path, probe.sha(path))

    def test_network_guard(self):
        with self.assertRaisesRegex(RuntimeError, "network"):
            probe.forbid_network("socket.connect", ())
        probe.forbid_network("open", ())


if __name__ == "__main__":
    unittest.main()
