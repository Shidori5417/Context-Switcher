"""Process Manager Agent birim testleri — psutil mock'lu."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.agents.process_manager import ProcessManagerAgent
from src.core.event_bus import SwitchEvent


def _make_proc(pid: int, name: str, status: str = "running", mem_mb: float = 100.0) -> MagicMock:
    """Sahte psutil.Process nesnesi üretir."""
    proc = MagicMock()
    proc.pid = pid
    proc.name.return_value = name
    proc.exe.return_value = f"/usr/bin/{name}"
    proc.status.return_value = status
    proc.cpu_percent.return_value = 5.0

    mem_info = MagicMock()
    mem_info.rss = int(mem_mb * 1024 * 1024)
    proc.memory_info.return_value = mem_info

    # oneshot context manager
    proc.oneshot.return_value.__enter__ = MagicMock(return_value=None)
    proc.oneshot.return_value.__exit__ = MagicMock(return_value=False)

    proc.info = {"name": name, "exe": f"/usr/bin/{name}", "status": status}
    return proc


class TestFindProcesses:
    def test_finds_by_name(self):
        agent = ProcessManagerAgent()
        mock_proc = _make_proc(1234, "discord")
        mock_proc.info = {"name": "discord", "exe": "/usr/bin/discord", "status": "running"}

        with patch("psutil.process_iter", return_value=[mock_proc]):
            results = agent.find_processes("discord")

        assert len(results) == 1
        assert results[0].pid == 1234

    def test_case_insensitive(self):
        agent = ProcessManagerAgent()
        mock_proc = _make_proc(1234, "Discord")
        mock_proc.info = {"name": "Discord", "exe": "/usr/bin/Discord", "status": "running"}

        with patch("psutil.process_iter", return_value=[mock_proc]):
            results = agent.find_processes("discord")

        assert len(results) == 1

    def test_not_found(self):
        agent = ProcessManagerAgent()
        with patch("psutil.process_iter", return_value=[]):
            results = agent.find_processes("nonexistent")
        assert results == []


class TestSuspendProcesses:
    def test_suspend_normal_process(self):
        agent = ProcessManagerAgent()
        mock_discord = _make_proc(5000, "discord")

        with patch.object(agent, "find_processes", return_value=[mock_discord]):
            pids, report = agent.suspend_processes(["discord"], dry_run=False)

        mock_discord.suspend.assert_called_once()
        assert 5000 in pids
        assert len(report.suspended) == 1
        assert report.saved_memory_mb > 0

    def test_dry_run_does_not_suspend(self):
        agent = ProcessManagerAgent()
        mock_discord = _make_proc(5000, "discord")

        with patch.object(agent, "find_processes", return_value=[mock_discord]):
            pids, report = agent.suspend_processes(["discord"], dry_run=True)

        mock_discord.suspend.assert_not_called()
        assert 5000 in pids

    def test_protected_process_skipped(self):
        agent = ProcessManagerAgent()
        mock_sys = _make_proc(1, "systemd")

        with patch.object(agent, "find_processes", return_value=[mock_sys]):
            pids, report = agent.suspend_processes(["systemd"])

        mock_sys.suspend.assert_not_called()
        assert pids == []
        assert len(report.skipped) == 1

    def test_extra_protected_skipped(self):
        agent = ProcessManagerAgent(extra_protected=["myapp"])
        mock_app = _make_proc(9999, "myapp")

        with patch.object(agent, "find_processes", return_value=[mock_app]):
            pids, report = agent.suspend_processes(["myapp"])

        mock_app.suspend.assert_not_called()

    def test_process_not_found_is_skipped(self):
        agent = ProcessManagerAgent()
        with patch.object(agent, "find_processes", return_value=[]):
            pids, report = agent.suspend_processes(["ghost_app"])
        assert pids == []
        assert len(report.skipped) == 1

    def test_resource_report_memory(self):
        agent = ProcessManagerAgent()
        mock_proc = _make_proc(2000, "steam", mem_mb=512.0)
        with patch.object(agent, "find_processes", return_value=[mock_proc]):
            _, report = agent.suspend_processes(["steam"])
        assert report.saved_memory_mb == pytest.approx(512.0, abs=1.0)


class TestResumeProcesses:
    def test_resume_suspended(self):
        agent = ProcessManagerAgent()
        mock_proc = MagicMock()
        mock_proc.name.return_value = "discord"

        with patch("psutil.Process", return_value=mock_proc):
            report = agent.resume_processes([5000])

        mock_proc.resume.assert_called_once()
        assert len(report.resumed) == 1

    def test_resume_dry_run(self):
        agent = ProcessManagerAgent()
        mock_proc = MagicMock()
        mock_proc.name.return_value = "discord"

        with patch("psutil.Process", return_value=mock_proc):
            report = agent.resume_processes([5000], dry_run=True)

        mock_proc.resume.assert_not_called()


class TestStartProcesses:
    def test_start_success(self):
        agent = ProcessManagerAgent()
        with patch("subprocess.Popen") as mock_popen:
            report = agent.start_processes(["vscode"])
        mock_popen.assert_called_once()
        assert len(report.started) == 1

    def test_start_dry_run(self):
        agent = ProcessManagerAgent()
        with patch("subprocess.Popen") as mock_popen:
            report = agent.start_processes(["vscode"], dry_run=True)
        mock_popen.assert_not_called()
        assert len(report.started) == 1

    def test_start_not_found(self):
        agent = ProcessManagerAgent()
        with patch("subprocess.Popen", side_effect=FileNotFoundError):
            report = agent.start_processes(["nonexistent_app"])
        assert len(report.errors) == 1


class TestExecute:
    def test_execute_full_event(self):
        agent = ProcessManagerAgent()
        config = {
            "name": "Dev",
            "processes": {"suspend": ["discord"], "start": ["vscode"]},
        }
        event = SwitchEvent(mode_name="dev", config=config)

        with (
            patch.object(agent, "suspend_processes") as mock_suspend,
            patch.object(agent, "start_processes") as mock_start,
        ):
            from src.agents.process_manager import ResourceReport
            mock_suspend.return_value = ([5000], ResourceReport())
            mock_start.return_value = ResourceReport()

            report = agent.execute(event)

        mock_suspend.assert_called_once_with(["discord"], dry_run=False)
        mock_start.assert_called_once_with(["vscode"], dry_run=False)
        assert report.success

    def test_execute_dry_run(self):
        agent = ProcessManagerAgent()
        config = {"name": "Dev", "processes": {"suspend": ["discord"]}}
        event = SwitchEvent(mode_name="dev", config=config, dry_run=True)

        with patch.object(agent, "suspend_processes") as mock_suspend:
            from src.agents.process_manager import ResourceReport
            mock_suspend.return_value = ([], ResourceReport())
            agent.execute(event)

        _, kwargs = mock_suspend.call_args
        assert kwargs.get("dry_run") is True
