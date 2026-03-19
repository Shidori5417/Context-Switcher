"""Layout Agent birim testleri — win32gui ve subprocess mock'lu."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.agents.layout_agent import (
    LayoutAgent,
    WindowInfo,
    _compute_positions,
)
from src.core.event_bus import SwitchEvent


def _make_event(arrangement: str = "split-left-right", primary: str = "vscode") -> SwitchEvent:
    return SwitchEvent(
        mode_name="dev",
        config={
            "name": "Dev",
            "layout": {"arrangement": arrangement, "primary_app": primary},
            "processes": {"start": ["terminal"]},
        },
    )


# ── _compute_positions ──────────────────────────────────────────────────────

class TestComputePositions:
    def test_fullscreen(self):
        pos = _compute_positions("fullscreen", 1920, 1080, 1)
        assert pos == [(0, 0, 1920, 1080)]

    def test_split_two_apps(self):
        pos = _compute_positions("split-left-right", 1920, 1080, 2)
        assert len(pos) == 2
        assert pos[0] == (0, 0, 960, 1080)
        assert pos[1] == (960, 0, 960, 1080)

    def test_split_one_app(self):
        pos = _compute_positions("split-left-right", 1920, 1080, 1)
        assert len(pos) == 1

    def test_triple_column(self):
        pos = _compute_positions("triple-column", 1920, 1080, 3)
        assert len(pos) == 3
        assert pos[0][0] == 0
        assert pos[1][0] == 640
        assert pos[2][0] == 1280

    def test_main_secondary_two(self):
        pos = _compute_positions("main-secondary", 1920, 1080, 2)
        assert len(pos) == 2
        # Ana uygulama geniş olmalı
        assert pos[0][2] > pos[1][2]

    def test_empty_apps(self):
        pos = _compute_positions("fullscreen", 1920, 1080, 0)
        assert pos == []

    def test_unknown_arrangement_fallback(self):
        pos = _compute_positions("custom", 1920, 1080, 1)
        assert pos == [(0, 0, 1920, 1080)]


# ── LayoutAgent.execute — Windows Backend ──────────────────────────────────

class TestLayoutAgentExecute:
    def test_no_config_skipped(self):
        agent = LayoutAgent()
        event = SwitchEvent(mode_name="dev", config={"name": "Dev"})
        report = agent.execute(event)
        assert report.success
        assert "atlandı" in report.message

    def test_dry_run_returns_positions(self):
        agent = LayoutAgent()
        event = _make_event("split-left-right")
        event = SwitchEvent(
            mode_name="dev",
            config={
                "name": "Dev",
                "layout": {"arrangement": "split-left-right", "primary_app": "vscode"},
                "processes": {"start": ["terminal"]},
            },
            dry_run=True,
        )
        with patch.object(agent._backend, "get_screen_size", return_value=(1920, 1080)):
            report = agent.execute(event)
        assert report.success
        assert "dry-run" in report.message
        assert report.details.get("screen") == "1920x1080"

    def test_execute_moves_found_windows(self):
        agent = LayoutAgent()
        mock_win = WindowInfo(handle=1, title="VS Code", x=0, y=0, width=100, height=100)
        event = SwitchEvent(
            mode_name="dev",
            config={
                "name": "Dev",
                "layout": {"arrangement": "fullscreen", "primary_app": "vscode"},
                "processes": {},
            },
        )
        with (
            patch.object(agent._backend, "get_screen_size", return_value=(1920, 1080)),
            patch.object(agent._backend, "find_windows", return_value=[mock_win]),
            patch.object(agent._backend, "move_window", return_value=True) as mock_move,
            patch.object(agent._backend, "save_layout", return_value=None),
        ):
            report = agent.execute(event)

        mock_move.assert_called_once_with(1, 0, 0, 1920, 1080)
        assert "1 pencere" in report.message

    def test_skips_not_found_apps(self):
        agent = LayoutAgent()
        event = SwitchEvent(
            mode_name="dev",
            config={
                "name": "Dev",
                "layout": {"arrangement": "fullscreen", "primary_app": "nonexistent"},
                "processes": {},
            },
        )
        with (
            patch.object(agent._backend, "get_screen_size", return_value=(1920, 1080)),
            patch.object(agent._backend, "find_windows", return_value=[]),
            patch.object(agent._backend, "save_layout", return_value=None),
        ):
            report = agent.execute(event)

        assert report.success
        assert "atlandı" in report.message


class TestLayoutAgentRollback:
    def test_rollback_no_previous_mode(self):
        agent = LayoutAgent()
        event = SwitchEvent(mode_name="dev", config={}, previous_mode=None)
        report = agent.rollback(event)
        assert report.success
        assert "yok" in report.message

    def test_rollback_no_layout_file(self, tmp_path):
        agent = LayoutAgent()
        event = SwitchEvent(mode_name="dev", config={}, previous_mode="study")
        with patch("src.agents.layout_agent.LAYOUTS_DIR", tmp_path):
            report = agent.rollback(event)
        assert report.success
        assert "bulunamadı" in report.message
