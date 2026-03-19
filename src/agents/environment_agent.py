"""Environment Agent — Bildirimler, ses ve müzik yönetimi."""

from __future__ import annotations

from src.agents.base_agent import BaseAgent
from src.core.event_bus import AgentName, StatusReport, SwitchEvent


class EnvironmentAgent(BaseAgent):
    """Çevre yöneticisi agent.

    Bildirim sessizleştirme, ses seviyesi ayarı ve
    Spotify/müzik kontrolünü sağlar.
    """

    @property
    def name(self) -> str:
        return AgentName.ENVIRONMENT

    def execute(self, event: SwitchEvent) -> StatusReport:
        """TODO (Faz 2): plyer + OS API ile çevre yönetimi."""
        return StatusReport(
            agent_name=self.name,
            success=True,
            message="Environment Agent: Hazır (henüz implement edilmedi).",
        )
