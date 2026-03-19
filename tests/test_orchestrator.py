"""Orchestrator Agent entegrasyon testleri."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.agents.orchestrator import OrchestratorAgent
from src.core.event_bus import StatusReport, SwitchEvent


def _make_event(dry_run: bool = False) -> SwitchEvent:
    return SwitchEvent(
        mode_name="dev",
        config={"name": "Dev", "processes": {"suspend": ["discord"]}},
        previous_mode=None,
        dry_run=dry_run,
    )


def _ok_report(agent_name: str) -> StatusReport:
    return StatusReport(agent_name=agent_name, success=True, message="OK",
                        details={"suspended_pids": []})


def _fail_report(agent_name: str) -> StatusReport:
    return StatusReport(agent_name=agent_name, success=False, message="FAIL")


class TestOrchestratorPipeline:
    def test_success_pipeline(self):
        orch = OrchestratorAgent()
        event = _make_event()

        # Tüm agent'ları başarılı döndürecek şekilde mock'la
        for agent in orch._agents:
            agent.execute = MagicMock(return_value=_ok_report(agent.name))

        with (
            patch("src.agents.orchestrator.take_snapshot", return_value=None),
            patch("src.agents.orchestrator.get_state") as mock_state,
            patch("src.agents.orchestrator.update_state"),
        ):
            mock_state.return_value = MagicMock(current_mode=None)
            result = orch.execute(event)

        assert result.success
        assert "tamamlandı" in result.message

    def test_dry_run_no_snapshot(self):
        orch = OrchestratorAgent()
        event = _make_event(dry_run=True)

        for agent in orch._agents:
            agent.execute = MagicMock(return_value=_ok_report(agent.name))

        with (
            patch("src.agents.orchestrator.take_snapshot") as mock_snap,
            patch("src.agents.orchestrator.get_state") as mock_state,
            patch("src.agents.orchestrator.update_state"),
        ):
            mock_state.return_value = MagicMock(current_mode=None)
            result = orch.execute(event)

        # dry_run modunda snapshot alınmamalı
        mock_snap.assert_not_called()
        assert result.success

    def test_failure_triggers_rollback(self):
        orch = OrchestratorAgent()
        event = _make_event()

        # İlk agent başarılı, ikincisi başarısız
        agents = orch._agents
        agents[0].execute = MagicMock(return_value=_ok_report(agents[0].name))
        agents[1].execute = MagicMock(return_value=_fail_report(agents[1].name))
        agents[0].rollback = MagicMock(return_value=_ok_report(agents[0].name))

        with (
            patch("src.agents.orchestrator.take_snapshot", return_value=None),
            patch("src.agents.orchestrator.get_state") as mock_state,
            patch("src.agents.orchestrator.update_state"),
        ):
            mock_state.return_value = MagicMock(current_mode=None)
            result = orch.execute(event)

        assert not result.success
        agents[0].rollback.assert_called_once()

    def test_agent_exception_handled(self):
        orch = OrchestratorAgent()
        event = _make_event()

        orch._agents[0].execute = MagicMock(side_effect=RuntimeError("Crashed"))

        with (
            patch("src.agents.orchestrator.take_snapshot", return_value=None),
            patch("src.agents.orchestrator.get_state") as mock_state,
            patch("src.agents.orchestrator.update_state"),
        ):
            mock_state.return_value = MagicMock(current_mode=None)
            result = orch.execute(event)

        assert not result.success


class TestOrchestratorRollback:
    def test_rollback_calls_all_agents(self):
        orch = OrchestratorAgent()
        event = _make_event()

        for agent in orch._agents:
            agent.rollback = MagicMock(return_value=_ok_report(agent.name))

        with patch("src.agents.orchestrator.get_state") as mock_state:
            mock_state.return_value = MagicMock()
            result = orch.rollback(event)

        assert result.success
        for agent in orch._agents:
            agent.rollback.assert_called_once()
