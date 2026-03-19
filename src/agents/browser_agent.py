"""Browser Agent — Tarayıcı sekmelerini ve profillerini yönetir."""

from __future__ import annotations

from src.agents.base_agent import BaseAgent
from src.core.event_bus import AgentName, StatusReport, SwitchEvent


class BrowserAgent(BaseAgent):
    """Tarayıcı orkestratörü.

    Moda özel sekme gruplarını açar, kapatır ve arşivler.
    Chrome DevTools Protocol (CDP) kullanır.
    """

    @property
    def name(self) -> str:
        return AgentName.BROWSER

    def execute(self, event: SwitchEvent) -> StatusReport:
        """TODO (Faz 2): CDP ile sekme yönetimi."""
        return StatusReport(
            agent_name=self.name,
            success=True,
            message="Browser Agent: Hazır (henüz implement edilmedi).",
        )
