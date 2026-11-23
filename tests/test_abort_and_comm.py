"""Abort sonrası yeniden dondurma ve Linux comm (15 karakter) eşleşmesi testleri.

Tüm testlerde psutil mock'lanır; gerçek süreç dondurulmaz/uyandırılmaz.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import psutil
import pytest

from src.agents.orchestrator import OrchestratorAgent
from src.agents.process_manager import ProcessManagerAgent
from src.core import state as state_mod
from src.core.event_bus import StatusReport, SwitchEvent


@pytest.fixture
def tmp_home(tmp_path):
    with (
        patch.object(state_mod, "_STATE_PATH", tmp_path / "state.json"),
        patch("src.core.snapshot.SNAPSHOT_DIR", tmp_path / "snapshots"),
        patch("psutil.process_iter", return_value=[]),
    ):
        yield tmp_path


def _fake_procs(create_times: dict[int, float]):
    """pid -> MagicMock süreç; psutil.Process yan etkisi ve süreç sözlüğü döner."""
    procs: dict[int, MagicMock] = {}
    for pid, ct in create_times.items():
        p = MagicMock()
        p.pid = pid
        p.create_time.return_value = ct
        procs[pid] = p

    def factory(pid):
        if pid not in procs:
            raise psutil.NoSuchProcess(pid)
        return procs[pid]

    return procs, factory


def _failing_orch():
    """ProcessManager (kritik) başarısız olan orchestrator."""
    orch = OrchestratorAgent()
    pm = orch._agents[0]
    pm.execute = MagicMock(
        return_value=StatusReport(agent_name=pm.name, success=False, message="boom")
    )
    pm.rollback = MagicMock(
        return_value=StatusReport(agent_name=pm.name, success=True, message="rb")
    )
    return orch


PREV = [{"pid": 10, "create_time": 1.0}, {"pid": 20, "create_time": 2.0}]


class TestAbortResuspends:
    def test_resumed_previous_processes_are_suspended_again(self, tmp_home):
        state_mod.update_state(current_mode="gaming", suspended_pids=PREV)
        before = state_mod.get_state()
        procs, factory = _fake_procs({10: 1.0, 20: 2.0})

        with patch("psutil.Process", side_effect=factory):
            result = _failing_orch().execute(
                SwitchEvent(mode_name="study", config={}, previous_mode="gaming")
            )

        assert not result.success
        for p in procs.values():
            p.resume.assert_called_once()
            p.suspend.assert_called_once()
        after = state_mod.get_state()
        assert after.current_mode == "gaming"
        assert after.suspended_pids == PREV
        assert after.switched_at == before.switched_at

    def test_only_processes_resumed_in_this_attempt_are_resuspended(self, tmp_home):
        state_mod.update_state(current_mode="gaming", suspended_pids=PREV)
        procs, factory = _fake_procs({10: 1.0})  # 20 artık yok
        procs[10].resume.return_value = None

        with patch("psutil.Process", side_effect=factory):
            _failing_orch().execute(
                SwitchEvent(mode_name="study", config={}, previous_mode="gaming")
            )

        procs[10].suspend.assert_called_once()

    def test_unresumable_process_is_not_resuspended(self, tmp_home):
        state_mod.update_state(current_mode="gaming", suspended_pids=PREV)
        procs, factory = _fake_procs({10: 1.0, 20: 2.0})
        procs[10].resume.side_effect = psutil.AccessDenied(10)

        with patch("psutil.Process", side_effect=factory):
            _failing_orch().execute(
                SwitchEvent(mode_name="study", config={}, previous_mode="gaming")
            )

        procs[10].suspend.assert_not_called()
        procs[20].suspend.assert_called_once()

    def test_reused_pid_is_not_resuspended(self, tmp_home):
        state_mod.update_state(current_mode="gaming", suspended_pids=PREV)
        # PID 10 başka bir sürece geçmiş (create_time uyuşmuyor) -> uyandırılmaz, dondurulmaz
        procs, factory = _fake_procs({10: 999.0, 20: 2.0})

        with patch("psutil.Process", side_effect=factory):
            _failing_orch().execute(
                SwitchEvent(mode_name="study", config={}, previous_mode="gaming")
            )

        procs[10].resume.assert_not_called()
        procs[10].suspend.assert_not_called()

    def test_successful_switch_does_not_resuspend(self, tmp_home):
        state_mod.update_state(current_mode="gaming", suspended_pids=PREV)
        orch = OrchestratorAgent()
        for agent in orch._agents:
            agent.execute = MagicMock(
                return_value=StatusReport(agent_name=agent.name, success=True, message="OK")
            )
        procs, factory = _fake_procs({10: 1.0, 20: 2.0})

        with patch("psutil.Process", side_effect=factory):
            result = orch.execute(SwitchEvent(mode_name="study", config={}, previous_mode="gaming"))

        assert result.success
        for p in procs.values():
            p.suspend.assert_not_called()

    def test_abort_without_previous_mode_leaves_state_alone(self, tmp_home):
        procs, factory = _fake_procs({})
        with patch("psutil.Process", side_effect=factory):
            result = _failing_orch().execute(SwitchEvent(mode_name="study", config={}))
        assert not result.success
        assert not (tmp_home / "state.json").exists()

    def test_resuspend_processes_skips_dead_and_denied(self):
        procs, factory = _fake_procs({10: 1.0, 20: 2.0})
        procs[20].suspend.side_effect = psutil.AccessDenied(20)
        agent = ProcessManagerAgent()
        with patch("psutil.Process", side_effect=factory):
            done = agent.resuspend_processes(PREV + [{"pid": 30, "create_time": 3.0}])
        assert done == [PREV[0]]


# ── Linux comm kırpması ────────────────────────────────────────────────────────

LONG = "google-chrome-stable"  # 20 karakter
TRUNC = LONG[:15]  # "google-chrome-s"


def _iter_proc(pid, name, exe="", cmdline=None):
    proc = MagicMock()
    proc.pid = pid
    proc.info = {"name": name, "exe": exe, "status": "running", "cmdline": cmdline}
    return proc


class TestLinuxCommTruncation:
    def _find(self, procs, name, linux=True):
        with (
            patch("psutil.process_iter", return_value=procs),
            patch("src.agents.process_manager._is_linux", return_value=linux),
        ):
            return [p.pid for p in ProcessManagerAgent().find_processes(name)]

    def test_truncated_name_with_exe_match(self):
        procs = [_iter_proc(1, TRUNC, "/opt/google/chrome/Google-Chrome-Stable")]
        assert self._find(procs, LONG) == [1]

    def test_truncated_name_with_cmdline_match_when_exe_unreadable(self):
        procs = [_iter_proc(2, TRUNC, None, ["/usr/bin/google-chrome-stable", "--flag"])]
        assert self._find(procs, LONG) == [2]

    def test_exe_suffix_stripped_and_case_insensitive(self):
        procs = [_iter_proc(3, TRUNC, None, ["C:\\x\\Google-Chrome-Stable.exe"])]
        assert self._find(procs, LONG + ".exe") == [3]

    def test_truncated_name_alone_is_not_enough(self):
        procs = [
            _iter_proc(4, TRUNC, None, None),
            _iter_proc(5, TRUNC, "/usr/bin/google-chrome-s", ["/usr/bin/google-chrome-s"]),
            _iter_proc(6, TRUNC, None, ["/usr/bin/other"]),
            _iter_proc(7, TRUNC, None, []),
        ]
        assert self._find(procs, LONG) == []

    def test_not_applied_off_linux(self):
        procs = [_iter_proc(8, TRUNC, None, ["/usr/bin/google-chrome-stable"])]
        assert self._find(procs, LONG, linux=False) == []

    def test_not_applied_for_short_targets(self):
        # 15 karakter ve altı hedefte kırpma yok: yalnızca tam ad eşleşir
        procs = [_iter_proc(9, "firefox", None, ["/usr/bin/firefox-esr"])]
        assert self._find(procs, "firefox-esr") == []

    def test_different_truncated_name_does_not_match(self):
        procs = [_iter_proc(10, "google-chrome-x", None, ["/usr/bin/google-chrome-stable"])]
        assert self._find(procs, LONG) == []
