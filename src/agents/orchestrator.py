"""Orchestrator Agent — Komuta merkezi, tüm geçiş sürecini yönetir."""

from __future__ import annotations

from src.agents.base_agent import BaseAgent
from src.core.event_bus import AgentName, StatusReport, SwitchEvent


class OrchestratorAgent(BaseAgent):
    """Mod geçişini koordine eden ana agent.

    Diğer agent'ları sırayla veya paralel tetikler,
    hata durumunda rollback koordinasyonunu yapar.
    """

    @property
    def name(self) -> str:
        return AgentName.ORCHESTRATOR

    def execute(self, event: SwitchEvent) -> StatusReport:
        """TODO (Faz 1): Agent tetikleme sırasını çalıştır."""
        return StatusReport(
            agent_name=self.name,
            success=True,
            message=f"Orchestrator: '{event.mode_name}' moduna geçiş planlandı.",
            details={"dry_run": event.dry_run},
        )
