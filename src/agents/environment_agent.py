"""Environment Agent — Ses, bildirim ve müzik yönetimi."""

from __future__ import annotations

import logging
import subprocess
import sys
from typing import Any

from src.agents.base_agent import BaseAgent
from src.core.event_bus import AgentName, StatusReport, SwitchEvent

logger = logging.getLogger(__name__)

IS_WINDOWS = sys.platform == "win32"
IS_LINUX = sys.platform.startswith("linux")
IS_MACOS = sys.platform == "darwin"


# ── Ses Seviyesi ────────────────────────────────────────────────────────────

def _set_volume_windows(level: int) -> bool:
    """Windows'ta ses seviyesini ayarlar.

    Önce pycaw (COM) dener, yoksa nircmd.exe ile fallback yapar.
    """
    # Yöntem 1: pycaw (pip install pycaw)
    try:
        from ctypes import cast, POINTER
        from comtypes import CLSCTX_ALL
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = cast(interface, POINTER(IAudioEndpointVolume))
        scalar = max(0.0, min(1.0, level / 100.0))
        volume.SetMasterVolumeLevelScalar(scalar, None)
        return True
    except Exception:
        pass

    # Yöntem 2: nircmd.exe (PATH'te olmalı)
    try:
        nircmd_level = int(65535 * level / 100)
        subprocess.run(
            ["nircmd.exe", "setvolume", "0", str(nircmd_level), str(nircmd_level)],
            capture_output=True, check=True, timeout=5,
        )
        return True
    except Exception:
        pass

    # Yöntem 3: PowerShell
    try:
        script = f"[Audio]::Volume = {level / 100}; Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.SendKeys]::SendWait('%{{F4}}')"
        ps_script = (
            "$obj = New-Object -ComObject WScript.Shell; "
            f"$wshShell = New-Object -ComObject WScript.shell; "
            f"(New-Object -ComObject 'WMPlayer.OCX.7').settings.volume = {level}"
        )
        # Basit PowerShell: SoundVolumeView veya system tray simulation — çok sınırlı
        # En güvenilir fallback: ses ikonuna tıklama yerine PowerShell audio API
        import ctypes
        HWND_BROADCAST = 0xFFFF
        WM_APPCOMMAND = 0x0319
        APPCOMMAND_VOLUME_MUTE = 0x80000
        # Volume set doğrudan WINMM ile yapalım
        winmm = ctypes.windll.winmm
        # waveOutSetVolume: 0x0000 sessiz, 0xFFFF maksimum, her kanal 16 bit
        vol = int(0xFFFF * level / 100)
        packed = (vol << 16) | vol
        winmm.waveOutSetVolume(0, packed)
        return True
    except Exception as e:
        logger.warning("Ses seviyesi ayarlanamadı: %s", e)
        return False


def _set_volume_linux(level: int) -> bool:
    try:
        subprocess.run(
            ["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{level}%"],
            check=True, capture_output=True, timeout=5,
        )
        return True
    except Exception:
        try:
            subprocess.run(
                ["amixer", "sset", "Master", f"{level}%"],
                check=True, capture_output=True, timeout=5,
            )
            return True
        except Exception as e:
            logger.warning("Ses ayarlanamadı (linux): %s", e)
            return False


def _set_volume_macos(level: int) -> bool:
    try:
        subprocess.run(
            ["osascript", "-e", f"set volume output volume {level}"],
            check=True, capture_output=True, timeout=5,
        )
        return True
    except Exception as e:
        logger.warning("Ses ayarlanamadı (macOS): %s", e)
        return False


def set_volume(level: int) -> bool:
    """Platform'a uygun ses seviyesi ayarlar (0-100)."""
    level = max(0, min(100, level))
    if IS_WINDOWS:
        return _set_volume_windows(level)
    if IS_LINUX:
        return _set_volume_linux(level)
    if IS_MACOS:
        return _set_volume_macos(level)
    return False


# ── Bildirim ──────────────────────────────────────────────────────────────

def send_notification(title: str, message: str) -> bool:
    """Sistem toast bildirimi gönderir."""
    try:
        from plyer import notification
        notification.notify(
            title=title,
            message=message,
            app_name="Context-Switcher",
            timeout=4,
        )
        return True
    except Exception as e:
        logger.debug("Bildirim gönderilemedi: %s", e)
        return False


# ── Spotify ────────────────────────────────────────────────────────────────

def _spotify_open_playlist(playlist: str, app: str = "spotify") -> bool:
    """Spotify'da çalma listesi başlatır.

    Playlist bir Spotify URI (spotify:playlist:xxx) veya isim olabilir.
    """
    # URI şeması ile aç
    if playlist.startswith("spotify:"):
        uri = playlist
    else:
        # İsim → URI dönüştürme için spotipy gerekir (opsiyonel)
        # Fallback: Spotify'ı sadece aç
        uri = None

    if IS_WINDOWS:
        try:
            if uri:
                subprocess.Popen(
                    ["cmd", "/c", "start", "", uri],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
            else:
                subprocess.Popen(
                    ["spotify"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
            return True
        except Exception as e:
            logger.debug("Spotify açılamadı: %s", e)
            return False

    if IS_LINUX:
        try:
            cmd = ["spotify"]
            if uri:
                cmd.append(uri)
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except Exception:
            return False

    if IS_MACOS and uri:
        try:
            script = f'tell application "Spotify" to play track "{uri}"'
            subprocess.run(["osascript", "-e", script], capture_output=True, timeout=5)
            return True
        except Exception:
            return False

    return False


# ── Main Agent ─────────────────────────────────────────────────────────────

class EnvironmentAgent(BaseAgent):
    """Çevre yöneticisi agent.

    Ses seviyesi, sistem bildirimi ve Spotify/müzik kontrolünü sağlar.
    """

    @property
    def name(self) -> str:
        return AgentName.ENVIRONMENT

    def execute(self, event: SwitchEvent) -> StatusReport:
        env_cfg: dict[str, Any] = event.config.get("environment", {})
        if not env_cfg:
            return StatusReport(
                agent_name=self.name, success=True,
                message="Environment: Config'de environment bölümü yok, atlandı.",
            )

        actions: list[str] = []
        mode_display = event.config.get("name", event.mode_name)

        # 1. Ses seviyesi
        volume = env_cfg.get("volume")
        if volume is not None:
            if event.dry_run:
                actions.append(f"Ses → %{volume} [simülasyon]")
            else:
                ok = set_volume(volume)
                actions.append(f"Ses → %{volume} {'✓' if ok else '⚠ (başarısız)'}")

        # 2. Spotify
        music_cfg = env_cfg.get("music", {})
        playlist = music_cfg.get("playlist")
        music_app = music_cfg.get("app", "spotify")
        if playlist:
            if event.dry_run:
                actions.append(f"Müzik → '{playlist}' [simülasyon]")
            else:
                ok = _spotify_open_playlist(playlist, music_app)
                actions.append(f"Müzik → '{playlist}' {'✓' if ok else '⚠ (Spotify bulunamadı?)'}")

        # 3. Tamamlanma bildirimi (dry-run'da gösterme)
        if not event.dry_run:
            icon = event.config.get("icon", "")
            send_notification(
                title=f"{icon} Context-Switcher",
                message=f"'{mode_display}' moduna geçildi.",
            )
            actions.append("Bildirim gönderildi")

        return StatusReport(
            agent_name=self.name,
            success=True,
            message=f"Environment: {', '.join(actions) if actions else 'İşlem yapılmadı.'}",
            details={"actions": actions},
        )

    def rollback(self, event: SwitchEvent) -> StatusReport:
        """Bildirim gönder; ses önceki seviyeye döndürülmez (bilinmiyor)."""
        prev = event.previous_mode or "önceki mod"
        send_notification("Context-Switcher", f"'{prev}' moduna geri dönüldü.")
        return StatusReport(
            agent_name=self.name, success=True,
            message="Environment rollback: Bildirim gönderildi.",
        )
