# 🧠 Context-Switcher — agents.md

> Akıllı Çalışma Alanı Mimarı · Agent Rolleri & Sorumluluklar

---

## Projeye Genel Bakış

Context-Switcher, kullanıcının gün içinde geçiş yaptığı çalışma modlarını (örn: Geliştirme, Ders, Eğlence) tek bir komutla tam anlamıyla "yaşayan" bir ortama dönüştüren bir CLI/masaüstü aracıdır. Klasik scriptlerin ötesinde; süreç yönetimi (process management), uygulama orkestrasyon ve sistem kaynaklarının akıllı kullanımını bir arada sunar.

---

## Agent Mimarisi

Bu proje, birbirinden sorumlu 5 temel agent üzerine kuruludur. Her agent bağımsız çalışabilir ve birbirleriyle olay tabanlı (event-driven) iletişim kurar.

---

### 1. 🎛️ Orchestrator Agent

**Rol:** Komuta Merkezi  
**Dosya:** `src/agents/orchestrator.py`

**Sorumluluklar:**

- Kullanıcıdan gelen mod komutunu (`context switch dev`) alır ve parse eder
- Hangi agent'ların hangi sırayla tetikleneceğini belirler
- Agent'lar arası bağımlılıkları yönetir (örn: Docker başlamadan VS Code açılmasın)
- Geçiş sürecinin başarılı tamamlanıp tamamlanmadığını raporlar
- Hata durumunda rollback (geri alma) koordinasyonunu yapar

**Tetikleyiciler:**

```
context switch <mod_adı>        # Mod geçişi
context switch --list           # Mevcut modları listele
context switch --status         # Aktif mod durumu
context switch --rollback       # Son geçişi geri al
```

**Çıktı:** Her agent'a `SwitchEvent` nesnesi iletir, tamamlanan adımları `progress.log` dosyasına yazar.

---

### 2. ⚙️ Process Manager Agent

**Rol:** Süreç Yöneticisi (Projenin Kalbi)  
**Dosya:** `src/agents/process_manager.py`

**Sorumluluklar:**

- Mevcut çalışan süreçleri listeler ve analiz eder
- Hedef moda **gerekmeyen** süreçleri `SIGSTOP` sinyali ile **dondurur** (öldürmez!)
- Hedef moda **gerekli** süreçleri `SIGCONT` ile **devam ettirir** veya yeniden başlatır
- Her işlem için CPU/RAM maliyetini hesaplar ve kaynak raporu üretir
- Mod değiştirildiğinde dondurulan süreçleri otomatik olarak geri getirir

**Desteklenen İşlemler:**

| İşlem  | Sinyal       | Açıklama                                   |
| ------ | ------------ | ------------------------------------------ |
| Dondur | `SIGSTOP`    | Süreci RAM'de tutar, CPU kullanmaz         |
| Devam  | `SIGCONT`    | Dondurulmuş süreci kaldığı yerden sürdürür |
| Başlat | `subprocess` | Yeni süreç oluşturur                       |
| Kapat  | `SIGTERM`    | Kullanıcı izniyle nazikçe kapatır          |

**Kritik Kural:** Bu agent **hiçbir zaman** sistem süreçlerine (PID < 100) ve kullanıcı tarafından `protected_processes` listesine alınan uygulamalara dokunmaz.

---

### 3. 🪟 Window & Layout Agent

**Rol:** Masaüstü Düzenleyici  
**Dosya:** `src/agents/layout_agent.py`

**Sorumluluklar:**

- Açılan uygulamaların pencere boyutlarını ve konumlarını ayarlar
- Mod'a özgü çoklu monitör düzenini uygular
- Sanal masaüstü (workspace) geçişlerini tetikler
- Uygulama odaklamasını (focus) yönetir — aktif pencereyi öne getirir
- Mevcut pencere düzenini `layouts/<mod>.json` olarak kaydeder

**Desteklenen Pencere Düzenleri:**

```
split-left-right    # Ekranı ikiye böl (sol/sağ)
triple-column       # Üç eşit sütun
main-secondary      # Ana uygulama büyük, yan uygulamalar küçük
fullscreen          # Tek uygulama tam ekran
custom              # Kullanıcı tanımlı koordinatlar
```

**Platform Desteği:**

- Linux: `wmctrl` + `xdotool`
- macOS: `AppleScript` + `Hammerspoon`
- Windows: `pywin32` + PowerShell

---

### 4. 🌐 Browser Agent

**Rol:** Tarayıcı Orkestratörü  
**Dosya:** `src/agents/browser_agent.py`

**Sorumluluklar:**

- Moda özel sekme gruplarını açar/kapatır/arşivler
- Gereksiz sekmeleri kapatmak yerine **sekme grubunu askıya alır** (tarayıcı uyku özelliği)
- Belirli URL'leri otomatik olarak açar (örn: proje dökümantasyonu, Jira board)
- Tarayıcı profilleri arasında geçiş yapabilir (örn: iş profili / kişisel profil)
- Mod değişiminde mevcut açık sekmeleri `sessions/<timestamp>_<mod>.json` olarak yedekler

**Desteklenen Tarayıcılar:**

- Google Chrome / Chromium (Chrome DevTools Protocol)
- Mozilla Firefox (Marionette Protocol)
- Brave Browser

**Örnek Sekme Yapılandırması:**

```yaml
# modes/dev.yaml içinden
browser:
  profile: "Work"
  tab_groups:
    - name: "Docs"
      tabs:
        - "https://docs.python.org"
        - "https://fastapi.tiangolo.com"
    - name: "Project"
      tabs:
        - "https://github.com/myorg/myrepo"
        - "https://linear.app/myteam"
```

---

### 5. 🔔 Notification & Audio Agent

**Rol:** Çevre Yöneticisi  
**Dosya:** `src/agents/environment_agent.py`

**Sorumluluklar:**

- Mod geçişinde belirli uygulamaların bildirimlerini sessize alır veya açar
- Spotify/müzik uygulamasında moda özel çalma listesini başlatır
- Sistem ses seviyesini moda göre ayarlar (örn: Ders modunda düşük, Eğlence'de yüksek)
- "Odak modu" süreçleriyle entegrasyon (Flow, Focus To-Do, vb.)
- Geçiş tamamlandığında kullanıcıya kısa bir sistem bildirimi gönderir

---

## Agent'lar Arası İletişim Akışı

```
Kullanıcı Komutu
      │
      ▼
┌─────────────────┐
│  Orchestrator   │  ← Tüm geçişi yönetir
│     Agent       │
└────────┬────────┘
         │ SwitchEvent (mod_adı, config, önceki_mod)
         │
    ┌────┴──────────────────────────────────┐
    │    Paralel / Sıralı Tetikleme         │
    │                                       │
    ▼                ▼              ▼        ▼
Process          Layout         Browser   Environment
Manager          Agent          Agent       Agent
Agent
    │                │              │        │
    └────────────────┴──────────────┴────────┘
                     │
                     ▼
             StatusReport → Kullanıcı Bildirimi
```

---

## Konfigürasyon Sistemi

Her mod, `~/.context-switcher/modes/` dizininde bir YAML dosyasıyla tanımlanır.

**Örnek: `modes/dev.yaml`**

```yaml
name: "Geliştirme Modu"
icon: "💻"
hotkey: "Ctrl+Alt+D"

processes:
  start:
    - vscode
    - docker
    - "spotify --uri spotify:playlist:xxxxx"
  suspend:
    - discord # Sessize al, kapat değil
    - steam
    - slack # İstersen bildirime izin ver

layout:
  workspace: 2
  arrangement: main-secondary
  primary_app: vscode

browser:
  profile: Work
  restore_session: true
  tab_groups:
    - name: Docs
      tabs: ["https://docs.python.org", "https://hub.docker.com"]

environment:
  volume: 40
  notifications:
    mute: [discord, slack]
    allow: [terminal]
  music:
    app: spotify
    playlist: "Deep Focus"
```

---

## Güvenlik & Kısıtlamalar

- **Root süreçlere dokunulmaz:** Sistem servisleri (systemd, kernel threads) asla hedef alınmaz
- **Protected List:** Kullanıcı `config.yaml` içinde koruma altına alacağı uygulamaları listeleyebilir
- **Dry-Run Modu:** `--dry-run` bayrağıyla gerçek değişiklik yapılmadan ne olacağı simüle edilir
- **Rollback:** Her geçiş öncesi sistem durumu snapshot'ı alınır; `context switch --rollback` ile geri dönülür

---

## Teknoloji Yığını

| Katman            | Teknoloji                            |
| ----------------- | ------------------------------------ |
| CLI Çerçevesi     | Python + `Typer`                     |
| Süreç Yönetimi    | `psutil`, POSIX sinyalleri           |
| Pencere Yönetimi  | `wmctrl`, `xdotool`, `pywin32`       |
| Tarayıcı Kontrolü | Chrome DevTools Protocol, `selenium` |
| Konfigürasyon     | YAML (`PyYAML`)                      |
| Bildirimler       | `plyer`, OS native API               |
| Test              | `pytest` + `pytest-mock`             |
