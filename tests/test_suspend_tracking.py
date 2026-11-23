"""Suspend/resume takibi, rollback ve süreç eşleştirme testleri.

Tüm testlerde psutil mock'lanır; gerçek süreç dondurulmaz/uyandırılmaz.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import psutil
import pytest

from src.agents.orchestrator import OrchestratorAgent
from src.agents.process_manager import ProcessManagerAgent
from src.core import state as state_mod
from src.core.event_bus import StatusReport, SwitchEvent
from src.core.procs import matches_entry, merge_entries, normalize_entries
from src.core.snapshot import restore_snapshot, take_snapshot


def _iter_proc(pid: int, name: str, exe: str = "", create_time: float = 1000.0) -> MagicMock:
    proc = MagicMock()
    proc.pid = pid
    proc.info = {"name": name, "exe": exe, "status": "running"}
    proc.name.return_value = name
    proc.create_time.return_value = create_time
    proc.memory_info.return_value.rss = 10 * 1024 * 1024
    proc.cpu_percent.return_value = 0.0
    return proc


@pytest.fixture
def tmp_home(tmp_path):
    """State ve snapshot dosyalarını geçici dizine yönlendirir."""
    with (
        patch.object(state_mod, "_STATE_PATH", tmp_path / "state.json"),
        patch("src.core.snapshot.SNAPSHOT_DIR", tmp_path / "snapshots"),
        patch("psutil.process_iter", return_value=[]),
    ):
        yield tmp_path


# ── Bug 3: tam eşleşme ─────────────────────────────────────────────────────────


class TestExactMatching:
    def _find(self, procs, name):
        with patch("psutil.process_iter", return_value=procs):
            return [p.pid for p in ProcessManagerAgent().find_processes(name)]

    def test_substring_does_not_match(self):
        procs = [
            _iter_proc(200, "t3code", "/opt/t3code/t3code"),
            _iter_proc(201, "vscode-server", "/home/u/.vscode-server/bin/node"),
            _iter_proc(202, "code", "/usr/bin/code"),
        ]
        assert self._find(procs, "code") == [202]

    def test_path_substring_does_not_match(self):
        # Eskiden "code" tam yolun içinde geçtiği için eşleşirdi
        procs = [_iter_proc(300, "node", "/home/u/code/project/node")]
        assert self._find(procs, "code") == []

    def test_exe_suffix_with_and_without(self):
        procs = [
            _iter_proc(400, "Discord.exe", r"C:\Users\u\Discord\Discord.exe"),
            _iter_proc(401, "discord", "/usr/bin/discord"),
        ]
        assert self._find(procs, "discord") == [400, 401]
        assert self._find(procs, "Discord.exe") == [400, 401]

    def test_matches_exe_basename_when_name_differs(self):
        procs = [_iter_proc(500, "Web Content", r"C:\Program Files\Slack\slack.exe")]
        assert self._find(procs, "slack") == [500]

    def test_none_name_and_exe_are_safe(self):
        proc = _iter_proc(600, "x")
        proc.info = {"name": None, "exe": None, "status": "running"}
        assert self._find([proc], "code") == []


# ── Bug 4: anlık kayıt ─────────────────────────────────────────────────────────


class TestIncrementalRecording:
    def test_pids_survive_mid_loop_exception(self):
        agent = ProcessManagerAgent()
        first = _iter_proc(1000, "discord", create_time=111.0)
        second = _iter_proc(1001, "discord", create_time=222.0)
        second.suspend.side_effect = RuntimeError("beklenmeyen")

        with patch.object(agent, "find_processes", return_value=[first, second]):
            with pytest.raises(RuntimeError):
                agent.suspend_processes(["discord"])

        assert agent._last_suspended_procs == [{"pid": 1000, "create_time": 111.0}]
        first.suspend.assert_called_once()

    def test_execute_reports_failure_with_recorded_procs(self):
        agent = ProcessManagerAgent()
        first = _iter_proc(1000, "discord", create_time=111.0)
        second = _iter_proc(1001, "discord", create_time=222.0)
        second.suspend.side_effect = RuntimeError("boom")
        event = SwitchEvent(mode_name="x", config={"processes": {"suspend": ["discord"]}})

        with patch.object(agent, "find_processes", return_value=[first, second]):
            report = agent.execute(event)

        assert not report.success
        assert report.details["suspended_procs"] == [{"pid": 1000, "create_time": 111.0}]

    def test_dry_run_records_nothing(self):
        agent = ProcessManagerAgent()
        proc = _iter_proc(1000, "discord")
        with patch.object(agent, "find_processes", return_value=[proc]):
            agent.suspend_processes(["discord"], dry_run=True)
        assert agent._last_suspended_procs == []
        proc.suspend.assert_not_called()

    def test_execute_details_contain_create_time(self):
        agent = ProcessManagerAgent()
        proc = _iter_proc(1000, "discord", create_time=123.5)
        event = SwitchEvent(mode_name="x", config={"processes": {"suspend": ["discord"]}})
        with patch.object(agent, "find_processes", return_value=[proc]):
            report = agent.execute(event)
        assert report.details["suspended_pids"] == [1000]
        assert report.details["suspended_procs"] == [{"pid": 1000, "create_time": 123.5}]


# ── Bug 5: PID yeniden kullanımı ───────────────────────────────────────────────


class TestPidReuse:
    def test_resume_skipped_when_create_time_differs(self):
        proc = MagicMock()
        proc.create_time.return_value = 5000.0
        with patch("psutil.Process", return_value=proc):
            report = ProcessManagerAgent().resume_processes([{"pid": 42, "create_time": 1000.0}])
        proc.resume.assert_not_called()
        assert report.resumed == []
        assert "yeniden kullanılmış" in report.errors[0].error

    def test_resume_when_create_time_matches(self):
        proc = MagicMock()
        proc.create_time.return_value = 1000.001
        with patch("psutil.Process", return_value=proc):
            report = ProcessManagerAgent().resume_processes([{"pid": 42, "create_time": 1000.0}])
        proc.resume.assert_called_once()
        assert len(report.resumed) == 1

    def test_legacy_int_pids_still_resume(self):
        proc = MagicMock()
        with patch("psutil.Process", return_value=proc):
            report = ProcessManagerAgent().resume_processes([42])
        proc.resume.assert_called_once()
        assert len(report.resumed) == 1

    def test_normalize_and_merge(self):
        assert normalize_entries([1, {"pid": 2, "create_time": 3.0}, "bad", True]) == [
            {"pid": 1, "create_time": None},
            {"pid": 2, "create_time": 3.0},
        ]
        merged = merge_entries([1, 2], [{"pid": 1, "create_time": 9.0}, 3])
        assert merged == [
            {"pid": 1, "create_time": 9.0},
            {"pid": 2, "create_time": None},
            {"pid": 3, "create_time": None},
        ]

    def test_matches_entry_without_create_time(self):
        assert matches_entry(MagicMock(), {"pid": 1, "create_time": None})

    def test_restore_snapshot_checks_create_time(self, tmp_path):
        snap = tmp_path / "s.json"
        snap.write_text(
            json.dumps(
                {
                    "suspended_pids": [
                        {"pid": 1, "create_time": 10.0},  # eşleşiyor
                        {"pid": 2, "create_time": 10.0},  # PID yeniden kullanılmış
                        3,  # eski format
                    ]
                }
            ),
            encoding="utf-8",
        )
        procs = {1: 10.0, 2: 99999.0, 3: 5.0}

        def fake_process(pid):
            p = MagicMock()
            p.create_time.return_value = procs[pid]
            return p

        with patch("psutil.Process", side_effect=fake_process):
            resumed = restore_snapshot(snap)
        assert resumed == [1, 3]

    def test_old_state_file_with_int_list_loads(self, tmp_home):
        (tmp_home / "state.json").write_text(
            json.dumps({"current_mode": "dev", "suspended_pids": [7, 8]}), encoding="utf-8"
        )
        state = state_mod.get_state()
        assert normalize_entries(state.suspended_pids) == [
            {"pid": 7, "create_time": None},
            {"pid": 8, "create_time": None},
        ]


# ── Bug 1: snapshot PID'leri ve rollback ───────────────────────────────────────


def _orch_with_pm_report(procs):
    orch = OrchestratorAgent()
    for agent in orch._agents:
        agent.execute = MagicMock(
            return_value=StatusReport(agent_name=agent.name, success=True, message="OK")
        )
    pm = orch._agents[0]
    pm.execute = MagicMock(
        return_value=StatusReport(
            agent_name=pm.name,
            success=True,
            message="OK",
            details={"suspended_pids": [p["pid"] for p in procs], "suspended_procs": procs},
        )
    )
    return orch


class TestSnapshotRecordsSuspended:
    def test_snapshot_and_state_updated_after_switch(self, tmp_home):
        procs = [{"pid": 10, "create_time": 1.0}, {"pid": 11, "create_time": 2.0}]
        orch = _orch_with_pm_report(procs)

        result = orch.execute(SwitchEvent(mode_name="dev", config={}, previous_mode=None))

        assert result.success
        state = state_mod.get_state()
        assert state.suspended_pids == procs
        snap = json.loads(open(state.last_snapshot, encoding="utf-8").read())
        assert snap["suspended_pids"] == procs

    def test_rollback_resumes_snapshot_pids(self, tmp_home):
        from src import cli

        snap = take_snapshot("dev", suspended_pids=[{"pid": 10, "create_time": 1.0}])
        state_mod.update_state(current_mode="dev", last_snapshot=str(snap), suspended_pids=[])

        proc = MagicMock()
        proc.create_time.return_value = 1.0
        with patch("psutil.Process", return_value=proc) as ctor:
            cli._handle_rollback()

        ctor.assert_called_with(10)
        proc.resume.assert_called_once()
        assert state_mod.get_state().current_mode is None  # state temizlendi

    def test_rollback_uses_union_of_snapshot_and_state(self, tmp_home):
        from src import cli

        snap = take_snapshot("dev", suspended_pids=[{"pid": 10, "create_time": None}])
        state_mod.update_state(
            current_mode="dev",
            last_snapshot=str(snap),
            suspended_pids=[{"pid": 10, "create_time": None}, 20],
        )

        resumed: list[int] = []

        def fake_process(pid):
            p = MagicMock()
            p.resume.side_effect = lambda: resumed.append(pid)
            return p

        with patch("psutil.Process", side_effect=fake_process):
            cli._handle_rollback()

        assert sorted(resumed) == [10, 20]  # tekilleştirilmiş birleşim

    def test_rollback_falls_back_to_state_when_snapshot_missing(self, tmp_home):
        from src import cli

        state_mod.update_state(
            current_mode="dev",
            last_snapshot=str(tmp_home / "yok.json"),
            suspended_pids=[30],
        )
        proc = MagicMock()
        with patch("psutil.Process", return_value=proc):
            cli._handle_rollback()
        proc.resume.assert_called_once()


# ── Bug 2: mod değişiminde önceki modun süreçleri ──────────────────────────────


class TestSwitchResumesPreviousMode:
    def test_previous_suspended_are_resumed_and_only_new_tracked(self, tmp_home):
        state_mod.update_state(
            current_mode="gaming",
            suspended_pids=[{"pid": 10, "create_time": 1.0}, {"pid": 20, "create_time": 2.0}],
        )
        new = [{"pid": 20, "create_time": 2.0}, {"pid": 30, "create_time": 3.0}]
        orch = _orch_with_pm_report(new)
        resumed_calls = []

        def fake_resume(entries, dry_run=False):
            resumed_calls.append(entries)
            from src.agents.process_manager import ResourceReport

            return ResourceReport()

        orch._agents[0].resume_processes = fake_resume

        result = orch.execute(SwitchEvent(mode_name="study", config={}, previous_mode="gaming"))

        assert result.success
        assert [e["pid"] for e in resumed_calls[0]] == [10, 20]
        assert state_mod.get_state().suspended_pids == new  # 10 artık izlenmiyor

    def test_unresumable_previous_stay_tracked(self, tmp_home):
        state_mod.update_state(
            current_mode="gaming", suspended_pids=[{"pid": 10, "create_time": 1.0}]
        )
        orch = _orch_with_pm_report([{"pid": 30, "create_time": 3.0}])

        proc = MagicMock()
        proc.create_time.return_value = 1.0
        proc.resume.side_effect = psutil.AccessDenied(10)
        with patch("psutil.Process", return_value=proc):
            orch.execute(SwitchEvent(mode_name="study", config={}, previous_mode="gaming"))

        pids = [e["pid"] for e in state_mod.get_state().suspended_pids]
        assert pids == [30, 10]

    def test_dry_run_does_not_resume_previous(self, tmp_home):
        state_mod.update_state(current_mode="gaming", suspended_pids=[10])
        orch = _orch_with_pm_report([])
        orch._agents[0].resume_processes = MagicMock()

        orch.execute(
            SwitchEvent(mode_name="study", config={}, previous_mode="gaming", dry_run=True)
        )

        orch._agents[0].resume_processes.assert_not_called()
        assert state_mod.get_state().suspended_pids == [10]


class TestBundledModesMatchPlatformNames:
    """Paketlenmiş mod YAML'ları her platformdaki gerçek süreç adlarıyla (tam eşleşme) uyuşmalı."""

    @staticmethod
    def _suspend_list(mode: str) -> list[str]:
        import pathlib

        import yaml

        path = pathlib.Path(__file__).resolve().parent.parent / "modes" / f"{mode}.yaml"
        return yaml.safe_load(path.read_text(encoding="utf-8"))["processes"]["suspend"]

    @staticmethod
    def _matches(names: list[str], proc_name: str) -> bool:
        proc = _iter_proc(1, proc_name)
        agent = ProcessManagerAgent()
        with patch("psutil.process_iter", return_value=[proc]):
            return any(agent.find_processes(name) for name in names)

    @pytest.mark.parametrize(
        "proc_name", ["chrome.exe", "Google Chrome", "google-chrome", "chrome"]
    )
    def test_study_suspends_chrome_on_every_platform(self, proc_name):
        assert self._matches(self._suspend_list("study"), proc_name)

    @pytest.mark.parametrize("proc_name", ["Docker Desktop.exe", "Docker Desktop", "docker"])
    def test_gaming_suspends_docker_on_every_platform(self, proc_name):
        assert self._matches(self._suspend_list("gaming"), proc_name)


class TestCreateTimeTolerance:
    def test_rapid_pid_reuse_is_rejected(self):
        proc = MagicMock()
        proc.create_time.return_value = 1000.5
        assert not matches_entry(proc, {"pid": 1, "create_time": 1000.0})

    def test_same_process_matches_after_json_roundtrip(self):
        proc = MagicMock()
        proc.create_time.return_value = 1731600000.123456
        stored = json.loads(json.dumps({"pid": 1, "create_time": 1731600000.123456}))
        assert matches_entry(proc, stored)
