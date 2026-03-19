"""Hotkey modülü testleri."""
from unittest.mock import patch, MagicMock
from src.hotkeys import HotkeyManager

@patch("src.hotkeys.keyboard")
@patch("src.hotkeys.discover_modes")
def test_hotkey_manager_register(mock_discover, mock_keyboard):
    mock_discover.return_value = {"study": MagicMock()}
    
    with patch("src.hotkeys.load_mode") as mock_load:
        mock_load.return_value = {"name": "Çalışma", "hotkey": "ctrl+alt+s"}
        
        hm = HotkeyManager(on_switch=lambda x: None)
        hm.register_all()
        
        # hook_all calisti mi
        mock_keyboard.unhook_all.assert_called_once()
        # "ctrl+alt+s" eklendi mi
        mock_keyboard.add_hotkey.assert_called_once()
        
        hm.unregister_all()
        assert mock_keyboard.unhook_all.call_count == 2
