"""Context-Switcher TUI Dashboard modülü."""

from __future__ import annotations

import time
from datetime import datetime

from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table

from src.core.config_loader import discover_modes
from src.core.state import get_state

def _generate_mode_table() -> Table:
    """Kayıtlı modları ve aktiflik durumunu gösterir."""
    state = get_state()
    modes = discover_modes()

    table = Table(show_header=True, header_style="bold magenta", expand=True)
    table.add_column("Durum", justify="center", width=8)
    table.add_column("Mod Adı")
    table.add_column("Yapılandırma Dosyası")

    for name, path in sorted(modes.items()):
        if name == state.current_mode:
            status = "[bold green]▶ AKTİF[/]"
            row_style = "green"
        else:
            status = "[dim]○ BOŞ[/]"
            row_style = "dim"
        table.add_row(status, name, str(path.name), style=row_style)

    return table

def _generate_stats_panel() -> Panel:
    """Sistem state istatistiklerini gösterir."""
    state = get_state()
    
    lines = [
        f"[bold cyan]Geçerli Mod:[/bold cyan] {state.current_mode or 'Yok'}",
        f"[bold cyan]Önceki Mod:[/bold cyan] {state.previous_mode or 'Yok'}",
        f"[bold cyan]Son Geçiş:[/bold cyan] {state.switched_at or 'Hiç'}",
        f"[bold yellow]Dondurulan Süreç (Suspend):[/bold yellow] {len(state.suspended_pids)} Process",
        f"[bold magenta]Son Snapshot:[/bold magenta] {state.last_snapshot or 'Yok'}",
    ]
    
    return Panel(
        "\n\n".join(lines),
        title="📊 Sistem İstatistikleri",
        border_style="cyan"
    )

def _generate_layout() -> Layout:
    """Dashboard yerleşimini oluşturur."""
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="main"),
        Layout(name="footer", size=3)
    )
    
    layout["main"].split_row(
        Layout(name="left", ratio=2),
        Layout(name="right", ratio=3)
    )
    
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    layout["header"].update(Panel(f"[bold]Context-Switcher Dashboard[/bold] | {now}", style="bold white on blue"))
    layout["footer"].update(Panel("[dim]Çıkmak için Ctrl+C'ye basın...[/dim]"))
    
    layout["left"].update(_generate_stats_panel())
    layout["right"].update(Panel(_generate_mode_table(), title="⚙️ Tanımlı Modlar", border_style="magenta"))
    
    return layout

def run_dashboard() -> None:
    """Live dashboard'u başlatır."""
    try:
        with Live(_generate_layout(), refresh_per_second=2, screen=True) as live:
            while True:
                time.sleep(0.5)
                live.update(_generate_layout())
    except KeyboardInterrupt:
        pass
