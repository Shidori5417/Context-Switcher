# 🧠 Context-Switcher

> Akıllı Çalışma Alanı Mimarı — Tek komutla ortam geçişi

Context-Switcher, gün içinde geçiş yaptığınız çalışma modlarını (Geliştirme, Ders, Eğlence) tek bir komutla tam anlamıyla "yaşayan" bir ortama dönüştüren bir CLI aracıdır.

## ✨ Özellikler

- **Süreç Yönetimi** — Gereksiz uygulamaları dondur, gerekenleri başlat
- **Pencere Düzeni** — Moda uygun pencere yerleşimi
- **Tarayıcı Kontrolü** — Otomatik sekme grupları ve profil geçişi
- **Ses & Bildirim** — Ses seviyesi, bildirim sessizleştirme, otomatik müzik
- **Rollback** — Her geçiş geri alınabilir

## 🚀 Hızlı Başlangıç

### Kurulum

```bash
git clone https://github.com/<kullanici>/context-switcher
cd context-switcher
python -m venv .venv
.venv\Scripts\activate        # Linux/macOS: source .venv/bin/activate
pip install -e ".[dev]"
```

### Kullanım

```bash
context switch dev             # Geliştirme moduna geç
context switch study           # Ders moduna geç
context switch --list          # Modları listele
context switch --status        # Aktif mod durumu
context switch --dry-run dev   # Simülasyon (değişiklik yapmaz)
context switch --rollback      # Son geçişi geri al
```

## 📁 Konfigürasyon

Mod dosyalarını `~/.context-switcher/modes/` dizinine YAML olarak ekleyin:

```yaml
name: "Geliştirme Modu"
icon: "💻"

processes:
  start: [vscode, docker]
  suspend: [discord, steam]

layout:
  arrangement: main-secondary
  primary_app: vscode

browser:
  profile: Work
  tab_groups:
    - name: Docs
      tabs: ["https://docs.python.org"]

environment:
  volume: 40
  music:
    app: spotify
    playlist: "Deep Focus"
```

Örnek dosyalar: [`modes/`](modes/) dizininde.

## 🏗️ Mimari

5 bağımsız agent, olay tabanlı (event-driven) iletişim ile çalışır:

| Agent | Görev |
|-------|-------|
| **Orchestrator** | Geçiş koordinasyonu |
| **Process Manager** | Süreç dondurma/başlatma |
| **Layout Agent** | Pencere düzeni |
| **Browser Agent** | Tarayıcı sekmeleri |
| **Environment Agent** | Ses, bildirim, müzik |

Detaylı mimari: [`agents.md`](agents.md)

## 🧪 Geliştirme

```bash
pytest tests/ -v          # Testleri çalıştır
ruff check src/           # Linter
ruff format src/           # Formatter
```

## 📋 İlerleme Durumu

Detaylı yol haritası: [`progress.md`](progress.md)

## 📄 Lisans

MIT
