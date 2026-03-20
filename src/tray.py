"""Sistem tepsisi (System Tray) yönetimi."""

from __future__ import annotations

import sys
import threading
from typing import Any, Callable

import pystray
from PIL import Image, ImageDraw
from pystray import MenuItem as item

from src.core.config_loader import discover_modes, load_mode
from src.core.logger import logger
from src.core.state import get_state

def _create_icon_image(color: str = "#4CAF50") -> Image.Image:
    """Tepsi için basit bir (C) ikonu oluşturur."""
    width, height = 64, 64
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    d = ImageDraw.Draw(image)
    # Arka plan yuvarlak
    d.ellipse((4, 4, 60, 60), fill=color)
    # Ortaya C harfi veya basit şekil
    d.arc((16, 16, 48, 48), start=45, end=315, fill="white", width=8)
    return image


class TrayManager:
    """Sistem tepsisinde ikonu çalıştıran sınıf."""

    def __init__(self, on_switch: Callable[[str], None]) -> None:
        self.on_switch = on_switch
        self._icon: pystray.Icon | None = None

    def _build_menu(self) -> tuple[pystray.MenuItem, ...]:
        """Dinamik olarak menü öğelerini oluşturur."""
        modes = discover_modes()
        state = get_state()
        current = state.current_mode

        menu_items = []
        
        # Modlar eklensin
        for mode_name, path in modes.items():
            try:
                config = load_mode(path)
                display_name = config.get("name", mode_name)
                icon_emoji = config.get("icon", "🔄")
                label = f"{icon_emoji} {display_name}"
                if current == mode_name:
                    label += " (Aktif)"

                # Python scope yakalama sorunu için default arg (m=mode_name)
                def make_callback(m: str) -> Callable:
                    def action(icon: pystray.Icon, item: pystray.MenuItem) -> None:
                        logger.info("Tray menüsünden mod geçişi: %s", m)
                        self.on_switch(m)
                        # Menüyü ve tooltip'i yenile
                        if self._icon:
                            self._icon.title = f"Context: {m}"
                            self._icon.menu = pystray.Menu(*self._build_menu())
                    return action

                menu_items.append(item(label, make_callback(mode_name), checked=lambda i, m=mode_name: m == current))
            except Exception as e:
                logger.error("Menü oluşturulurken mod okuma hatası: %s", e)

        menu_items.append(pystray.Menu.SEPARATOR)
        menu_items.append(item("Çıkış", self.stop))

        return tuple(menu_items)

    def run(self) -> None:
        """Tepsi ikonunu başlatır (Blocking çağrıdır)."""
        logger.info("System Tray başlatılıyor.")
        state = get_state()
        title = f"Context: {state.current_mode or 'Yok'}"
        
        menu = pystray.Menu(*self._build_menu())
        self._icon = pystray.Icon(
            "context_switcher",
            _create_icon_image(),
            title=title,
            menu=menu
        )
        self._icon.run()

    def stop(self, *args: Any) -> None:
        """İkonu kapatır."""
        logger.info("System Tray kapatılıyor.")
        if self._icon:
            self._icon.stop()
