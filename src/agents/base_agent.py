"""BaseAgent — Tüm agent'ların implement etmesi gereken soyut temel sınıf."""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.core.event_bus import StatusReport, SwitchEvent


class BaseAgent(ABC):
    """Agent arayüzü.

    Her agent bu sınıftan türer ve `execute` metodunu implement eder.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Agent'ın benzersiz adı (örn: 'process_manager')."""
        ...

    @abstractmethod
    def execute(self, event: SwitchEvent) -> StatusReport:
        """Mod geçişi olayını işler.

        Args:
            event: Orchestrator'dan gelen SwitchEvent.

        Returns:
            İşlem sonucunu içeren StatusReport.
        """
        ...

    def rollback(self, event: SwitchEvent) -> StatusReport:
        """Geçişi geri alır (opsiyonel — varsayılan: desteklenmiyor)."""
        return StatusReport(
            agent_name=self.name,
            success=False,
            message="Rollback bu agent tarafından henüz desteklenmiyor.",
        )

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name!r}>"
