# 📋 Context-Switcher — progress.md

> Akıllı Çalışma Alanı Mimarı · Geliştirme Yol Haritası & İlerleme Durumu

---

## Proje Durumu Özeti

| Metrik               | Değer                             |
| -------------------- | --------------------------------- |
| **Genel İlerleme**   | %15 — Faz 0 Tamamlandı             |
| **Aktif Faz**        | Faz 1: MVP Core                    |
| **Başlangıç Tarihi** | 2026-03-19                          |
| **Hedef MVP Tarihi** | Başlangıçtan +6 hafta             |
| **Platform Hedefi**  | Linux önce, macOS & Windows sonra |

---

## Faz Haritası (Roadmap)

```
FAZ 0       FAZ 1        FAZ 2         FAZ 3        FAZ 4
Kurulum  →  MVP Core  →  Genişletme →  UX Cilası  →  Yayın
(Hf 1)     (Hf 2-3)     (Hf 4-5)      (Hf 6)       (Hf 7+)
  ●─────────●────────────────────────────────────────▶
[Tamamlandı] [Burada]
```

---

## ✅ Faz 0 — Proje Kurulumu & Mimari Tasarım

**Süre:** Hafta 1  
**Durum:** ✅ Tamamlandı (2026-03-19)

### Görevler

- [x] **[F0-01]** Proje dizin yapısı oluşturuldu *(2026-03-19)*

  ```
  context-switcher/
  ├── src/
  │   ├── agents/
  │   │   ├── base_agent.py
  │   │   ├── orchestrator.py
  │   │   ├── process_manager.py
  │   │   ├── layout_agent.py
  │   │   ├── browser_agent.py
  │   │   └── environment_agent.py
  │   ├── core/
  │   │   ├── config_loader.py
  │   │   ├── event_bus.py
  │   │   └── snapshot.py
  │   └── cli.py
  ├── modes/
  │   ├── dev.yaml.example
  │   ├── study.yaml.example
  │   └── gaming.yaml.example
  ├── schema/
  │   └── mode_schema.json
  ├── tests/
  ├── agents.md
  ├── progress.md
  └── README.md
  ```

- [x] **[F0-02]** `pyproject.toml` hazırlandı *(2026-03-19)*
  - Bağımlılıklar: `typer`, `psutil`, `PyYAML`, `plyer`, `rich`, `jsonschema`
- [x] **[F0-03]** Temel `Event Bus` (olay yöneticisi) tasarlandı *(2026-03-19)*
  - Agent'lar arası mesaj iletişim protokolü
  - `SwitchEvent` ve `StatusReport` veri yapıları

- [x] **[F0-04]** YAML konfigürasyon şeması (`mode_schema.json`) tanımlandı *(2026-03-19)*
  - Geçersiz mod dosyalarını başlatmadan yakala

- [x] **[F0-05]** Geliştirme ortamı kuruldu *(2026-03-19)* (`venv`, ruff, pre-commit hooks)

- [x] **[F0-06]** `agents.md`, `progress.md` ve `README.md` yazıldı ✅

**Faz 0 Tamamlanma Kriteri:** ✅ `context switch --help` komutu çalışıyor ve YAML dosyası okunabiliyor.

---

## ✅ Faz 1 — MVP: Temel Çekirdek (Core)

**Süre:** Hafta 2–3  
**Durum:** ✅ Tamamlandı (2026-03-19)

### Hedef

Kullanıcı `context switch dev` yazdığında; terminal bunu anlasın, YAML'dan modu okusun ve en az **Process Manager** ile **Orchestrator** çalışsın.

---

### [F1-A] CLI & Orchestrator

- [ ] **[F1-A-01]** `typer` ile CLI iskeleti kurulacak

  ```bash
  context switch <mod>          # ✓
  context switch --list         # ✓
  context switch --status       # ✓
  context switch --dry-run <mod># ✓
  context switch --rollback     # ✓
  ```

- [ ] **[F1-A-02]** `config_loader.py` — YAML mod dosyalarını okuyup doğrulayan modül

- [ ] **[F1-A-03]** Orchestrator'ın agent tetikleme sırası belirlenmeli:
  1. Snapshot al (rollback için)
  2. Process Manager → (suspend işlemleri)
  3. Process Manager → (start işlemleri)
  4. Layout Agent
  5. Browser Agent
  6. Environment Agent
  7. Bildirim gönder

- [ ] **[F1-A-04]** `snapshot.py` — Geçiş öncesi sistem durumunu kaydet (JSON)

- [ ] **[F1-A-05]** `--dry-run` modu: Gerçek değişiklik yapmadan simülasyon çıktısı

---

### [F1-B] Process Manager Agent

- [ ] **[F1-B-01]** `psutil` ile tüm kullanıcı süreçlerini listele

- [ ] **[F1-B-02]** Suspend mekanizması (`SIGSTOP`) — Linux/macOS

  ```python
  process.suspend()   # psutil.Process.suspend()
  process.resume()    # psutil.Process.resume()
  ```

- [ ] **[F1-B-03]** Windows desteği için `NtSuspendProcess` / `NtResumeProcess` araştırılacak

- [ ] **[F1-B-04]** Protected process listesi kontrolü

- [ ] **[F1-B-05]** Uygulama adından PID bulma (örn: `"discord"` → PID listesi)
  - Hem süreç adı hem de executable path eşleştirmesi

- [ ] **[F1-B-06]** Uygulama başlatma (subprocess) — YAML'daki `start` listesi için

- [ ] **[F1-B-07]** Kaynak raporu: Suspend edilen süreçlerden ne kadar RAM/CPU kurtarıldı

- [ ] **[F1-B-08]** Rollback: Snapshot'tan önceki durumu geri yükle

---

### [F1-C] Temel Testler

- [ ] **[F1-C-01]** Process Manager için birim testleri (mock psutil)
- [ ] **[F1-C-02]** Config Loader için YAML validasyon testleri
- [ ] **[F1-C-03]** Orchestrator entegrasyon testi (sahte agent'larla)

**Faz 1 Tamamlanma Kriteri:** `context switch dev` → Discord dondurulur, VS Code başlar. `context switch --rollback` → Discord geri döner.

---

## 🔲 Faz 2 — Genişletme: Diğer Agent'lar

**Süre:** Hafta 4–5  
**Durum:** 🔲 Başlamadı

### [F2-A] Window & Layout Agent

- [ ] **[F2-A-01]** Linux'ta `wmctrl` / `xdotool` entegrasyonu
- [ ] **[F2-A-02]** Pencere konumu ve boyutu ayarlama
- [ ] **[F2-A-03]** Sanal masaüstü (workspace) geçişi
- [ ] **[F2-A-04]** Düzen şablonları (`split`, `triple-column`, `main-secondary`)
- [ ] **[F2-A-05]** Mevcut pencere düzenini YAML/JSON olarak kaydetme
- [ ] **[F2-A-06]** macOS AppleScript desteği (ikincil öncelik)
- [ ] **[F2-A-07]** Çoklu monitör desteği

---

### [F2-B] Browser Agent

- [ ] **[F2-B-01]** Chrome DevTools Protocol (CDP) bağlantısı
  - Chrome'u `--remote-debugging-port=9222` ile başlatma
- [ ] **[F2-B-02]** Sekme açma, kapatma, gruplama

- [ ] **[F2-B-03]** Sekme grubunu "askıya alma" (Tab Group suspend)

- [ ] **[F2-B-04]** Mevcut sekmeleri `sessions/` klasörüne yedekleme (JSON)

- [ ] **[F2-B-05]** Tarayıcı profili geçişi

- [ ] **[F2-B-06]** Firefox Marionette desteği (opsiyonel)

---

### [F2-C] Notification & Audio Agent

- [ ] **[F2-C-01]** `plyer` ile cross-platform bildirim sessizleştirme
- [ ] **[F2-C-02]** Linux `pactl` / macOS `osascript` ile ses seviyesi kontrolü
- [ ] **[F2-C-03]** Spotify API ile çalma listesi başlatma (OAuth token yönetimi)
- [ ] **[F2-C-04]** Spotify Desktop uygulama kontrolü (D-Bus / AppleScript)
- [ ] **[F2-C-05]** Geçiş tamamlandı bildirimi (sistem toast bildirimi)

---

### [F2-D] Konfigürasyon Wizard'ı

- [ ] **[F2-D-01]** `context switch init` komutuyla interaktif mod oluşturucu
- [ ] **[F2-D-02]** Çalışan süreçleri listeleyen mod asistanı: "Bu uygulamayı moda eklemek ister misiniz?"
- [ ] **[F2-D-03]** Örnek YAML şablonları (`dev`, `study`, `gaming`)

**Faz 2 Tamamlanma Kriteri:** Tüm 5 agent çalışıyor. `context switch study` → Tam ortam geçişi yapılıyor (pencere, tarayıcı, ses, süreçler).

---

## 🔲 Faz 3 — UX Cilası & Sağlamlaştırma

**Süre:** Hafta 6  
**Durum:** 🔲 Başlamadı

- [ ] **[F3-01]** `rich` kütüphanesi ile renkli, animasyonlu CLI çıktısı

  ```
  🔄 Context-Switcher: dev moduna geçiliyor...
  ✅ Discord donduruldu      (RAM tasarrufu: 412 MB)
  ✅ VS Code başlatıldı
  ✅ Tarayıcı sekmeleri yüklendi
  ✅ Spotify: Deep Focus çalıyor
  ─────────────────────────────
  ⚡ Geçiş tamamlandı (2.3 sn)
  ```

- [ ] **[F3-02]** Sistem tepsisi (system tray) ikonu — anlık mod göstergesi

- [ ] **[F3-03]** Global klavye kısayolu desteği
  - Linux: `keyboard` veya `xbindkeys`
  - macOS: Hammerspoon
  - Windows: AutoHotkey entegrasyonu

- [ ] **[F3-04]** `context switch --status` → Aktif mod, askıya alınan süreçler, kurtarılan kaynak

- [ ] **[F3-05]** Hata yönetimi iyileştirmeleri
  - Uygulama bulunamadığında anlaşılır hata mesajları
  - Kısmi hata durumunda diğer agent'ların çalışmaya devam etmesi

- [ ] **[F3-06]** Log sistemi: `~/.context-switcher/logs/` — her geçiş kaydedilir

- [ ] **[F3-07]** Kapsamlı test coverage (%80+)

**Faz 3 Tamamlanma Kriteri:** Hiçbir Python traceback görmeden tüm hata senaryoları düzgün yönetiliyor. CLI çıktısı anlaşılır ve bilgilendirici.

---

## 🔲 Faz 4 — Yayın & Dağıtım

**Süre:** Hafta 7+  
**Durum:** 🔲 Başlamadı

- [ ] **[F4-01]** PyPI paketi olarak yayınla (`pip install context-switcher`)
- [ ] **[F4-02]** Homebrew formula (macOS)
- [ ] **[F4-03]** `.deb` / `.rpm` paketleri (Linux)
- [ ] **[F4-04]** GitHub Actions CI/CD pipeline
- [ ] **[F4-05]** Kapsamlı README + dokümantasyon sitesi
- [ ] **[F4-06]** Demo video & GIF'ler

---

## 🐛 Bilinen Sorunlar & Riskler

| #   | Risk                                                                               | Olasılık | Etki   | Çözüm Planı                                                                       |
| --- | ---------------------------------------------------------------------------------- | -------- | ------ | --------------------------------------------------------------------------------- |
| R1  | `SIGSTOP` ile dondurulan bazı uygulamalar (Electron tabanlı) tutarsız davranabilir | Orta     | Yüksek | Her uygulama için test; sorunlu olanlar için `protected_list`'e alma seçeneği sun |
| R2  | Chrome CDP bağlantısı her zaman açık olmayabilir                                   | Orta     | Orta   | Chrome başlatılırken otomatik `--remote-debugging-port` ekleme                    |
| R3  | Windows'ta POSIX sinyalleri çalışmaz                                               | Yüksek   | Yüksek | `NtSuspendProcess` WinAPI ile alternatif implementasyon                           |
| R4  | Spotify API rate limiting                                                          | Düşük    | Düşük  | D-Bus/AppleScript ile doğrudan uygulama kontrolü (API bypass)                     |
| R5  | Kullanıcı yanlış YAML yazarsa anlaşılmaz hata                                      | Yüksek   | Orta   | Faz 0'da JSON Schema validasyonu                                                  |

---

## 💡 Gelecek Fikirler (Backlog)

- **Otomatik Mod Algılama:** Saate göre otomatik geçiş (09:00 → Dev, 22:00 → Eğlence)
- **Uygulama Kullanım Takibi:** "Bu hafta Dev modunda 34 saat geçirdin"
- **Bulut Senkronizasyonu:** Mod konfigürasyonlarını cihazlar arasında paylaş
- **Eklenti Sistemi:** Topluluk tarafından yazılan agent'lar
- **AI Mod Önerisi:** Takvim etkinliklerine bakarak mod öneren asistan
- **GUI Konfigürasyon Editörü:** YAML bilmeyenler için görsel arayüz

---

## 📝 Geliştirici Notları

### Bu Dosyayı Güncelleme Kuralları

1. Bir görev tamamlandığında `- [ ]` → `- [x]` yapın ve tarihi ekleyin: `- [x] **[F1-B-01]** *(2025-01-15)*`
2. Yeni keşfedilen görevler için Backlog'a ekleyin, Faz içine değil
3. Her Faz bitiminde "Faz Tamamlanma Tarihi" ve öğrenilen dersleri buraya yazın
4. Risk tablosu her hafta gözden geçirilmeli

### Ortam Kurulumu (Geliştirici İçin)

```bash
git clone https://github.com/<kullanici>/context-switcher
cd context-switcher
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
context switch --help       # Çalıştığını doğrula
```
