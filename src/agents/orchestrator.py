"""Orchestrator Agent — Komuta merkezi, tüm geçiş sürecini yönetir."""

from __future__ import annotations

import logging
from typing import Any, Callable

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from src.agents.base_agent import BaseAgent
from src.agents.browser_agent import BrowserAgent
from src.agents.environment_agent import EnvironmentAgent
from src.agents.layout_agent import LayoutAgent
from src.agents.process_manager import ProcessManagerAgent
from src.core.event_bus import AgentName, StatusReport, SwitchEvent
from src.core.logger import logger
from src.core.snapshot import take_snapshot
from src.core.state import get_state, update_state

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
        # Kritik kabul edilen (çökerse geçiş iptal olan) agent'lar
        self._critical_agents = {AgentName.PROCESS_MANAGER}

    @property
    def name(self) -> str:
        return AgentName.ORCHESTRATOR

    def execute(self, event: SwitchEvent, on_progress: Callable[[str, float], None] | None = None) -> StatusReport:
        """Tüm agent pipeline'ını çalıştırır."""
        logger.info("Mod geçişi başlatıldı: %s (Dry-run: %s)", event.mode_name, event.dry_run)
        
        state = get_state()
        all_reports: list[StatusReport] = []
        snapshot_path = None

        if on_progress is not None:
            on_progress("Snapshot alınıyor...", 0)

        # 1. Snapshot — dry-run'da atla
        if not event.dry_run:
            try:
                snapshot_path = take_snapshot(
                    mode_name=event.previous_mode or "unknown"
                )
                logger.debug("Snapshot alındı: %s", snapshot_path)
            except Exception as e:
                logger.warning("Snapshot alınamadı: %s", e)

        # 2. Agent pipeline
        completed_agents: list[tuple[BaseAgent, StatusReport]] = []
        failed = False
        total_agents = len(self._agents)

        if event.dry_run:
            reports = self._run_dry_run(event, on_progress)
            all_reports.extend(reports)
        else:
            for i, agent in enumerate(self._agents, 1):
                if on_progress is not None:
                    on_progress(f"{agent.name} çalışıyor...", (i / total_agents) * 100)
                
                logger.debug("Agent tetikleniyor: %s", agent.name)
                try:
                    report = agent.execute(event)
                    all_reports.append(report)
                    completed_agents.append((agent, report))

                    if not report.success:
                        logger.error("Agent başarısız: %s — %s", agent.name, report.message)
                        if agent.name in self._critical_agents:
                            failed = True
                            break
                        else:
                            logger.info("Kritik olmayan agent başarısız oldu, devam ediliyor: %s", agent.name)
                            # Kritik değilse partial hata, ama devam et

                except Exception as e:
                    logger.exception("Agent çöktü: %s", agent.name)
                    all_reports.append(StatusReport(
                        agent_name=agent.name,
                        success=False,
                        message=f"Beklenmeyen hata: {e}",
                    ))
                    if agent.name in self._critical_agents:
                        failed = True
                        break

            # 3. Kritik hata → rollback
            if failed:
                logger.error("Kritik agent hatası. Rollback başlatılıyor.")
                if on_progress is not None:
                    on_progress("Kritik hata! Geri alınıyor (Rollback)...", 100)
                self._rollback(completed_agents, event)
                return StatusReport(
                    agent_name=self.name,
                    success=False,
                    message=f"Geçiş başarısız — rollback yapıldı.",
                    details={"reports": [r.message for r in all_reports]},
                )

            # 4. State güncelle
            if on_progress is not None:
                on_progress("Durum kaydediliyor...", 100)
            
            suspended_pids = self._collect_suspended_pids(all_reports)
            update_state(
                current_mode=event.mode_name,
                previous_mode=event.previous_mode,
                last_snapshot=str(snapshot_path) if snapshot_path else None,
                suspended_pids=suspended_pids,
            )
            logger.info("Geçiş başarıyla tamamlandı.")

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

    def _run_dry_run(self, event: SwitchEvent, on_progress: Callable[[str, float], None] | None = None) -> list[StatusReport]:
        """Dry-run: agent'ları dry_run=True ile çalıştırır."""
        reports = []
        total_agents = len(self._agents)
        for i, agent in enumerate(self._agents, 1):
            if on_progress is not None:
                on_progress(f"[SİMÜLASYON] {agent.name} çalışıyor...", (i / total_agents) * 100)
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
