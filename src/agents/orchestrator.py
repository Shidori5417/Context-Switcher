"""Orchestrator Agent — Komuta merkezi, tüm geçiş sürecini yönetir."""

from __future__ import annotations

import logging
from typing import Any

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from src.agents.base_agent import BaseAgent
from src.agents.browser_agent import BrowserAgent
from src.agents.environment_agent import EnvironmentAgent
from src.agents.layout_agent import LayoutAgent
from src.agents.process_manager import ProcessManagerAgent
from src.core.event_bus import AgentName, StatusReport, SwitchEvent
from src.core.snapshot import take_snapshot
from src.core.state import get_state, update_state

logger = logging.getLogger(__name__)
console = Console()


class OrchestratorAgent(BaseAgent):
    """Mod geçişini koordine eden ana agent.

    Pipeline sırası:
      1. Snapshot al
      2. ProcessManager (suspend sonra start)
      3. LayoutAgent
      4. BrowserAgent
      5. EnvironmentAgent
      6. State güncelle
    """

    def __init__(self, extra_protected: list[str] | None = None) -> None:
        self._agents: list[BaseAgent] = [
            ProcessManagerAgent(extra_protected=extra_protected),
            LayoutAgent(),
            BrowserAgent(),
            EnvironmentAgent(),
        ]

    @property
    def name(self) -> str:
        return AgentName.ORCHESTRATOR

    def execute(self, event: SwitchEvent) -> StatusReport:
        """Tüm agent pipeline'ını çalıştırır."""
        state = get_state()
        all_reports: list[StatusReport] = []
        snapshot_path = None

        # 1. Snapshot — dry-run'da atla
        if not event.dry_run:
            try:
                snapshot_path = take_snapshot(
                    mode_name=event.previous_mode or "unknown"
                )
            except Exception as e:
                logger.warning("Snapshot alınamadı: %s", e)

        # 2. Agent pipeline
        completed_agents: list[tuple[BaseAgent, StatusReport]] = []
        failed = False

        if event.dry_run:
            reports = self._run_dry_run(event)
            all_reports.extend(reports)
        else:
            for agent in self._agents:
                try:
                    report = agent.execute(event)
                    all_reports.append(report)
                    completed_agents.append((agent, report))

                    if not report.success:
                        logger.error("Agent başarısız: %s — %s", agent.name, report.message)
                        failed = True
                        break
                except Exception as e:
                    logger.exception("Agent çöktü: %s", agent.name)
                    all_reports.append(StatusReport(
                        agent_name=agent.name,
                        success=False,
                        message=f"Beklenmeyen hata: {e}",
                    ))
                    failed = True
                    break

            # 3. Hata → rollback
            if failed:
                self._rollback(completed_agents, event)
                return StatusReport(
                    agent_name=self.name,
                    success=False,
                    message=f"Geçiş başarısız — rollback yapıldı.",
                    details={"reports": [r.message for r in all_reports]},
                )

            # 4. Suspended PID'leri topla ve state güncelle
            suspended_pids = self._collect_suspended_pids(all_reports)
            if not event.dry_run:
                update_state(
                    current_mode=event.mode_name,
                    previous_mode=event.previous_mode,
                    last_snapshot=str(snapshot_path) if snapshot_path else None,
                    suspended_pids=suspended_pids,
                )

        return StatusReport(
            agent_name=self.name,
            success=True,
            message=f"'{event.mode_name}' moduna geçiş tamamlandı.",
            details={
                "reports": [r.message for r in all_reports],
                "dry_run": event.dry_run,
                "snapshot": str(snapshot_path) if snapshot_path else None,
            },
        )

    def rollback(self, event: SwitchEvent) -> StatusReport:
        """Tüm agent'ların rollback metodunu çağırır."""
        state = get_state()
        reports = []
        for agent in self._agents:
            try:
                report = agent.rollback(event)
                reports.append(report)
            except Exception as e:
                reports.append(StatusReport(
                    agent_name=agent.name,
                    success=False,
                    message=f"Rollback hatası: {e}",
                ))
        return StatusReport(
            agent_name=self.name,
            success=all(r.success for r in reports),
            message="Rollback tamamlandı.",
            details={"reports": [r.message for r in reports]},
        )

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _run_dry_run(self, event: SwitchEvent) -> list[StatusReport]:
        """Dry-run: agent'ları dry_run=True ile çalıştırır."""
        reports = []
        for agent in self._agents:
            try:
                report = agent.execute(event)
                reports.append(report)
            except Exception as e:
                reports.append(StatusReport(
                    agent_name=agent.name,
                    success=False,
                    message=f"Simülasyon hatası: {e}",
                ))
        return reports

    def _rollback(
        self,
        completed: list[tuple[BaseAgent, StatusReport]],
        event: SwitchEvent,
    ) -> None:
        """Tamamlanan agent'ları ters sırayla rollback yapar."""
        for agent, _report in reversed(completed):
            try:
                agent.rollback(event)
            except Exception as e:
                logger.error("Rollback hatası (%s): %s", agent.name, e)

    def _collect_suspended_pids(self, reports: list[StatusReport]) -> list[int]:
        """Tüm raporlardan suspend edilen PID'leri toplar."""
        pids: list[int] = []
        for report in reports:
            pids.extend(report.details.get("suspended_pids", []))
        return pids
