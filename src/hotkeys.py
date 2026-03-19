"""Klavye kısayolları için dinleyici modülü."""

from __future__ import annotations

import threading
import keyboard
from typing import Callable

from src.core.config_loader import discover_modes, load_mode
from src.core.logger import logger

class HotkeyManager:
    """Modlarda tanımlı hotkey parametrelerine göre global klavye kısayollarını dinler."""

    def __init__(self, on_switch: Callable[[str], None]) -> None:
        self.on_switch = on_switch
        self._registered_keys: set[str] = set()

    def register_all(self) -> None:
        """YAML dosyalarını okuyarak 'hotkey' geçen modları dinlemeye başlar."""
        logger.info("Kısayol yöneticisi (Hotkeys) başlatılıyor.")
        modes = discover_modes()
        
        # Öncekileri temizle (reload desteği için)
        keyboard.unhook_all()
        self._registered_keys.clear()

        for mode_name, path in modes.items():
            try:
                config = load_mode(path)
                hotkey = config.get("hotkey")
                if hotkey:
                    logger.debug("Kısayol eklendi: %s -> %s", hotkey, mode_name)
                    # Keyboard callback için local variable capture fix
                    def make_callback(m: str) -> Callable:
                        def action() -> None:
                            logger.info("Kısayol ile (hotkey) geçiş tetiklendi: %s", m)
                            # Keyboard callback thread'indedir, asenkron geçiş güvenli olmayabilir
                            # O yüzden background thread'de on_switch çağırılabilir.
                            threading.Thread(target=self.on_switch, args=(m,), daemon=True).start()
                        return action
                    
                    keyboard.add_hotkey(hotkey, make_callback(mode_name))
                    self._registered_keys.add(hotkey)
            except Exception as e:
                logger.error("Hotkey okuma hatası (%s): %s", mode_name, e)

    def unregister_all(self) -> None:
        """Tüm kısayolları kaldırır."""
        logger.info("Tüm kısayollar kaldırılıyor.")
        keyboard.unhook_all()
        self._registered_keys.clear()
