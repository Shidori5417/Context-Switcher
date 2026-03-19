# 🧠 Context-Switcher — agents.md

> Akıllı Çalışma Alanı Mimarı · Agent Rolleri & Sorumluluklar

---

## Projeye Genel Bakış

Context-Switcher, kullanıcının gün içinde geçiş yaptığı çalışma modlarını (örn: Geliştirme, Ders, Eğlence) tek bir komutla tam anlamıyla "yaşayan" bir ortama dönüştüren bir CLI/masaüstü aracıdır. Klasik scriptlerin ötesinde; süreç yönetimi (process management), uygulama orkestrasyon ve sistem kaynaklarının akıllı kullanımını bir arada sunar.

---

## Agent Mimarisi

Bu proje, birbirinden sorumlu 5 temel agent üzerine kuruludur. Her agent bağımsız çalışabilir ve **Orchestrator** tarafından yönetilen bir işlem hattı (pipeline) içinde koordineli çalışır.

---

### 1. 🎛️ Orchestrator Agent
**Rol:** Komuta Merkezi  
**Dosya:** `src/agents/orchestrator.py`

**Sorumluluklar:**
- Mod komutlarını parse eder ve koordinasyonu başlatır.
- **İzole Hata Yönetimi:** Kritik olmayan agent hatalarında (örn: Spotify açılmaması) süreci kesmez, kritik hatalarda (örn: Süreç dondurma başarısızlığı) güvenli duruş sağlar.
- **Rollback:** Geçiş başarısız olursa veya kullanıcı talep ederse snapshot üzerinden eski durumu geri yükler.

**Tetikleyiciler:**
```bash
context switch <mod>   # Hızlı mod geçişi
context daemon         # Arka plan servisini (Tray + Hotkeys) başlat
context dashboard      # Canlı TUI izleme panelini aç
```

---

### 2. ⚙️ Process Manager Agent
**Rol:** Süreç Yöneticisi (Projenin Kalbi)  
**Dosya:** `src/agents/process_manager.py`

**Sorumluluklar:**
- **Dondur (SIGSTOP):** Gereksiz süreçleri RAM'de tutar ama CPU kullanımını sıfırlar.
- **Devam Et (SIGCONT):** Dondurulmuş süreçleri anında uyandırır.
- **Akıllı Başlatma:** Uygulama zaten açıksa yeni instance oluşturmaz, sadece odağa alır.
- **Kaynak Analizi:** Her geçiş sonunda "Kazanılan RAM" ve "CPU Tasarrufu" raporlar.

---

### 3. 🪟 Window & Layout Agent
**Rol:** Masaüstü Düzenleyici  
**Dosya:** `src/agents/layout_agent.py`

**Sorumluluklar:**
- Uygulamaları önceden tanımlanmış matrislere (`split`, `triple`, `main`) göre boyutlandırır.
- **Windows (pywin32):** WinAPI üzerinden pencere handle'larını yönetir.
- **Linux (wmctrl):** X11 üzerinden pencere konumlandırması yapar.

---

### 4. 🌐 Browser Agent
**Rol:** Tarayıcı Orkestratörü  
**Dosya:** `src/agents/browser_agent.py`

**Sorumluluklar:**
- **CDP Entegrasyonu:** Chrome/Brave gibi tarayıcılarla Remote Debugging üzerinden konuşur.
- **Sekme Grupları:** Tek bir URL yerine, projeyle ilgili tüm tab'leri gruplanmış halde açar.
- **Oturum Yönetimi:** Mod kapatıldığında açık sekmeleri JSON olarak yedekler.

---

### 5. 🔔 Notification & Environment Agent
**Rol:** Çevre Yöneticisi  
**Dosya:** `src/agents/environment_agent.py`

**Sorumluluklar:**
- **Ses Kontrolü:** Sistem sesini ve Spotify playlist'lerini yönetir.
- **Bildirimler:** Rahatsız etmeyin modunu tetikler veya önemli uygulamalara izin verir.
- **Görsel Bildirimler:** Geçiş tamamlandığında sistem tepsisi üzerinden durum iletir.

---

## 🚀 Ekosistem ve Kullanıcı Arayüzü

### 📺 TUI Dashboard (`src/tui.py`)
Kullanıcılar `context dashboard` komutuyla yaşayan bir panel açabilir. Bu panelde:
- Aktif modun durumu.
- Dondurulan süreçlerin listesi.
- Sistem kaynak tüketimi (Canlı grafikler) izlenebilir.

### 🍷 System Tray & Hotkeys (`src/daemon.py`)
`context daemon` komutu arka planda çalışarak:
- **Tray Icon:** Sağ tık menüsüyle hızlı mod değişimi sağlar.
- **Global Hotkeys:** YAML dosyasında tanımlanan `ctrl+alt+d` gibi kombinasyonları sistem genelinde dinler.

---

## 🛠️ Teknoloji Yığını

| Katman | Teknoloji |
| :--- | :--- |
| **CLI & TUI** | `Typer` + `Rich` + `Textual` |
| **Arka Plan Servisi** | `pystray` + `keyboard` |
| **Süreç Yönetimi** | `psutil` |
| **Tarayıcı Kontrolü** | `CDP` (Chrome DevTools) + `requests` |
| **Windows API** | `pywin32` + `comtypes` + `pycaw` |
| **Linux API** | `wmctrl` + `sh` |
| **Konfigürasyon** | `PyYAML` + `jsonschema` |

---

## Güvenlik & Kısıtlamalar
- **Protected List:** `explorer.exe`, `taskmgr.exe` gibi kritik süreçler asla dondurulmaz.
- **Failsafe:** Herhangi bir agent çökerse Orchestrator durumu `progress.log`'a yazar ve sistemi tutarlı bir halde bırakır.
