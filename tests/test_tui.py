"""TUI Dashboard testleri."""
from unittest.mock import patch, MagicMock
from src.tui import _generate_mode_table, _generate_stats_panel, _generate_layout
from rich.table import Table
from rich.panel import Panel

@patch("src.tui.get_state")
@patch("src.tui.discover_modes")
def test_dashboard_tables(mock_discover, mock_state):
    mock_discover.return_value = {"games": MagicMock(name="games.yaml")}
    mock_state.return_value = MagicMock(
        current_mode="dev",
        previous_mode="study",
        switched_at="2026-03-20 00:00:00",
        suspended_pids=[1000, 2000],
        last_snapshot=None
    )
    
    table = _generate_mode_table()
    assert isinstance(table, Table)
    
    panel = _generate_stats_panel()
    assert isinstance(panel, Panel)
    
    # Layout üretimi hatasız geçmeli
    layout = _generate_layout()
    assert layout is not None
