"""Orchestrator Agent — Komuta merkezi, tüm geçiş sürecini yönetir."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from rich.console import Console

from src.agents.base_agent import BaseAgent
from src.agents.browser_agent import BrowserAgent
from src.agents.environment_agent import EnvironmentAgent
from src.agents.layout_agent import LayoutAgent
from src.agents.process_manager import ProcessManagerAgent
from src.core.event_bus import AgentName, StatusReport, SwitchEvent
from src.core.logger import logger
from src.core.procs import ProcEntry, merge_entries, normalize_entries
from src.core.snapshot import take_snapshot, update_snapshot_suspended
from src.core.state import get_state, save_state, update_state

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
        # Bu geçiş denemesinde uyandırılan önceki mod süreçleri (abort'ta yeniden dondurulur)
        self._resumed_this_switch: list[ProcEntry] = []

    @property
    def name(self) -> str:
        return AgentName.ORCHESTRATOR

    def execute(
        self, event: SwitchEvent, on_progress: Callable[[str, float], None] | None = None
    ) -> StatusReport:
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
                snapshot_path = take_snapshot(mode_name=event.previous_mode or "unknown")
                logger.debug("Snapshot alındı: %s", snapshot_path)
            except Exception as e:
                logger.warning("Snapshot alınamadı: %s", e)

        # 1b. Önceki modun dondurduğu süreçleri uyandır (hedef mod gerekirse yeniden dondurur)
        retained: list[ProcEntry] = []
        self._resumed_this_switch = []
        if not event.dry_run:
            retained = self._resume_previous(state)

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
                            logger.info(
                                "Kritik olmayan agent başarısız oldu, devam ediliyor: %s",
                                agent.name,
                            )
                            # Kritik değilse partial hata, ama devam et

                except Exception as e:
                    logger.exception("Agent çöktü: %s", agent.name)
                    all_reports.append(
                        StatusReport(
                            agent_name=agent.name,
                            success=False,
                            message=f"Beklenmeyen hata: {e}",
                        )
                    )
                    if agent.name in self._critical_agents:
                        failed = True
                        break

            # 3. Kritik hata → rollback
            if failed:
                logger.error("Kritik agent hatası. Rollback başlatılıyor.")
                if on_progress is not None:
                    on_progress("Kritik hata! Geri alınıyor (Rollback)...", 100)
                self._rollback(completed_agents, event)
                self._restore_previous_mode(state)
                return StatusReport(
                    agent_name=self.name,
                    success=False,
                    message="Geçiş başarısız — rollback yapıldı.",
                    details={"reports": [r.message for r in all_reports]},
                )

            # 4. State güncelle
            if on_progress is not None:
                on_progress("Durum kaydediliyor...", 100)

            # Uyandırılamayanlar (yetki hatası) izlenmeye devam eder
            suspended = merge_entries(self._collect_suspended_procs(all_reports), retained)
            if snapshot_path:
                try:
                    update_snapshot_suspended(snapshot_path, suspended)
                except Exception as e:
                    logger.warning("Snapshot güncellenemedi: %s", e)
            update_state(
                current_mode=event.mode_name,
                previous_mode=event.previous_mode,
                last_snapshot=str(snapshot_path) if snapshot_path else None,
                suspended_pids=suspended,
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
        reports = []
        for agent in self._agents:
            try:
                report = agent.rollback(event)
                reports.append(report)
            except Exception as e:
                reports.append(
                    StatusReport(
                        agent_name=agent.name,
                        success=False,
                        message=f"Rollback hatası: {e}",
                    )
                )
        return StatusReport(
            agent_name=self.name,
            success=all(r.success for r in reports),
            message="Rollback tamamlandı.",
            details={"reports": [r.message for r in reports]},
        )

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _run_dry_run(
        self, event: SwitchEvent, on_progress: Callable[[str, float], None] | None = None
    ) -> list[StatusReport]:
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
                reports.append(
                    StatusReport(
                        agent_name=agent.name,
                        success=False,
                        message=f"Simülasyon hatası: {e}",
                    )
                )
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

    def _resume_previous(self, state: Any) -> list[ProcEntry]:
        """Önceki geçişte dondurulmuş süreçleri uyandırır.

        Yeni mod aynı süreci de dondurmak istiyorsa ProcessManager onu tekrar
        dondurur. Döner: uyandırılamayan (yetki hatası) ve izlenmesi gereken kayıtlar.
        """
        self._resumed_this_switch = []
        previous = state.suspended_pids if isinstance(state.suspended_pids, list) else []
        entries = normalize_entries(previous)
        if not entries:
            return []

        pm = next((a for a in self._agents if isinstance(a, ProcessManagerAgent)), None)
        if pm is None:
            return entries
        try:
            report = pm.resume_processes(entries)
        except Exception as e:
            logger.warning("Önceki modun süreçleri uyandırılamadı: %s", e)
            return entries

        logger.info("Önceki modun %d süreci uyandırıldı.", len(report.resumed))
        failed = {a.pid for a in report.errors if a.action == "error"}
        resumed = {a.pid for a in report.resumed}
        self._resumed_this_switch = [e for e in entries if e["pid"] in resumed]
        return [e for e in entries if e["pid"] in failed]

    def _restore_previous_mode(self, previous_state: Any) -> None:
        """Geçiş abort olduysa, bu denemede uyandırılan önceki mod süreçlerini tekrar
        dondurur ve önceki state kaydını geri yazar."""
        resumed = self._resumed_this_switch
        self._resumed_this_switch = []
        if not resumed:
            return
        pm = next((a for a in self._agents if isinstance(a, ProcessManagerAgent)), None)
        if pm is not None:
            try:
                restored = pm.resuspend_processes(resumed)
                logger.info("Abort: önceki modun %d süreci yeniden donduruldu.", len(restored))
            except Exception as e:
                logger.error("Önceki modun süreçleri yeniden dondurulamadı: %s", e)
        try:
            save_state(previous_state)
        except Exception as e:
            logger.error("Önceki state geri yazılamadı: %s", e)

    def _collect_suspended_procs(self, reports: list[StatusReport]) -> list[ProcEntry]:
        """Tüm raporlardan suspend edilen süreçleri ({pid, create_time}) toplar."""
        groups: list[list[Any]] = []
        for report in reports:
            procs = report.details.get("suspended_procs")
            # suspended_procs yoksa eski formatlı (düz PID) rapora düş
            groups.append(procs if procs else report.details.get("suspended_pids", []))
        return merge_entries(*groups)
