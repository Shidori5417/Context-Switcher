"""Config Loader birim testleri."""

from pathlib import Path

import pytest
import yaml

from src.core.config_loader import load_mode, validate_mode_config

# Test fixtures dizini
FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def ensure_fixtures_dir():
    """Test fixtures dizinini oluşturur."""
    FIXTURES_DIR.mkdir(exist_ok=True)
    yield


def _write_yaml(filename: str, data: dict) -> Path:
    """Geçici YAML dosyası yazar."""
    path = FIXTURES_DIR / filename
    path.write_text(yaml.dump(data, allow_unicode=True), encoding="utf-8")
    return path


class TestLoadMode:
    def test_valid_config(self):
        config = {
            "name": "Test Modu",
            "icon": "🧪",
            "processes": {"start": ["vscode"], "suspend": ["discord"]},
        }
        path = _write_yaml("valid.yaml", config)
        result = load_mode(path)
        assert result["name"] == "Test Modu"
        assert result["icon"] == "🧪"

    def test_minimal_config(self):
        config = {"name": "Minimal"}
        path = _write_yaml("minimal.yaml", config)
        result = load_mode(path)
        assert result["name"] == "Minimal"

    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            load_mode(Path("/nonexistent/mode.yaml"))

    def test_empty_file(self):
        path = FIXTURES_DIR / "empty.yaml"
        path.write_text("", encoding="utf-8")
        with pytest.raises(ValueError, match="Boş mod dosyası"):
            load_mode(path)

    def test_invalid_schema(self):
        config = {"name": "Test", "unknown_field": True}
        path = _write_yaml("invalid_schema.yaml", config)
        with pytest.raises(Exception):
            load_mode(path)

    def test_missing_name(self):
        config = {"icon": "🎮"}
        path = _write_yaml("no_name.yaml", config)
        with pytest.raises(Exception):
            load_mode(path)


class TestValidateModeConfig:
    def test_valid(self):
        errors = validate_mode_config({"name": "Test"})
        assert errors == []

    def test_invalid(self):
        errors = validate_mode_config({"unknown": True})
        assert len(errors) > 0

    def test_full_config(self):
        config = {
            "name": "Full Test",
            "icon": "🧪",
            "hotkey": "Ctrl+Alt+T",
            "processes": {"start": ["app1"], "suspend": ["app2"]},
            "layout": {"workspace": 1, "arrangement": "fullscreen", "primary_app": "app1"},
            "browser": {
                "profile": "Test",
                "restore_session": True,
                "tab_groups": [{"name": "Group", "tabs": ["https://example.com"]}],
            },
            "environment": {
                "volume": 50,
                "notifications": {"mute": ["app2"], "allow": ["app1"]},
                "music": {"app": "spotify", "playlist": "Test"},
            },
        }
        errors = validate_mode_config(config)
        assert errors == []

    def test_invalid_volume(self):
        config = {"name": "Bad", "environment": {"volume": 150}}
        errors = validate_mode_config(config)
        assert len(errors) > 0

    def test_invalid_arrangement(self):
        config = {"name": "Bad", "layout": {"arrangement": "invalid-type"}}
        errors = validate_mode_config(config)
        assert len(errors) > 0
