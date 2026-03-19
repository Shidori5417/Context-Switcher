@echo off
:: Context-Switcher için UTF-8 Windows başlatıcısı
:: Bu dosyayı kullanarak context komutunu çalıştırın
set PYTHONUTF8=1
.venv\Scripts\context %*
