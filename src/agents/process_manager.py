"""Process Manager Agent — Süreç dondurma, devam ettirme ve başlatma."""

from __future__ import annotations

from src.agents.base_agent import BaseAgent
from src.core.event_bus import AgentName, StatusReport, SwitchEvent


class ProcessManagerAgent(BaseAgent):
    """Sistem süreçlerini yöneten agent.

    Hedef moda gerekmeyen süreçleri dondurur (SIGSTOP),
    gerekli süreçleri başlatır veya devam ettirir (SIGCONT).
    """

    @property
    def name(self) -> str:
        return AgentName.PROCESS_MANAGER

    def execute(self, event: SwitchEvent) -> StatusReport:
        """TODO (Faz 1): psutil ile süreç yönetimi."""
        return StatusReport(
            agent_name=self.name,
            success=True,
            message="Process Manager: Hazır (henüz implement edilmedi).",
        )
