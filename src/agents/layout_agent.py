"""Layout Agent — Pencere düzeni ve masaüstü yönetimi (cross-platform)."""

from __future__ import annotations

import json
import logging
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.agents.base_agent import BaseAgent
from src.core.event_bus import AgentName, StatusReport, SwitchEvent

logger = logging.getLogger(__name__)

LAYOUTS_DIR = Path.home() / ".context-switcher" / "layouts"

# ── Platform Tespiti ────────────────────────────────────────────────────────

IS_WINDOWS = sys.platform == "win32"
IS_LINUX = sys.platform.startswith("linux")
IS_MACOS = sys.platform == "darwin"


@dataclass
class WindowInfo:
    """Bir pencerenin temel bilgileri."""
    handle: Any       # Windows: HWND (int), Linux: window ID (str)
    title: str
    x: int
    y: int
    width: int
    height: int


# ── Windows Backend ─────────────────────────────────────────────────────────

class _WindowsBackend:
    """pywin32 tabanlı Windows pencere yöneticisi."""

    def __init__(self) -> None:
        try:
            import win32con
            import win32gui
            self._win32gui = win32gui
            self._win32con = win32con
            self.available = True
        except ImportError:
            self.available = False
            logger.warning("pywin32 yüklü değil. Layout Agent Windows üzerinde çalışamayacak.")

    def get_screen_size(self) -> tuple[int, int]:
        if not self.available:
            return 1920, 1080
        import win32api
        monitor = win32api.GetMonitorInfo(win32api.MonitorFromPoint((0, 0)))
        work_area = monitor["Work"]
        return work_area[2] - work_area[0], work_area[3] - work_area[1]

    def find_windows(self, app_name: str) -> list[WindowInfo]:
        if not self.available:
            return []

        results: list[WindowInfo] = []
        target = app_name.lower()

        def _enum_callback(hwnd: int, _extra: Any) -> None:
            if not self._win32gui.IsWindowVisible(hwnd):
                return
            title = self._win32gui.GetWindowText(hwnd)
            if not title:
                return
            if target in title.lower():
                try:
                    rect = self._win32gui.GetWindowRect(hwnd)
                    x, y, x2, y2 = rect
                    results.append(WindowInfo(
                        handle=hwnd, title=title,
                        x=x, y=y, width=x2 - x, height=y2 - y,
                    ))
                except Exception:
                    pass

        self._win32gui.EnumWindows(_enum_callback, None)
        return results

    def move_window(self, hwnd: int, x: int, y: int, w: int, h: int) -> bool:
        if not self.available:
            return False
        try:
            self._win32gui.SetWindowPos(
                hwnd,
                self._win32con.HWND_TOP,
                x, y, w, h,
                self._win32con.SWP_SHOWWINDOW,
            )
            return True
        except Exception as e:
            logger.warning("Pencere taşınamadı (hwnd=%s): %s", hwnd, e)
            return False

    def save_layout(self, mode_name: str) -> Path:
        """Mevcut pencere durumunu JSON'a kaydeder."""
        LAYOUTS_DIR.mkdir(parents=True, exist_ok=True)
        layout_path = LAYOUTS_DIR / f"{mode_name}.json"

        windows: list[dict] = []
        if self.available:
            def _cb(hwnd: int, _: Any) -> None:
                if not self._win32gui.IsWindowVisible(hwnd):
                    return
                title = self._win32gui.GetWindowText(hwnd)
                if not title:
                    return
                try:
                    rect = self._win32gui.GetWindowRect(hwnd)
                    x, y, x2, y2 = rect
                    windows.append({"hwnd": hwnd, "title": title,
                                    "x": x, "y": y, "w": x2 - x, "h": y2 - y})
                except Exception:
                    pass
            self._win32gui.EnumWindows(_cb, None)

        layout_path.write_text(json.dumps({"mode": mode_name, "windows": windows},
                                           ensure_ascii=False, indent=2), encoding="utf-8")
        return layout_path


# ── Linux Backend ────────────────────────────────────────────────────────────

class _LinuxBackend:
    """wmctrl + xdotool tabanlı Linux pencere yöneticisi."""

    def get_screen_size(self) -> tuple[int, int]:
        try:
            out = subprocess.check_output(["xdotool", "getdisplaygeometry"],
                                          text=True).strip()
            w, h = out.split()
            return int(w), int(h)
        except Exception:
            return 1920, 1080

    def find_windows(self, app_name: str) -> list[WindowInfo]:
        try:
            out = subprocess.check_output(
                ["wmctrl", "-l", "-G"], text=True
            )
        except FileNotFoundError:
            logger.warning("wmctrl yüklü değil. `sudo apt install wmctrl`")
            return []

        results = []
        for line in out.splitlines():
            parts = line.split(None, 9)
            if len(parts) < 9:
                continue
            win_id, _desktop, x, y, w, h = parts[0], parts[1], *parts[2:6]
            title = parts[-1]
            if app_name.lower() in title.lower():
                results.append(WindowInfo(
                    handle=win_id, title=title,
                    x=int(x), y=int(y), width=int(w), height=int(h),
                ))
        return results

    def move_window(self, win_id: str, x: int, y: int, w: int, h: int) -> bool:
        try:
            subprocess.run(
                ["wmctrl", "-ir", win_id, "-e", f"0,{x},{y},{w},{h}"],
                check=True, capture_output=True,
            )
            return True
        except Exception as e:
            logger.warning("wmctrl pencere taşıma hatası: %s", e)
            return False

    def save_layout(self, mode_name: str) -> Path:
        LAYOUTS_DIR.mkdir(parents=True, exist_ok=True)
        layout_path = LAYOUTS_DIR / f"{mode_name}.json"
        try:
            out = subprocess.check_output(["wmctrl", "-l", "-G"], text=True)
            windows = [{"raw": line} for line in out.splitlines() if line]
        except Exception:
            windows = []
        layout_path.write_text(json.dumps({"mode": mode_name, "windows": windows},
                                           ensure_ascii=False, indent=2), encoding="utf-8")
        return layout_path


# ── macOS Backend ──────────────────────────────────────────────────────────

class _MacOSBackend:
    """AppleScript tabanlı macOS pencere yöneticisi (minimal)."""

    def get_screen_size(self) -> tuple[int, int]:
        script = 'tell application "Finder" to get bounds of window of desktop'
        try:
            out = subprocess.check_output(["osascript", "-e", script], text=True)
            parts = out.strip().split(", ")
            return int(parts[2]), int(parts[3])
        except Exception:
            return 1920, 1080

    def find_windows(self, app_name: str) -> list[WindowInfo]:
        return []  # macOS: AppleScript window enumeration karmaşık, Faz 2 kapsamı dışı

    def move_window(self, *args: Any) -> bool:
        return False

    def save_layout(self, mode_name: str) -> Path:
        LAYOUTS_DIR.mkdir(parents=True, exist_ok=True)
        path = LAYOUTS_DIR / f"{mode_name}.json"
        path.write_text(json.dumps({"mode": mode_name, "windows": [], "platform": "macos"}),
                        encoding="utf-8")
        return path


# ── Arrangement Helpers ────────────────────────────────────────────────────

def _compute_positions(
    arrangement: str, screen_w: int, screen_h: int, app_count: int
) -> list[tuple[int, int, int, int]]:
    """Düzene göre x/y/w/h değerleri hesaplar.

    Returns:
        [(x, y, w, h), ...] — her uygulama için.
    """
    if app_count == 0:
        return []

    half_w = screen_w // 2
    third_w = screen_w // 3

    if arrangement == "fullscreen":
        return [(0, 0, screen_w, screen_h)] * app_count

    if arrangement == "split-left-right":
        result = [
            (0, 0, half_w, screen_h),
            (half_w, 0, half_w, screen_h),
        ]
        return result[:min(app_count, 2)]


    if arrangement == "triple-column":
        return [
            (i * third_w, 0, third_w, screen_h)
            for i in range(min(app_count, 3))
        ]

    if arrangement == "main-secondary":
        result = [(0, 0, int(screen_w * 0.65), screen_h)]  # Ana
        side_w = screen_w - int(screen_w * 0.65)
        side_h = screen_h // max(1, app_count - 1)
        for i in range(1, app_count):
            result.append((int(screen_w * 0.65), (i - 1) * side_h, side_w, side_h))
        return result

    # custom → fullscreen fallback
    return [(0, 0, screen_w, screen_h)] * app_count


# ── Main Agent ─────────────────────────────────────────────────────────────

class LayoutAgent(BaseAgent):
    """Masaüstü pencere düzenleyici agent.

    Platform'a göre doğru backend seçer:
    - Windows → pywin32
    - Linux   → wmctrl / xdotool
    - macOS   → AppleScript (minimal)
    """

    def __init__(self) -> None:
        if IS_WINDOWS:
            self._backend: _WindowsBackend | _LinuxBackend | _MacOSBackend = _WindowsBackend()
        elif IS_LINUX:
            self._backend = _LinuxBackend()
        else:
            self._backend = _MacOSBackend()

    @property
    def name(self) -> str:
        return AgentName.LAYOUT

    def execute(self, event: SwitchEvent) -> StatusReport:
        layout_cfg: dict[str, Any] = event.config.get("layout", {})
        if not layout_cfg:
            return StatusReport(
                agent_name=self.name, success=True,
                message="Layout: Config'de layout bölümü yok, atlandı.",
            )

        arrangement = layout_cfg.get("arrangement", "fullscreen")
        primary_app = layout_cfg.get("primary_app")

        # Ekran boyutu
        screen_w, screen_h = self._backend.get_screen_size()

        # Uygulanacak pencereler
        app_names: list[str] = []
        if primary_app:
            app_names.append(primary_app)

        # processes.start listesinden diğerlerini al
        start_list: list[str] = event.config.get("processes", {}).get("start", [])
        for app in start_list:
            name = app.split()[0]
            if name not in app_names:
                app_names.append(name)

        if not app_names:
            return StatusReport(
                agent_name=self.name, success=True,
                message="Layout: Düzenlenecek uygulama yok.",
            )

        if event.dry_run:
            positions = _compute_positions(arrangement, screen_w, screen_h, len(app_names))
            details = [f"{app} → ({x},{y}) {w}x{h}" for app, (x, y, w, h)
                       in zip(app_names, positions)]
            return StatusReport(
                agent_name=self.name, success=True,
                message=f"Layout [dry-run]: '{arrangement}' düzeni uygulanacak.",
                details={"positions": details, "screen": f"{screen_w}x{screen_h}"},
            )

        # Gerçek uygula
        positions = _compute_positions(arrangement, screen_w, screen_h, len(app_names))
        moved: list[str] = []
        skipped: list[str] = []

        for app_name, (x, y, w, h) in zip(app_names, positions):
            windows = self._backend.find_windows(app_name)
            if not windows:
                skipped.append(app_name)
                continue
            # İlk pencereyi taşı
            ok = self._backend.move_window(windows[0].handle, x, y, w, h)
            if ok:
                moved.append(app_name)
            else:
                skipped.append(app_name)

        # Layout'u kaydet
        try:
            self._backend.save_layout(event.mode_name)
        except Exception as e:
            logger.warning("Layout kaydedilemedi: %s", e)

        return StatusReport(
            agent_name=self.name,
            success=True,
            message=f"Layout '{arrangement}': {len(moved)} pencere düzenlendi, {len(skipped)} atlandı.",
            details={"moved": moved, "skipped": skipped, "screen": f"{screen_w}x{screen_h}"},
        )

    def rollback(self, event: SwitchEvent) -> StatusReport:
        """Önceki mod layout'unu geri yükler (varsa)."""
        prev_mode = event.previous_mode
        if not prev_mode:
            return StatusReport(agent_name=self.name, success=True,
                                message="Layout rollback: Önceki mod yok.")
        layout_path = LAYOUTS_DIR / f"{prev_mode}.json"
        if not layout_path.exists():
            return StatusReport(agent_name=self.name, success=True,
                                message=f"Layout rollback: '{prev_mode}' için kayıt bulunamadı.")

        # Kaydedilmiş pencere konumlarını geri yükle
        try:
            data = json.loads(layout_path.read_text(encoding="utf-8"))
            restored = 0
            for win_data in data.get("windows", []):
                if IS_WINDOWS and "hwnd" in win_data:
                    ok = self._backend.move_window(  # type: ignore[arg-type]
                        win_data["hwnd"],
                        win_data["x"], win_data["y"],
                        win_data["w"], win_data["h"],
                    )
                    if ok:
                        restored += 1
            return StatusReport(agent_name=self.name, success=True,
                                message=f"Layout rollback: {restored} pencere eski konumuna döndü.")
        except Exception as e:
            return StatusReport(agent_name=self.name, success=False,
                                message=f"Layout rollback hatası: {e}")
