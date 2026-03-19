"""Config Loader — YAML mod dosyalarını okur ve JSON Schema ile doğrular."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
from jsonschema import ValidationError, validate

# Varsayılan dizinler
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_SCHEMA_PATH = _PROJECT_ROOT / "schema" / "mode_schema.json"
_BUNDLED_MODES_DIR = _PROJECT_ROOT / "modes"
_USER_MODES_DIR = Path.home() / ".context-switcher" / "modes"


def _load_schema() -> dict[str, Any]:
    """JSON Schema dosyasını yükler."""
    if not _SCHEMA_PATH.exists():
        raise FileNotFoundError(f"Schema dosyası bulunamadı: {_SCHEMA_PATH}")
    return json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))


def load_mode(mode_path: Path) -> dict[str, Any]:
    """Tek bir YAML mod dosyasını okur ve validate eder.

    Args:
        mode_path: YAML dosyasının yolu.

    Returns:
        Doğrulanmış konfigürasyon sözlüğü.

    Raises:
        FileNotFoundError: Dosya yoksa.
        yaml.YAMLError: YAML parse hatası.
        jsonschema.ValidationError: Schema'ya uymuyorsa.
    """
    if not mode_path.exists():
        raise FileNotFoundError(f"Mod dosyası bulunamadı: {mode_path}")

    raw = yaml.safe_load(mode_path.read_text(encoding="utf-8"))
    if raw is None:
        raise ValueError(f"Boş mod dosyası: {mode_path}")

    schema = _load_schema()
    validate(instance=raw, schema=schema)
    return raw


def discover_modes() -> dict[str, Path]:
    """Kullanılabilir mod dosyalarını tarar.

    Önce proje içi `modes/` dizinine, sonra `~/.context-switcher/modes/` dizinine bakar.
    `.yaml` ve `.yml` uzantılarını kabul eder, `.example` uzantılarını atlar.

    Returns:
        {mod_adı: dosya_yolu} sözlüğü.
    """
    modes: dict[str, Path] = {}

    for search_dir in [_BUNDLED_MODES_DIR, _USER_MODES_DIR]:
        if not search_dir.is_dir():
            continue
        for f in search_dir.iterdir():
            if f.suffix in (".yaml", ".yml") and ".example" not in f.name:
                mode_name = f.stem
                modes[mode_name] = f  # Kullanıcı dizini proje dizinini override eder

    return modes


def validate_mode_config(config: dict[str, Any]) -> list[str]:
    """Konfigürasyonu schema'ya karşı doğrular, hata mesajları listesi döner.

    Returns:
        Boş liste → geçerli, dolu liste → hata mesajları.
    """
    try:
        schema = _load_schema()
        validate(instance=config, schema=schema)
        return []
    except ValidationError as e:
        return [e.message]
    except FileNotFoundError:
        return ["Schema dosyası bulunamadı — validasyon atlandı."]
