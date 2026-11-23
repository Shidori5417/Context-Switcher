"""Process Manager Agent — Süreç dondurma, devam ettirme ve başlatma."""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from dataclasses import dataclass, field
from typing import Any

import psutil

from src.agents.base_agent import BaseAgent
from src.core.event_bus import AgentName, StatusReport, SwitchEvent
from src.core.procs import ProcEntry, make_entry, matches_entry, merge_entries, normalize_entries

logger = logging.getLogger(__name__)

# Sistem süreçleri — asla dokunulmaz
_SYSTEM_PROCESS_NAMES = frozenset(
    {
        "system",
        "smss.exe",
        "csrss.exe",
        "wininit.exe",
        "services.exe",
        "lsass.exe",
        "svchost.exe",
        "winlogon.exe",
        "explorer.exe",
        "systemd",
        "init",
        "kthreadd",
        "ksoftirqd",
        "python",
        "python3",
        "python.exe",  # Kendimizi dondurma
    }
)


def _strip_exe(name: str) -> str:
    return name[:-4] if name.endswith(".exe") else name


def _basename(path: str) -> str:
    """Hem Windows (\\) hem POSIX (/) ayraçlarıyla dosya adını döner."""
    return path.replace("\\", "/").rsplit("/", 1)[-1]


# Linux'ta /proc/<pid>/comm (psutil name()) en fazla 15 karakterdir
_LINUX_COMM_MAX = 15


def _is_linux() -> bool:
    return sys.platform.startswith("linux")


def _cmdline0_basename(cmdline: Any) -> str:
    """cmdline[0]'ın basename'i (küçük harf, .exe'siz); yoksa boş string."""
    if isinstance(cmdline, (list, tuple)) and cmdline and isinstance(cmdline[0], str):
        return _strip_exe(_basename(cmdline[0]).lower())
    return ""


@dataclass
class ProcessAction:
    """Bir süreç üzerinde yapılan işlemin kaydı."""

    pid: int
    name: str
    action: str  # "suspended" | "resumed" | "started" | "skipped"
    memory_mb: float = 0.0
    cpu_percent: float = 0.0
    error: str | None = None
    create_time: float | None = None


@dataclass
class ResourceReport:
    """Suspend işleminden elde edilen kaynak tasarrufu raporu."""

    suspended: list[ProcessAction] = field(default_factory=list)
    resumed: list[ProcessAction] = field(default_factory=list)
    started: list[ProcessAction] = field(default_factory=list)
    skipped: list[ProcessAction] = field(default_factory=list)
    errors: list[ProcessAction] = field(default_factory=list)

    @property
    def saved_memory_mb(self) -> float:
        return sum(a.memory_mb for a in self.suspended)

    @property
    def summary(self) -> str:
        parts = []
        if self.suspended:
            parts.append(
                f"{len(self.suspended)} donduruldu ({self.saved_memory_mb:.0f} MB kurtarıldı)"
            )
        if self.started:
            parts.append(f"{len(self.started)} başlatıldı")
        if self.errors:
            parts.append(f"{len(self.errors)} hata")
        return ", ".join(parts) if parts else "İşlem yapılmadı"


class ProcessManagerAgent(BaseAgent):
    """Sistem süreçlerini yöneten agent.

    Hedef moda gerekmeyen süreçleri dondurur (suspend),
    gerekli süreçleri başlatır veya devam ettirir (resume).
    Cross-platform: psutil Windows'ta NtSuspendProcess,
    Linux/macOS'ta SIGSTOP kullanır.
    """

    def __init__(self, extra_protected: list[str] | None = None) -> None:
        self._protected = _SYSTEM_PROCESS_NAMES | frozenset(
            n.lower() for n in (extra_protected or [])
        )
        # Dondurulan süreçler, ANINDA kaydedilir (döngü ortasında hata olsa bile kaybolmaz)
        self._last_suspended_procs: list[ProcEntry] = []

    @property
    def name(self) -> str:
        return AgentName.PROCESS_MANAGER

    # ── Public API ─────────────────────────────────────────────────────────────

    def find_processes(self, app_name: str) -> list[psutil.Process]:
        """Uygulama adına göre çalışan süreçleri bulur.

        Süreç adı veya executable dosya adı (basename) ile TAM eşleşme arar;
        büyük/küçük harf duyarsızdır ve `.exe` uzantısı olsa da olmasa da eşleşir.
        (`code` -> `code`, `Code.exe`; ama `t3code` veya `vscode-server` değil.)

        Linux'ta süreç adı (`/proc/<pid>/comm`) 15 karaktere kırpıldığı için, hedef ad
        15 karakterden uzunsa kırpılmış adı taşıyan süreç de, exe basename'i veya
        cmdline[0] basename'i tam hedefle eşleşiyorsa kabul edilir.
        """
        target = _strip_exe(app_name.strip().lower())
        results: list[psutil.Process] = []
        for proc in psutil.process_iter(["pid", "name", "exe", "status", "cmdline"]):
            try:
                proc_name = _strip_exe((proc.info["name"] or "").lower())
                proc_exe = _strip_exe(_basename(proc.info["exe"] or "").lower())
                if target and target in (proc_name, proc_exe):
                    results.append(proc)
                elif (
                    target
                    and len(target) > _LINUX_COMM_MAX
                    and _is_linux()
                    and proc_name == target[:_LINUX_COMM_MAX]
                    and target in (proc_exe, _cmdline0_basename(proc.info.get("cmdline")))
                ):
                    results.append(proc)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return results

    def suspend_processes(
        self, app_names: list[str], dry_run: bool = False
    ) -> tuple[list[int], ResourceReport]:
        """Listedeki isimlere uyan süreçleri dondurur.

        Returns:
            (suspended_pids, report) tuple.
        """
        report = ResourceReport()
        suspended_pids: list[int] = []
        if not dry_run:
            self._last_suspended_procs = []

        for app_name in app_names:
            procs = self.find_processes(app_name)
            if not procs:
                logger.debug("Süreç bulunamadı: %s", app_name)
                report.skipped.append(ProcessAction(pid=0, name=app_name, action="skipped"))
                continue

            for proc in procs:
                action = self._suspend_one(proc, dry_run)
                if action.action == "suspended":
                    suspended_pids.append(action.pid)
                    if not dry_run:
                        self._record_suspended(action)
                    report.suspended.append(action)
                elif action.error:
                    report.errors.append(action)
                else:
                    report.skipped.append(action)

        return suspended_pids, report

    def resume_processes(
        self, pids: list[int] | list[ProcEntry], dry_run: bool = False
    ) -> ResourceReport:
        """Süreçleri devam ettirir.

        Liste düz PID'lerden (eski format) veya {pid, create_time} kayıtlarından
        oluşabilir. create_time kayıtlıysa ve canlı sürecinkiyle uyuşmuyorsa
        (PID başka bir sürece geçmiş) süreç atlanır.
        """
        report = ResourceReport()
        for entry in normalize_entries(pids):
            action = self._resume_one(entry["pid"], dry_run, entry.get("create_time"))
            if action.action == "resumed":
                report.resumed.append(action)
            elif action.error:
                report.errors.append(action)
        return report

    def resuspend_processes(self, entries: list[ProcEntry]) -> list[ProcEntry]:
        """Bu geçiş denemesinde uyandırılmış süreçleri tekrar dondurur (abort durumunda).

        create_time uyuşmayan (PID yeniden kullanılmış) ya da artık var olmayan
        süreçlere dokunulmaz. Döner: gerçekten yeniden dondurulan kayıtlar.
        """
        restored: list[ProcEntry] = []
        for entry in normalize_entries(entries):
            try:
                proc = psutil.Process(entry["pid"])
                if not matches_entry(proc, entry):
                    continue
                proc.suspend()
                restored.append(entry)
            except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                logger.warning("PID %s yeniden dondurulamadı: %s", entry["pid"], e)
        return restored

    def start_processes(self, commands: list[str], dry_run: bool = False) -> ResourceReport:
        """Komut listesindeki uygulamaları başlatır."""
        report = ResourceReport()
        for cmd in commands:
            action = self._start_one(cmd, dry_run)
            if action.action == "started":
                report.started.append(action)
            elif action.error:
                report.errors.append(action)
        return report

    # ── BaseAgent Interface ────────────────────────────────────────────────────

    def execute(self, event: SwitchEvent) -> StatusReport:
        """Mod geçişinde süreç yönetimini çalıştırır."""
        processes_cfg: dict[str, Any] = event.config.get("processes", {})
        suspend_list: list[str] = processes_cfg.get("suspend", [])
        start_list: list[str] = processes_cfg.get("start", [])

        all_suspended_pids: list[int] = []
        combined_report = ResourceReport()
        self._last_suspended_procs = []

        try:
            # 1. Suspend
            if suspend_list:
                pids, report = self.suspend_processes(suspend_list, dry_run=event.dry_run)
                all_suspended_pids.extend(pids)
                combined_report.suspended.extend(report.suspended)
                combined_report.skipped.extend(report.skipped)
                combined_report.errors.extend(report.errors)

            # 2. Start
            if start_list:
                report = self.start_processes(start_list, dry_run=event.dry_run)
                combined_report.started.extend(report.started)
                combined_report.errors.extend(report.errors)
        except Exception as e:
            # Döngü ortasında hata: o ana kadar dondurulanlar _last_suspended_procs'ta
            # kayıtlı; orchestrator rollback'inde uyandırılabilmeleri için raporla.
            logger.exception("Süreç yönetimi sırasında beklenmeyen hata")
            return StatusReport(
                agent_name=self.name,
                success=False,
                message=f"Süreç yönetimi hatası: {e}",
                details={
                    "suspended_pids": [p["pid"] for p in self._last_suspended_procs],
                    "suspended_procs": list(self._last_suspended_procs),
                },
            )

        success = len(combined_report.errors) == 0
        return StatusReport(
            agent_name=self.name,
            success=success,
            message=combined_report.summary,
            details={
                "suspended_pids": all_suspended_pids,
                "suspended_procs": (
                    []
                    if event.dry_run
                    else [
                        {"pid": a.pid, "create_time": a.create_time}
                        for a in combined_report.suspended
                    ]
                ),
                "suspended": [a.name for a in combined_report.suspended],
                "started": [a.name for a in combined_report.started],
                "skipped": [a.name for a in combined_report.skipped],
                "errors": [a.error for a in combined_report.errors if a.error],
                "saved_memory_mb": combined_report.saved_memory_mb,
            },
        )

    def rollback(self, event: SwitchEvent) -> StatusReport:
        """Geçişi geri alır: state.json ve geçici bellekten PID'leri okur."""
        from src.core.state import get_state

        state = get_state()

        entries = merge_entries(self._last_suspended_procs, state.suspended_pids)

        report = self.resume_processes(entries)
        self._last_suspended_procs = []

        return StatusReport(
            agent_name=self.name,
            success=True,
            message=f"Rollback: {len(report.resumed)} süreç uyandırıldı.",
            details={"resumed_pids": [a.pid for a in report.resumed]},
        )

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _record_suspended(self, action: ProcessAction) -> None:
        """Dondurulan süreci hemen kaydeder (sonraki bir hata kaydı kaybettirmesin)."""
        self._last_suspended_procs.append({"pid": action.pid, "create_time": action.create_time})

    def _is_protected(self, proc: psutil.Process) -> bool:
        try:
            name = (proc.name() or "").lower()
            return proc.pid < 100 or name in self._protected
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return True  # Erişilemeyen → güvenli tarafta kal

    def _get_resource_info(self, proc: psutil.Process) -> tuple[float, float]:
        try:
            mem = proc.memory_info().rss / 1024 / 1024
            cpu = proc.cpu_percent(interval=0)
            return round(mem, 2), round(cpu, 2)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return 0.0, 0.0

    def _suspend_one(self, proc: psutil.Process, dry_run: bool) -> ProcessAction:
        try:
            proc_name = proc.name()
            if self._is_protected(proc):
                return ProcessAction(pid=proc.pid, name=proc_name, action="skipped")

            mem_mb, cpu = self._get_resource_info(proc)

            if not dry_run:
                proc.suspend()

            return ProcessAction(
                pid=proc.pid,
                name=proc_name,
                action="suspended",
                memory_mb=mem_mb,
                cpu_percent=cpu,
                create_time=make_entry(proc)["create_time"],
            )
        except psutil.AccessDenied as e:
            return ProcessAction(
                pid=getattr(proc, "pid", 0),
                name="unknown",
                action="error",
                error=f"Yetki hatası: {e}",
            )
        except psutil.NoSuchProcess:
            return ProcessAction(pid=0, name="unknown", action="skipped")

    def _resume_one(
        self, pid: int, dry_run: bool, create_time: float | None = None
    ) -> ProcessAction:
        try:
            proc = psutil.Process(pid)
            if not matches_entry(proc, {"pid": pid, "create_time": create_time}):
                return ProcessAction(
                    pid=pid,
                    name="?",
                    action="skipped",
                    error=f"PID {pid} başka bir sürece ait (yeniden kullanılmış)",
                )
            name = proc.name()
            if not dry_run:
                proc.resume()
            return ProcessAction(pid=pid, name=name, action="resumed")
        except psutil.NoSuchProcess:
            return ProcessAction(
                pid=pid, name="?", action="skipped", error=f"PID {pid} artık mevcut değil"
            )
        except psutil.AccessDenied as e:
            return ProcessAction(pid=pid, name="?", action="error", error=f"Yetki hatası: {e}")

    def _start_one(self, cmd: str, dry_run: bool) -> ProcessAction:
        exe_name = cmd.split()[0]
        try:
            if not dry_run:
                # Windows özel kontrolleri ve .cmd wrapper'ı için shell=True kullanılabilir
                # ama güvenlik açısından önce direkt çalıştırmayı deniyoruz
                try:
                    subprocess.Popen(
                        cmd.split(),
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        start_new_session=True,
                    )
                except FileNotFoundError:
                    if (
                        os.name == "nt"
                        and not exe_name.endswith(".cmd")
                        and not exe_name.endswith(".exe")
                    ):
                        # 'code' Windows'ta 'code.cmd' dosyasıdır ve shell komutudur.
                        subprocess.Popen(
                            cmd,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            shell=True,
                            start_new_session=True,
                        )
                    else:
                        raise
            return ProcessAction(pid=0, name=exe_name, action="started")
        except FileNotFoundError:
            return ProcessAction(
                pid=0,
                name=cmd,
                action="error",
                error=f"Uygulama veya komut bulunamadı: {exe_name!r}",
            )
        except Exception as e:
            return ProcessAction(pid=0, name=cmd, action="error", error=str(e))
