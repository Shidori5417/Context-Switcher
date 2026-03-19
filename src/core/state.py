"""State — Aktif mod durumunu disk üzerinde kalıcı olarak yönetir."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

_STATE_PATH = Path.home() / ".context-switcher" / "state.json"


@dataclass
class AppState:
    """Uygulamanın kalıcı durum modeli."""

    current_mode: str | None = None
    previous_mode: str | None = None
    last_snapshot: str | None = None  # snapshot dosyasının yolu
    switched_at: str | None = None    # ISO format timestamp
    suspended_pids: list[int] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {k: getattr(self, k) for k in self.__dataclass_fields__}  # type: ignore

    @classmethod
    def from_dict(cls, data: dict) -> "AppState":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


def get_state() -> AppState:
    """Disk'ten mevcut durumu okur; yoksa boş state döner."""
    if not _STATE_PATH.exists():
        return AppState()
    try:
        data = json.loads(_STATE_PATH.read_text(encoding="utf-8"))
        return AppState.from_dict(data)
    except (json.JSONDecodeError, TypeError):
        return AppState()


def save_state(state: AppState) -> None:
    """Durumu diske yazar."""
    _STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _STATE_PATH.write_text(
        json.dumps(state.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def update_state(
    current_mode: str,
    previous_mode: str | None = None,
    last_snapshot: str | None = None,
    suspended_pids: list[int] | None = None,
) -> AppState:
    """Mevcut state'i günceller ve diske yazar."""
    state = AppState(
        current_mode=current_mode,
        previous_mode=previous_mode,
        last_snapshot=last_snapshot,
        switched_at=datetime.now().isoformat(),
        suspended_pids=suspended_pids or [],
    )
    save_state(state)
    return state


def clear_state() -> None:
    """Durumu sıfırlar (rollback sonrası veya çıkışta)."""
    if _STATE_PATH.exists():
        _STATE_PATH.unlink()
