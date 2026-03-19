"""Browser Agent — Tarayıcı sekmelerini ve profillerini yönetir.

Chrome DevTools Protocol (CDP) ile çalışır.
Desteklenen tarayıcılar: Chrome, Edge (Chromium), Brave.
Chrome yoksa Edge'e otomatik düşer — Edge Windows'ta her zaman yüklü.
"""

from __future__ import annotations

import json
import logging
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from src.agents.base_agent import BaseAgent
from src.core.event_bus import AgentName, StatusReport, SwitchEvent

logger = logging.getLogger(__name__)

SESSIONS_DIR = Path.home() / ".context-switcher" / "sessions"
CDP_PORT = 9222

# ── Tarayıcı Tespiti ────────────────────────────────────────────────────────

_BROWSER_PATHS_WINDOWS: list[tuple[str, str]] = [
    ("chrome", r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
    ("chrome", r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
    ("edge", r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
    ("edge", r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
    ("brave", r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe"),
]

_BROWSER_PATHS_LINUX: list[tuple[str, str]] = [
    ("chrome", "/usr/bin/google-chrome"),
    ("chrome", "/usr/bin/chromium-browser"),
    ("chrome", "/usr/bin/chromium"),
    ("brave", "/usr/bin/brave-browser"),
]


def detect_browser() -> tuple[str, str] | None:
    """Yüklü bir Chromium tabanlı tarayıcı bulur.

    Returns:
        (tarayıcı_adı, yürütülebilir_yol) veya None.
    """
    if sys.platform == "win32":
        candidates = _BROWSER_PATHS_WINDOWS
    else:
        candidates = _BROWSER_PATHS_LINUX

    for name, path in candidates:
        if Path(path).exists():
            return name, path
    return None


# ── CDP Client ─────────────────────────────────────────────────────────────

class CDPClient:
    """Chrome DevTools Protocol REST API istemcisi.

    Sadece `requests` kullanır — WebSocket gerektirmez.
    """

    def __init__(self, port: int = CDP_PORT) -> None:
        self._base = f"http://localhost:{port}"
        self._available: bool | None = None

    def is_available(self) -> bool:
        """CDP portu açık mı?"""
        if self._available is not None:
            return self._available
        try:
            import requests
            resp = requests.get(f"{self._base}/json/version", timeout=2)
            self._available = resp.status_code == 200
        except Exception:
            self._available = False
        return self._available

    def get_tabs(self) -> list[dict[str, Any]]:
        """Açık tüm sekmeleri listeler."""
        try:
            import requests
            resp = requests.get(f"{self._base}/json", timeout=3)
            return [t for t in resp.json() if t.get("type") == "page"]
        except Exception as e:
            logger.debug("CDP sekme listesi alınamadı: %s", e)
            return []

    def open_tab(self, url: str) -> bool:
        """Yeni sekme açar."""
        try:
            import requests
            requests.get(f"{self._base}/json/new?{url}", timeout=3)
            return True
        except Exception:
            return False

    def close_tab(self, tab_id: str) -> bool:
        """Belirtilen sekmeyi kapatır."""
        try:
            import requests
            requests.get(f"{self._base}/json/close/{tab_id}", timeout=3)
            return True
        except Exception:
            return False


# ── Browser Launcher ────────────────────────────────────────────────────────

def launch_browser_with_cdp(browser_path: str, profile: str | None = None) -> subprocess.Popen | None:
    """Tarayıcıyı CDP portu açık olarak başlatır."""
    cmd = [
        browser_path,
        f"--remote-debugging-port={CDP_PORT}",
        "--no-first-run",
        "--no-default-browser-check",
    ]
    if profile:
        cmd.append(f"--profile-directory={profile}")

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        time.sleep(2)  # CDP portunu dinlemesi için bekle
        return proc
    except FileNotFoundError:
        return None


# ── Main Agent ─────────────────────────────────────────────────────────────

class BrowserAgent(BaseAgent):
    """Tarayıcı orkestratörü.

    Chrome/Edge/Brave'i otomatik tespit eder.
    Tarayıcı yoksa veya CDP kapalıysa geçişi durdurmaz, sadece uyarı verir.
    """

    def __init__(self) -> None:
        self._cdp = CDPClient(port=CDP_PORT)

    @property
    def name(self) -> str:
        return AgentName.BROWSER

    def execute(self, event: SwitchEvent) -> StatusReport:
        browser_cfg: dict[str, Any] = event.config.get("browser", {})
        if not browser_cfg:
            return StatusReport(
                agent_name=self.name, success=True,
                message="Browser: Config'de browser bölümü yok, atlandı.",
            )

        profile = browser_cfg.get("profile")
        tab_groups: list[dict] = browser_cfg.get("tab_groups", [])
        restore = browser_cfg.get("restore_session", False)

        # Tüm açılacak URL'leri topla
        target_urls: list[str] = []
        for group in tab_groups:
            target_urls.extend(group.get("tabs", []))

        if event.dry_run:
            return StatusReport(
                agent_name=self.name, success=True,
                message=f"Browser [dry-run]: {len(target_urls)} sekme açılacak.",
                details={"urls": target_urls, "profile": profile},
            )

        # CDP kontrolü
        if not self._cdp.is_available():
            # Tarayıcı yok mu? Başlatmayı dene
            browser_info = detect_browser()
            if browser_info:
                browser_name, browser_path = browser_info
                logger.info("CDP kapalı. %s başlatılıyor...", browser_name)
                launch_browser_with_cdp(browser_path, profile)
                self._cdp._available = None  # Önbelleği temizle

            if not self._cdp.is_available():
                return StatusReport(
                    agent_name=self.name, success=True,  # Başarısız ama bloke etme
                    message="Browser: CDP bağlantısı kurulamadı. Tarayıcı atlandı.",
                    details={"hint": "Tarayıcıyı --remote-debugging-port=9222 ile başlatın."},
                )

        # Mevcut sekmeleri yedekle
        backup_path = self._backup_tabs(event.mode_name)

        # Yeni sekmeleri aç
        opened = 0
        for url in target_urls:
            if self._cdp.open_tab(url):
                opened += 1

        return StatusReport(
            agent_name=self.name, success=True,
            message=f"Browser: {opened}/{len(target_urls)} sekme açıldı.",
            details={
                "opened": opened,
                "total": len(target_urls),
                "backup": str(backup_path) if backup_path else None,
            },
        )

    def rollback(self, event: SwitchEvent) -> StatusReport:
        """Önceki mod sekmelerini yedekten geri yükler."""
        if not self._cdp.is_available():
            return StatusReport(
                agent_name=self.name, success=True,
                message="Browser rollback: CDP mevcut değil, atlandı.",
            )

        # Son session dosyasını bul
        prev_mode = event.previous_mode
        if not prev_mode:
            return StatusReport(agent_name=self.name, success=True,
                                message="Browser rollback: Önceki mod yok.")

        session_files = sorted(SESSIONS_DIR.glob(f"*_{prev_mode}.json"), reverse=True)
        if not session_files:
            return StatusReport(agent_name=self.name, success=True,
                                message=f"Browser rollback: '{prev_mode}' için session bulunamadı.")

        try:
            data = json.loads(session_files[0].read_text(encoding="utf-8"))
            restored = 0
            for tab in data.get("tabs", []):
                if self._cdp.open_tab(tab.get("url", "")):
                    restored += 1
            return StatusReport(
                agent_name=self.name, success=True,
                message=f"Browser rollback: {restored} sekme geri yüklendi.",
            )
        except Exception as e:
            return StatusReport(agent_name=self.name, success=False,
                                message=f"Browser rollback hatası: {e}")

    # ── Helpers ───────────────────────────────────────────────────────────

    def _backup_tabs(self, mode_name: str) -> Path | None:
        """Mevcut sekmeleri JSON'a kaydeder."""
        tabs = self._cdp.get_tabs()
        if not tabs:
            return None

        SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = SESSIONS_DIR / f"{timestamp}_{mode_name}.json"
        path.write_text(
            json.dumps({"mode": mode_name, "timestamp": timestamp, "tabs": tabs},
                       ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return path
