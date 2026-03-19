"""Snapshot — Geçiş öncesi sistem durumu kaydı ve geri yükleme."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import psutil

SNAPSHOT_DIR = Path.home() / ".context-switcher" / "snapshots"


def _process_info(proc: psutil.Process) -> dict[str, Any]:
    """Bir psutil.Process nesnesinden serileştirilebilir bilgi üretir."""
    try:
        with proc.oneshot():
            return {
                "pid": proc.pid,
                "name": proc.name(),
                "exe": _safe_exe(proc),
                "status": proc.status(),
                "cpu_percent": proc.cpu_percent(),
                "memory_mb": round(proc.memory_info().rss / 1024 / 1024, 2),
            }
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return {}


def _safe_exe(proc: psutil.Process) -> str:
    try:
        return proc.exe()
    except (psutil.AccessDenied, psutil.NoSuchProcess):
        return ""


def take_snapshot(mode_name: str, suspended_pids: list[int] | None = None) -> Path:
    """Mevcut kullanıcı süreçlerinin anlık görüntüsünü alır.

    Args:
        mode_name: Geçiş yapılan modun adı.
        suspended_pids: Bu geçişte dondurulan PID'ler.

    Returns:
        Yazılan snapshot dosyasının yolu.
    """
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    snapshot_path = SNAPSHOT_DIR / f"{timestamp}_{mode_name}.json"

    processes = []
    for proc in psutil.process_iter():
        info = _process_info(proc)
        if info:
            processes.append(info)

    snapshot = {
        "mode_name": mode_name,
        "timestamp": datetime.now().isoformat(),
        "suspended_pids": suspended_pids or [],
        "processes": processes,
    }

    snapshot_path.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return snapshot_path


def load_snapshot(snapshot_path: Path) -> dict[str, Any]:
    """Snapshot dosyasını okur."""
    if not snapshot_path.exists():
        raise FileNotFoundError(f"Snapshot bulunamadı: {snapshot_path}")
    return json.loads(snapshot_path.read_text(encoding="utf-8"))


def restore_snapshot(snapshot_path: Path) -> list[int]:
    """Snapshot'taki suspended_pids listesindeki süreçleri devam ettirir.

    Returns:
        Başarıyla resume edilen PID listesi.
    """
    data = load_snapshot(snapshot_path)
    suspended_pids: list[int] = data.get("suspended_pids", [])
    resumed: list[int] = []

    for pid in suspended_pids:
        try:
            proc = psutil.Process(pid)
            proc.resume()
            resumed.append(pid)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.Error):
            pass  # Süreç zaten ölmüş ya da yetki yok — atla

    return resumed


def list_snapshots() -> list[Path]:
    """Mevcut snapshot dosyalarını tarihe göre sıralı listeler."""
    if not SNAPSHOT_DIR.exists():
        return []
    return sorted(SNAPSHOT_DIR.glob("*.json"), reverse=True)


def latest_snapshot() -> Path | None:
    """En son snapshot dosyasını döner."""
    snapshots = list_snapshots()
    return snapshots[0] if snapshots else None
