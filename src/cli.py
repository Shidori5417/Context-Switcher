"""Context-Switcher CLI — Typer ile komut satırı arayüzü."""

from __future__ import annotations

import io
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.core.config_loader import discover_modes, load_mode
from src.core.snapshot import restore_snapshot
from src.core.state import clear_state, get_state, update_state


def _fix_encoding() -> None:
    """Windows konsolunda UTF-8 encoding'i zorla."""
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except AttributeError:
            pass

app = typer.Typer(
    name="context",
    help="Context-Switcher — Akilli Calisma Alani Mimari",
    add_completion=False,
    rich_markup_mode="rich",
)
console = Console(stderr=False, highlight=True)


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
            "[yellow]⚠  Mod adı belirtilmedi.[/yellow] "
            "Kullanım: [bold]context switch <mod>[/bold] "
            "veya [bold]context switch --list[/bold]"
        )
        raise typer.Exit(1)

    _handle_switch(mode, dry_run)


# ── Handlers ──────────────────────────────────────────────────────────────────

def _handle_list() -> None:
    """Mevcut modları tablo olarak listeler."""
    modes = discover_modes()
    if not modes:
        console.print(
            "[dim]Henüz tanımlı mod yok.[/dim] "
            "[cyan]modes/[/cyan] dizinine YAML dosyaları ekleyin."
        )
        return

    table = Table(title="📋 Mevcut Modlar", show_lines=True)
    table.add_column("Mod", style="bold cyan")
    table.add_column("Dosya", style="dim")

    for name, path in sorted(modes.items()):
        table.add_row(name, str(path))

    console.print(table)


def _handle_status() -> None:
    """Aktif mod durumunu gösterir."""
    state = get_state()

    if state.current_mode is None:
        console.print(
            Panel(
                "[dim]Henüz aktif mod yok.[/dim]\n"
                "[bold]context switch <mod>[/bold] ile geçiş yapın.",
                title="📊 Durum",
                border_style="blue",
            )
        )
        return

    suspended_count = len(state.suspended_pids)
    lines = [
        f"[bold green]Aktif Mod:[/bold green] {state.current_mode}",
        f"[dim]Önceki Mod:[/dim] {state.previous_mode or '—'}",
        f"[dim]Geçiş Zamanı:[/dim] {state.switched_at or '—'}",
        f"[yellow]Dondurulmuş Süreç:[/yellow] {suspended_count} adet",
    ]

    console.print(
        Panel(
            "\n".join(lines),
            title="📊 Durum",
            border_style="green",
        )
    )


def _handle_rollback() -> None:
    """Son geçişi geri alır."""
    state = get_state()

    if state.current_mode is None:
        console.print("[yellow]⚠  Geri alınacak aktif geçiş yok.[/yellow]")
        raise typer.Exit(1)

    console.print(f"[cyan]🔄 Rollback:[/cyan] '{state.current_mode}' modundan çıkılıyor...")

    # Snapshot'tan suspend edilenleri resume et
    resumed_count = 0
    if state.last_snapshot:
        snap_path = Path(state.last_snapshot)
        try:
            resumed = restore_snapshot(snap_path)
            resumed_count = len(resumed)
        except FileNotFoundError:
            console.print("[yellow]⚠  Snapshot dosyası bulunamadı — süreçler resume edilemedi.[/yellow]")
    else:
        # Snapshot yoksa state'deki PID'leri dene
        from src.agents.process_manager import ProcessManagerAgent
        pm = ProcessManagerAgent()
        report = pm.resume_processes(state.suspended_pids)
        resumed_count = len(report.resumed)

    clear_state()
    console.print(
        Panel(
            f"[green]✓ Rollback tamamlandı[/green]\n"
            f"[dim]{resumed_count} süreç devam ettirildi.[/dim]",
            title="🔄 Rollback",
            border_style="green",
        )
    )


def _handle_switch(mode_name: str, dry_run: bool) -> None:
    """Mod geçişini Orchestrator üzerinden çalıştırır."""
    # Mod dosyasını bul
    modes = discover_modes()
    if mode_name not in modes:
        console.print(f"[red]✗ '{mode_name}' adında bir mod bulunamadı.[/red]")
        console.print("[dim]Mevcut modlar: context switch --list[/dim]")
        raise typer.Exit(1)

    # YAML'ı yükle ve validate et
    try:
        config = load_mode(modes[mode_name])
    except Exception as e:
        console.print(f"[red]✗ Mod dosyası okunamadı: {e}[/red]")
        raise typer.Exit(1)

    # Mevcut durumu al
    state = get_state()
    previous_mode = state.current_mode

    mode_display = config.get("name", mode_name)
    icon = config.get("icon", "🔄")
    prefix = "🧪 [yellow]Dry Run:[/yellow]" if dry_run else f"{icon}"

    console.print(f"{prefix} [bold]{mode_display}[/bold] moduna geçiliyor...")

    # Orchestrator'ı çalıştır
    from src.agents.orchestrator import OrchestratorAgent
    from src.core.event_bus import SwitchEvent

    orchestrator = OrchestratorAgent()
    event = SwitchEvent(
        mode_name=mode_name,
        config=config,
        previous_mode=previous_mode,
        dry_run=dry_run,
    )

    result = orchestrator.execute(event)

    if result.success:
        # Çıktıyı formatla
        sub_reports = result.details.get("reports", [])
        lines = [f"[green]✓ {msg}[/green]" for msg in sub_reports if msg]
        snap_note = ""
        if result.details.get("snapshot"):
            snap_note = "\n[dim]Rollback için: context switch --rollback[/dim]"

        console.print(
            Panel(
                "\n".join(lines) + snap_note if lines else f"[green]✓ Geçiş tamamlandı[/green]{snap_note}",
                title=f"{'🧪 Simülasyon' if dry_run else '✅ Geçiş'} Tamamlandı",
                border_style="yellow" if dry_run else "green",
            )
        )
    else:
        console.print(
            Panel(
                f"[red]✗ {result.message}[/red]",
                title="❌ Geçiş Başarısız",
                border_style="red",
            )
        )
        raise typer.Exit(1)


def app_entry() -> None:
    """pyproject.toml entry point."""
    _fix_encoding()
    app()


if __name__ == "__main__":
    app_entry()
