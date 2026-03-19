"""Layout Agent — Pencere düzeni ve sanal masaüstü yönetimi."""

from __future__ import annotations

from src.agents.base_agent import BaseAgent
from src.core.event_bus import AgentName, StatusReport, SwitchEvent


class LayoutAgent(BaseAgent):
    """Masaüstü düzenleyici agent.

    Uygulama pencerelerinin boyut, konum ve workspace'ini ayarlar.
    """

    @property
    def name(self) -> str:
        return AgentName.LAYOUT

    def execute(self, event: SwitchEvent) -> StatusReport:
        """TODO (Faz 2): wmctrl/xdotool/pywin32 ile pencere yönetimi."""
        return StatusReport(
            agent_name=self.name,
            success=True,
            message="Layout Agent: Hazır (henüz implement edilmedi).",
        )
