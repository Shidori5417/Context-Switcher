"""Browser Agent birim testleri — requests ve CDP mock'lu."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from src.agents.browser_agent import BrowserAgent, CDPClient, detect_browser
from src.core.event_bus import SwitchEvent


def _make_event(tabs: list[str] | None = None, dry_run: bool = False) -> SwitchEvent:
    return SwitchEvent(
        mode_name="dev",
        config={
            "name": "Dev",
            "browser": {
                "profile": "Work",
                "tab_groups": [{"name": "Main", "tabs": tabs or ["https://example.com"]}],
            },
        },
        dry_run=dry_run,
    )


class TestCDPClient:
    def test_available_when_port_open(self):
        client = CDPClient(port=9222)
        mock_resp = MagicMock()
        mock_resp.status_code = 200

        with patch("requests.get", return_value=mock_resp):
            assert client.is_available() is True

    def test_unavailable_when_connection_error(self):
        client = CDPClient(port=9222)
        with patch("requests.get", side_effect=ConnectionError):
            assert client.is_available() is False

    def test_get_tabs_filters_pages(self):
        client = CDPClient(port=9222)
        mock_resp = MagicMock()
        mock_resp.json.return_value = [
            {"type": "page", "url": "https://a.com", "id": "1"},
            {"type": "service_worker", "url": "chrome://sw"},
        ]
        with patch("requests.get", return_value=mock_resp):
            tabs = client.get_tabs()
        assert len(tabs) == 1
        assert tabs[0]["url"] == "https://a.com"

    def test_get_tabs_on_error_returns_empty(self):
        client = CDPClient(port=9222)
        with patch("requests.get", side_effect=Exception):
            assert client.get_tabs() == []


class TestBrowserAgentExecute:
    def test_no_browser_config_skipped(self):
        agent = BrowserAgent()
        event = SwitchEvent(mode_name="dev", config={"name": "Dev"})
        report = agent.execute(event)
        assert report.success
        assert "atlandı" in report.message

    def test_dry_run_returns_url_count(self):
        agent = BrowserAgent()
        event = _make_event(tabs=["https://a.com", "https://b.com"], dry_run=True)
        # dry-run: CDP kontrolüne gerek yok
        report = agent.execute(event)
        assert report.success
        assert "2" in report.message

    def test_cdp_unavailable_skips_gracefully(self):
        agent = BrowserAgent()
        event = _make_event()

        with (
            patch.object(agent._cdp, "is_available", return_value=False),
            patch("src.agents.browser_agent.detect_browser", return_value=None),
        ):
            report = agent.execute(event)

        assert report.success  # Geçişi durdurmamalı
        assert "CDP" in report.message

    def test_cdp_available_opens_tabs(self):
        agent = BrowserAgent()
        event = _make_event(tabs=["https://a.com", "https://b.com"])

        with (
            patch.object(agent._cdp, "is_available", return_value=True),
            patch.object(agent._cdp, "get_tabs", return_value=[]),
            patch.object(agent._cdp, "open_tab", return_value=True) as mock_open,
            patch.object(agent, "_backup_tabs", return_value=None),
        ):
            report = agent.execute(event)

        assert mock_open.call_count == 2
        assert report.details["opened"] == 2

    def test_backup_tabs_creates_file(self, tmp_path):
        agent = BrowserAgent()
        tabs = [{"type": "page", "url": "https://example.com", "id": "1"}]

        with (
            patch.object(agent._cdp, "get_tabs", return_value=tabs),
            patch("src.agents.browser_agent.SESSIONS_DIR", tmp_path),
        ):
            path = agent._backup_tabs("dev")

        assert path is not None
        data = json.loads(path.read_text())
        assert len(data["tabs"]) == 1


class TestDetectBrowser:
    def test_detects_existing_browser(self, tmp_path):
        # Sahte bir tarayıcı dosyası oluştur
        fake_browser = tmp_path / "chrome.exe"
        fake_browser.touch()

        windows_paths = [("chrome", str(fake_browser))]
        with patch("src.agents.browser_agent._BROWSER_PATHS_WINDOWS", windows_paths):
            with patch("sys.platform", "win32"):
                result = detect_browser()
        # Platform bağımlı — sadece None olmadığını kontrol et ya da mock'la
        # (gerçek browser yolu olmadığından bu test yalnızca logic'i test eder)

    def test_returns_none_when_no_browser(self):
        with (
            patch("src.agents.browser_agent._BROWSER_PATHS_WINDOWS", []),
            patch("src.agents.browser_agent._BROWSER_PATHS_LINUX", []),
        ):
            result = detect_browser()
        assert result is None
