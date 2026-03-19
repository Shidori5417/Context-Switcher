"""Context-Switcher CLI — Typer ile komut satırı arayüzü."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.core.config_loader import discover_modes, load_mode

app = typer.Typer(
    name="context",
    help="🧠 Context-Switcher — Akıllı Çalışma Alanı Mimarı",
    add_completion=False,
    rich_markup_mode="rich",
)
console = Console()


@app.command()
def switch(
    mode: Optional[str] = typer.Argument(None, help="Geçiş yapılacak mod adı"),
    list_modes: bool = typer.Option(False, "--list", "-l", help="Mevcut modları listele"),
    status: bool = typer.Option(False, "--status", "-s", help="Aktif mod durumunu göster"),
    dry_run: bool = typer.Option(False, "--dry-run", "-n", help="Simülasyon — değişiklik yapma"),
    rollback: bool = typer.Option(False, "--rollback", "-r", help="Son geçişi geri al"),
) -> None:
    """Çalışma modlarını yönet ve geçiş yap."""
    if list_modes:
        _handle_list()
        return

    if status:
        _handle_status()
        return

    if rollback:
        _handle_rollback()
        return

    if mode is None:
        console.print(
            "[yellow]⚠ Mod adı belirtilmedi.[/yellow] "
            "Kullanım: [bold]context switch <mod>[/bold] veya [bold]context switch --list[/bold]"
        )
        raise typer.Exit(1)

    _handle_switch(mode, dry_run)


def _handle_list() -> None:
    """Mevcut modları tablo olarak listeler."""
    modes = discover_modes()
    if not modes:
        console.print("[dim]Henüz tanımlı mod yok. modes/ dizinine YAML dosyaları ekleyin.[/dim]")
        return

    table = Table(title="📋 Mevcut Modlar", show_lines=True)
    table.add_column("Mod", style="bold cyan")
    table.add_column("Dosya", style="dim")

    for name, path in sorted(modes.items()):
        table.add_row(name, str(path))

    console.print(table)


def _handle_status() -> None:
    """Aktif mod durumunu gösterir."""
    console.print(
        Panel(
            "[dim]Henüz aktif mod yok. Geçiş yapmak için:[/dim]\n"
            "[bold]context switch <mod>[/bold]",
            title="📊 Durum",
            border_style="blue",
        )
    )


def _handle_rollback() -> None:
    """Son geçişi geri alır."""
    console.print("[yellow]🔄 Rollback henüz implement edilmedi (Faz 1).[/yellow]")


def _handle_switch(mode: str, dry_run: bool) -> None:
    """Mod geçişini başlatır."""
    # Mod dosyasını bul
    modes = discover_modes()
    if mode not in modes:
        console.print(f"[red]✗ '{mode}' adında bir mod bulunamadı.[/red]")
        console.print("[dim]Mevcut modları görmek için: context switch --list[/dim]")
        raise typer.Exit(1)

    # YAML'ı yükle ve validate et
    try:
        config = load_mode(modes[mode])
    except Exception as e:
        console.print(f"[red]✗ Mod dosyası okunamadı: {e}[/red]")
        raise typer.Exit(1)

    mode_name = config.get("name", mode)
    icon = config.get("icon", "🔄")

    if dry_run:
        console.print(
            Panel(
                f"{icon} [bold]{mode_name}[/bold] moduna geçiş simülasyonu\n\n"
                f"[dim]Gerçek değişiklik yapılmayacak.[/dim]",
                title="🧪 Dry Run",
                border_style="yellow",
            )
        )
    else:
        console.print(
            Panel(
                f"{icon} [bold]{mode_name}[/bold] moduna geçiliyor...\n\n"
                f"[dim]Agent'lar henüz implement edilmedi (Faz 1).[/dim]",
                title="🔄 Geçiş",
                border_style="green",
            )
        )


def app_entry() -> None:
    """pyproject.toml entry point."""
    app()


if __name__ == "__main__":
    app_entry()
