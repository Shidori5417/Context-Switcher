"""Snapshot — Geçiş öncesi sistem durumu kaydı (Faz 1'de implement edilecek)."""

from __future__ import annotations

from pathlib import Path

# Snapshot'ların kaydedileceği varsayılan dizin
SNAPSHOT_DIR = Path.home() / ".context-switcher" / "snapshots"


def take_snapshot() -> Path | None:
    """Mevcut sistem durumunun anlık görüntüsünü alır.

    TODO (Faz 1): Çalışan süreçler, pencere düzeni ve tarayıcı
    sekmelerini JSON olarak kaydet.
    """
    return None


def restore_snapshot(snapshot_path: Path) -> bool:
    """Bir snapshot'tan sistem durumunu geri yükler.

    TODO (Faz 1): JSON snapshot dosyasından durumu oku ve geri yükle.
    """
    return False
