"""Snapshot modülü testleri."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.core.snapshot import (
    latest_snapshot,
    list_snapshots,
    load_snapshot,
    restore_snapshot,
    take_snapshot,
)


class TestTakeSnapshot:
    def test_creates_file(self, tmp_path):
        mock_proc = MagicMock()
        mock_proc.pid = 1234
        mock_proc.name.return_value = "test_app"
        mock_proc.exe.return_value = "/bin/test_app"
        mock_proc.status.return_value = "running"
        mock_proc.cpu_percent.return_value = 1.0
        mock_proc.memory_info.return_value.rss = 100 * 1024 * 1024
        mock_proc.oneshot.return_value.__enter__ = MagicMock(return_value=None)
        mock_proc.oneshot.return_value.__exit__ = MagicMock(return_value=False)

        with (
            patch("src.core.snapshot.SNAPSHOT_DIR", tmp_path),
            patch("psutil.process_iter", return_value=[mock_proc]),
        ):
            path = take_snapshot("dev", suspended_pids=[1234])

        assert path.exists()
        data = json.loads(path.read_text())
        assert data["mode_name"] == "dev"
        assert data["suspended_pids"] == [1234]
        assert len(data["processes"]) == 1

    def test_snapshot_dir_created(self, tmp_path):
        new_dir = tmp_path / "snapshots"
        with (
            patch("src.core.snapshot.SNAPSHOT_DIR", new_dir),
            patch("psutil.process_iter", return_value=[]),
        ):
            path = take_snapshot("test")

        assert new_dir.exists()


class TestLoadSnapshot:
    def test_load_existing(self, tmp_path):
        snap = tmp_path / "snap.json"
        data = {"mode_name": "dev", "suspended_pids": [100], "processes": []}
        snap.write_text(json.dumps(data))

        result = load_snapshot(snap)
        assert result["mode_name"] == "dev"

    def test_load_missing_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_snapshot(tmp_path / "nonexistent.json")


class TestRestoreSnapshot:
    def test_resumes_pids(self, tmp_path):
        snap = tmp_path / "snap.json"
        data = {"mode_name": "dev", "suspended_pids": [100, 200], "processes": []}
        snap.write_text(json.dumps(data))

        mock_proc = MagicMock()

        with patch("psutil.Process", return_value=mock_proc):
            resumed = restore_snapshot(snap)

        assert len(resumed) == 2
        assert mock_proc.resume.call_count == 2

    def test_skips_dead_process(self, tmp_path):
        import psutil as _psutil
        snap = tmp_path / "snap.json"
        data = {"mode_name": "dev", "suspended_pids": [9999], "processes": []}
        snap.write_text(json.dumps(data))

        with patch("psutil.Process", side_effect=_psutil.NoSuchProcess(9999)):
            resumed = restore_snapshot(snap)

        assert resumed == []

    def test_no_pids(self, tmp_path):
        snap = tmp_path / "snap.json"
        snap.write_text(json.dumps({"mode_name": "dev", "suspended_pids": [], "processes": []}))
        resumed = restore_snapshot(snap)
        assert resumed == []


class TestListSnapshots:
    def test_lists_in_reverse_order(self, tmp_path):
        (tmp_path / "a.json").write_text("{}")
        (tmp_path / "b.json").write_text("{}")

        with patch("src.core.snapshot.SNAPSHOT_DIR", tmp_path):
            snaps = list_snapshots()

        assert len(snaps) == 2

    def test_empty_dir(self, tmp_path):
        with patch("src.core.snapshot.SNAPSHOT_DIR", tmp_path):
            snaps = list_snapshots()
        assert snaps == []

    def test_nonexistent_dir(self, tmp_path):
        with patch("src.core.snapshot.SNAPSHOT_DIR", tmp_path / "missing"):
            snaps = list_snapshots()
        assert snaps == []
