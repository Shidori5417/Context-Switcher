"""Config Wizard — İnteraktif mod oluşturucu."""

from __future__ import annotations

from pathlib import Path

import psutil
import typer
import yaml
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()

MODES_DIR = Path.home() / ".context-switcher" / "modes"

# Desteklenen düzen şablonları
ARRANGEMENTS = ["split-left-right", "main-secondary", "fullscreen", "triple-column", "custom"]


def run_wizard() -> None:
    """İnteraktif mod oluşturma sihirbazı."""
    console.print(
        Panel(
            "[bold cyan]Context-Switcher[/bold cyan] — Yeni mod oluşturma sihirbazı\n"
            "[dim]Çıkmak için Ctrl+C[/dim]",
            title="✨ Mod Sihirbazı",
            border_style="cyan",
        )
    )

    # 1. Temel bilgiler
    mode_name: str = typer.prompt("Mod adı (örn: dev, study, gaming)")
    mode_name = mode_name.strip().lower().replace(" ", "-")

    display_name: str = typer.prompt(
        "Görüntülenen ad", default=mode_name.capitalize()
    )
    icon: str = typer.prompt("İkon (emoji, opsiyonel)", default="")
    hotkey: str = typer.prompt("Klavye kısayolu (opsiyonel, örn: Ctrl+Alt+D)", default="")

    config: dict = {"name": display_name}
    if icon:
        config["icon"] = icon
    if hotkey:
        config["hotkey"] = hotkey

    # 2. Çalışan süreçler
    console.print("\n[bold]Çalışan Süreçler[/bold] (hang uygulamaları bu modda donduracaksın?)")
    running = _list_user_processes()

    suspend_list: list[str] = []
    start_list: list[str] = []

    if running:
        table = Table(show_lines=True, title="Çalışan Uygulamalar")
        table.add_column("#", style="dim", width=4)
        table.add_column("Uygulama", style="cyan")
        table.add_column("RAM", style="yellow")
        for i, (name, mem) in enumerate(running, 1):
            table.add_row(str(i), name, f"{mem} MB")
        console.print(table)

        raw = typer.prompt(
            "Dondurulacak uygulama adları (virgülle ayır, boş bırak = yok)",
            default="",
        )
        suspend_list = [s.strip() for s in raw.split(",") if s.strip()]

    raw_start = typer.prompt(
        "Başlatılacak uygulamalar (virgülle ayır, boş bırak = yok)", default=""
    )
    start_list = [s.strip() for s in raw_start.split(",") if s.strip()]

    if suspend_list or start_list:
        config["processes"] = {}
        if suspend_list:
            config["processes"]["suspend"] = suspend_list
        if start_list:
            config["processes"]["start"] = start_list

    # 3. Pencere düzeni
    console.print("\n[bold]Pencere Düzeni[/bold]")
    want_layout = typer.confirm("Pencere düzeni eklemek ister misin?", default=False)
    if want_layout:
        console.print("Seçenekler: " + ", ".join(ARRANGEMENTS))
        arrangement = typer.prompt("Düzen şablonu", default="main-secondary")
        primary_app = typer.prompt("Ana uygulama (opsiyonel)", default="")
        workspace = typer.prompt("Sanal masaüstü numarası", default="1")

        layout: dict = {"arrangement": arrangement}
        if primary_app:
            layout["primary_app"] = primary_app
        try:
            layout["workspace"] = int(workspace)
        except ValueError:
            pass
        config["layout"] = layout

    # 4. Tarayıcı
    want_browser = typer.confirm("\nTarayıcı sekmeleri eklemek ister misin?", default=False)
    if want_browser:
        profile = typer.prompt("Tarayıcı profili (opsiyonel)", default="")
        raw_tabs = typer.prompt("Açılacak URL'ler (virgülle ayır)")
        tab_urls = [u.strip() for u in raw_tabs.split(",") if u.strip()]

        browser: dict = {}
        if profile:
            browser["profile"] = profile
        if tab_urls:
            browser["tab_groups"] = [{"name": "Main", "tabs": tab_urls}]
        browser["restore_session"] = typer.confirm("Önceki oturumu geri yükle?", default=True)
        config["browser"] = browser

    # 5. Çevre ayarları
    want_env = typer.confirm("\nSes ve müzik ayarları eklemek ister misin?", default=False)
    if want_env:
        volume_raw = typer.prompt("Ses seviyesi (0-100)", default="")
        playlist = typer.prompt("Spotify çalma listesi adı veya URI (opsiyonel)", default="")

        env: dict = {}
        if volume_raw.isdigit():
            env["volume"] = int(volume_raw)
        if playlist:
            env["music"] = {"app": "spotify", "playlist": playlist}
        if env:
            config["environment"] = env

    # 6. YAML'ı yaz
    MODES_DIR.mkdir(parents=True, exist_ok=True)
    output_path = MODES_DIR / f"{mode_name}.yaml"

    if output_path.exists():
        overwrite = typer.confirm(
            f"'{output_path}' zaten var. Üzerine yaz?", default=False
        )
        if not overwrite:
            console.print("[yellow]İptal edildi.[/yellow]")
            raise typer.Exit()

    output_path.write_text(
        yaml.dump(config, allow_unicode=True, default_flow_style=False),
        encoding="utf-8",
    )

    console.print(
        Panel(
            f"[green]✓ Mod oluşturuldu:[/green] [bold]{output_path}[/bold]\n\n"
            f"Kullanım: [cyan]context switch {mode_name}[/cyan]",
            title="✅ Tamamlandı",
            border_style="green",
        )
    )


def _list_user_processes(limit: int = 20) -> list[tuple[str, float]]:
    """En çok RAM kullanan kullanıcı süreçlerini listeler."""
    procs: list[tuple[str, float]] = []
    seen: set[str] = set()
    skip = {"system", "idle", "registry", "smss.exe", "csrss.exe",
            "wininit.exe", "services.exe", "lsass.exe", "python.exe",
            "python3", "python", "conhost.exe"}

    for proc in psutil.process_iter(["name", "memory_info"]):
        try:
            name = (proc.info["name"] or "").lower()
            if name in skip or name in seen:
                continue
            mem_mb = round(proc.info["memory_info"].rss / 1024 / 1024, 1)
            if mem_mb < 5:
                continue
            seen.add(name)
            procs.append((name, mem_mb))
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    return sorted(procs, key=lambda x: x[1], reverse=True)[:limit]
