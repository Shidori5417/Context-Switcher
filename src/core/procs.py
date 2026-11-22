"""Süreç kayıtları — PID + create_time çiftleri (PID yeniden kullanımına karşı)."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import psutil

# create_time karşılaştırmasında kabul edilen sapma (saniye)
CREATE_TIME_TOLERANCE = 1.0

ProcEntry = dict[str, Any]


def make_entry(proc: psutil.Process) -> ProcEntry:
    """Bir sürecin {pid, create_time} kaydını üretir (create_time alınamazsa None)."""
    try:
        create_time: float | None = float(proc.create_time())
    except (psutil.Error, TypeError, ValueError):
        create_time = None
    return {"pid": int(proc.pid), "create_time": create_time}


def normalize_entries(items: Iterable[Any] | None) -> list[ProcEntry]:
    """Eski (düz int) ve yeni ({pid, create_time}) formatları tek biçime çevirir."""
    entries: list[ProcEntry] = []
    for item in items or []:
        if isinstance(item, bool):
            continue
        if isinstance(item, int):
            entries.append({"pid": item, "create_time": None})
        elif isinstance(item, dict) and isinstance(item.get("pid"), int):
            create_time = item.get("create_time")
            entries.append(
                {
                    "pid": item["pid"],
                    "create_time": float(create_time)
                    if isinstance(create_time, (int, float))
                    else None,
                }
            )
    return entries


def merge_entries(*groups: Iterable[Any]) -> list[ProcEntry]:
    """Birden çok listeyi PID bazında tekilleştirerek birleştirir (ilk kayıt kazanır,
    create_time bilgisi sonradan gelen kayıtta varsa tamamlanır)."""
    merged: dict[int, ProcEntry] = {}
    for group in groups:
        for entry in normalize_entries(group):
            current = merged.get(entry["pid"])
            if current is None:
                merged[entry["pid"]] = entry
            elif current["create_time"] is None:
                current["create_time"] = entry["create_time"]
    return list(merged.values())


def matches_entry(proc: psutil.Process, entry: ProcEntry) -> bool:
    """Canlı süreç, kayıttaki süreçle aynı mı? create_time yoksa doğrulanamaz → True."""
    recorded = entry.get("create_time")
    if recorded is None:
        return True
    try:
        return abs(float(proc.create_time()) - recorded) <= CREATE_TIME_TOLERANCE
    except (TypeError, ValueError):
        return True
