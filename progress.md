# 📋 Context-Switcher — progress.md

> Akıllı Çalışma Alanı Mimarı · Geliştirme Yol Haritası & İlerleme Durumu

---

## Proje Durumu Özeti

| Metrik               | Değer                             |
| -------------------- | --------------------------------- |
| **Genel İlerleme**   | %75 — Faz 3 Tamamlandı             |
| **Aktif Faz**        | Faz 4: Yayın & Dağıtım             |
| **Başlangıç Tarihi** | 2026-03-19                          |
| **Hedef MVP Tarihi** | Başlangıçtan +6 hafta             |
| **Platform Hedefi**  | Linux & Windows (macOS ikincil)   |

---

## Faz Haritası (Roadmap)

```
FAZ 0       FAZ 1        FAZ 2         FAZ 3        FAZ 4
Kurulum  →  MVP Core  →  Genişletme →  UX Cilası  →  Yayın
(Hf 1)     (Hf 2-3)     (Hf 4-5)      (Hf 6)       (Hf 7+)
  ●─────────●────────────●─────────────●────────────○▶
[Tamamlandı] [Tamamlandı] [Tamamlandı] [Tamamlandı] [Burada]
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

---

## ✅ Faz 1 — MVP: Temel Çekirdek (Core)

**Süre:** Hafta 2–3  
**Durum:** ✅ Tamamlandı (2026-03-19)

### [F1-A] CLI & Orchestrator

- [x] **[F1-A-01]** `typer` ile CLI iskeleti kuruldu
- [x] **[F1-A-02]** `config_loader.py` — YAML mod dosyaları okuma
- [x] **[F1-A-03]** Orchestrator agent tetikleme sırası
- [x] **[F1-A-04]** `snapshot.py` — Rollback için sistem kaydı
- [x] **[F1-A-05]** `--dry-run` modu simülasyonu

### [F1-B] Process Manager Agent

- [x] **[F1-B-01]** `psutil` süreç listeleme
- [x] **[F1-B-02]** Suspend mekanizması (`SIGSTOP`)
- [x] **[F1-B-03]** Windows desteği (`NtSuspendProcess` entegrasyonu)
- [x] **[F1-B-04]** Protected process listesi
- [x] **[F1-B-05]** Uygulama adından PID bulma
- [x] **[F1-B-06]** Uygulama başlatma (`subprocess`)
- [x] **[F1-B-07]** Kaynak raporu (RAM/CPU okuma)
- [x] **[F1-B-08]** Rollback desteği

### [F1-C] Temel Testler

- [x] **[F1-C-01]** Process Manager birim testleri
- [x] **[F1-C-02]** Config Loader testleri
- [x] **[F1-C-03]** Orchestrator entegrasyon testi

---

## ✅ Faz 2 — Genişletme: Diğer Agent'lar

**Süre:** Hafta 4–5  
**Durum:** ✅ Tamamlandı (2026-03-20)

### [F2-A] Window & Layout Agent

- [x] **[F2-A-01]** `pywin32` (Windows) ve `wmctrl` (Linux) kodlaması
- [x] **[F2-A-02]** Pencere konumu ve boyutu ayarlama
- [x] **[F2-A-03]** Sanal masaüstü desteği
- [x] **[F2-A-04]** Düzen şablonları (`split`, `triple-column`)
- [x] **[F2-A-05]** Mevcut pencere düzenini JSON olarak kaydetme

### [F2-B] Browser Agent

- [x] **[F2-B-01]** Chrome DevTools Protocol (CDP) bağlantısı
- [x] **[F2-B-02]** Sekme yönetimi (açma/kapama)
- [x] **[F2-B-03]** Sekme yedekleme ve geri yükleme

### [F2-C] Notification & Audio Agent

- [x] **[F2-C-01]** `plyer` ile sistem bildirimleri
- [x] **[F2-C-02]** Sistem ses seviyesi kontrolü
- [x] **[F2-C-03]** Spotify URI kontrolü

### [F2-D] Konfigürasyon Wizard'ı

- [x] **[F2-D-01]** `context init` interaktif sihirbazı
- [x] **[F2-D-03]** Örnek YAML şablonları

---

## ✅ Faz 3 — UX Cilası & Sağlamlaştırma (TUI, Tray, Hotkeys, Logging)

**Süre:** Hafta 6  
**Durum:** ✅ Tamamlandı (2026-03-20)

### Görevler

- [x] **[F3-01]** `rich` kütüphanesi ile renkli, animasyonlu CLI çıktısı
- [x] **[F3-02]** Sistem tepsisi (system tray) ikonu — anlık mod göstergesi
- [x] **[F3-03]** Global klavye kısayolu desteği
- [x] **[F3-04]** `context switch --status` -> Aktif mod, askıya alınan süreçler, kurtarılan kaynak
- [x] **[F3-05]** Hata yönetimi iyileştirmeleri (İzole hata yönetimi)
- [x] **[F3-06]** Log sistemi: `~/.context-switcher/logs/` (Rotating logs)
- [x] **[F3-07]** Kapsamlı test coverage (%80+)

**Faz 3 Tamamlanma Kriteri:** ✅ Tüm UX iyileştirmeleri ve sağlamlaştırma adımları tamamlandı, %80+ test kapsamı sağlandı. (2026-03-20)

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
