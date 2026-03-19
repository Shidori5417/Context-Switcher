"""Tepsi (System Tray) modülü testleri."""
from unittest.mock import patch, MagicMock
from src.tray import TrayManager, _create_icon_image

def test_create_icon_image():
    # Sadece icon yarattiginda hata vermemeli
    img = _create_icon_image()
    assert img.size == (64, 64)
    assert img.mode == "RGBA"

@patch("src.tray.discover_modes")
@patch("src.tray.get_state")
def test_tray_manager_build_menu(mock_state, mock_discover):
    mock_discover.return_value = {"dev": MagicMock()}
    mock_state.return_value = MagicMock(current_mode="dev")
    
    with patch("src.tray.load_mode") as mock_load:
        mock_load.return_value = {"name": "Test Dev", "icon": "🚀"}
        
        tm = TrayManager(on_switch=lambda x: None)
        menu_items = tm._build_menu()
        
        assert len(menu_items) >= 2  # Mod, Ayrac, Çıkış vs.
        # "🚀 Test Dev (Aktif)" metni var mı?
        assert getattr(menu_items[0], "text", None) == "🚀 Test Dev (Aktif)"
