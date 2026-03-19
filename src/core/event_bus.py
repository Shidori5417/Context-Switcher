"""Event Bus — Agent'lar arası olay tabanlı iletişim sistemi."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable


class AgentName(str, Enum):
    """Sistemdeki tüm agent isimleri."""

    ORCHESTRATOR = "orchestrator"
    PROCESS_MANAGER = "process_manager"
    LAYOUT = "layout"
    BROWSER = "browser"
    ENVIRONMENT = "environment"


@dataclass
class SwitchEvent:
    """Mod geçişi sırasında agent'lara iletilen olay nesnesi."""

    mode_name: str
    config: dict[str, Any]
    previous_mode: str | None = None
    dry_run: bool = False
    timestamp: datetime = field(default_factory=datetime.now)

    def __repr__(self) -> str:
        return (
            f"SwitchEvent(mode={self.mode_name!r}, "
            f"prev={self.previous_mode!r}, "
            f"dry_run={self.dry_run})"
        )


@dataclass
class StatusReport:
    """Her agent'ın geçiş sonucunu raporladığı veri yapısı."""

    agent_name: str
    success: bool
    message: str
    details: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


# Event handler tipi: SwitchEvent alır, StatusReport döner
EventHandler = Callable[[SwitchEvent], StatusReport]


class EventBus:
    """Basit publish/subscribe olay yöneticisi.

    Agent'lar belirli olay tiplerine abone olur, Orchestrator olayları yayınlar.
    """

    def __init__(self) -> None:
        self._subscribers: dict[str, list[EventHandler]] = {}

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        """Bir olay tipine handler ekler."""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)

    def publish(self, event_type: str, event: SwitchEvent) -> list[StatusReport]:
        """Olayı tüm abonelere iletir, StatusReport listesi döner."""
        reports: list[StatusReport] = []
        for handler in self._subscribers.get(event_type, []):
            report = handler(event)
            reports.append(report)
        return reports

    def clear(self) -> None:
        """Tüm abonelikleri temizler."""
        self._subscribers.clear()

    @property
    def subscriber_count(self) -> int:
        """Toplam abone sayısı."""
        return sum(len(handlers) for handlers in self._subscribers.values())
