# Progress & rencana (catatan kerja; boleh dihapus sebelum publikasi)

Dokumen ini supaya pekerjaan bisa dilanjutkan di sesi berikutnya tanpa mengulang.
Tanda: [x] selesai & teruji di sandbox Linux, [~] selesai tetapi BELUM diuji di Windows asli, [ ] belum.

## Fase 1: siap GitHub
- [x] Pecah monolit 4.4k baris menjadi paket `netsys_monitor/` (16 modul, tanpa impor siklik) + UI statis (index.html/style.css/app.js)
- [x] Font di-host sendiri (woff2 subset, OFL), tidak ada request ke Google Fonts
- [x] Default aman: 127.0.0.1:8765, hosts file opsional (`--hosts`), cek Host/Origin, token otomatis untuk LAN, rate limit, CSP/header keamanan
- [x] Logging berputar (netsys.log), `--log-level`
- [x] Tes pytest (56): parser netsh/nmcli/tracert/LHM (sampel asli), DNS vs server palsu, penjaga WiFi, alert, server (keamanan, statis, token)
- [x] Bug nyata ditemukan tes: `0.004 V` terbaca `4` (sudah diperbaiki)
- [x] pyproject.toml, requirements, LICENSE (MIT, ganti nama pemegang hak cipta!), .gitignore, README EN+ID, CHANGELOG, SECURITY, CONTRIBUTING, THIRD_PARTY_NOTICES, templat issue/PR, dependabot
- [x] CI (lint+tes Win/Linux, py3.9/3.12, node --check, build exe) dan workflow rilis (exe + installer + SHA256)
- [x] Spec PyInstaller (diuji: build Linux + binary menyajikan file statis)
- [~] Skrip installer Inno Setup (`packaging/installer.iss`) belum pernah dikompilasi
- [~] Workflow GitHub Actions belum pernah dijalankan di GitHub (kemungkinan perlu penyesuaian kecil)
- [ ] Screenshot asli (butuh dijepret di Windows, lihat docs/screenshots/README.md)
- [ ] Code signing .exe (butuh sertifikat berbayar; alternatif: SignPath untuk OSS)

## Fase 2: fitur
- [x] Pengaturan persisten + validasi (tema, jam tenang, ambang per metrik, webhook, mode hemat) + dialog UI
- [x] Tema gelap (variabel + blok otomatis `tools/gen_dark_css.py`); [~] BELUM pernah dilihat secara visual (tidak ada browser di sandbox)
- [x] Webhook Discord/Telegram/JSON + tombol tes + jam tenang + batas 6/menit; rahasia tidak pernah keluar dari API
- [x] Riwayat SQLite (metrik/menit, kejadian, log perangkat), grafik 6 jam-30 hari, ekspor CSV/JSON
- [x] Vendor MAC (OUI IEEE diunduh atas permintaan; tidak dibundel karena sumber/lisensi) + Wake-on-LAN
- [x] Deteksi MAC gateway berubah (per SSID+subnet) + tombol "Percayai gateway baru"
- [x] Cek update GitHub (opsional); [ ] `GITHUB_REPO` di `updater.py` harus diisi setelah repo ada
- [x] Mode hemat (slow_loop 3 dtk jadi 12 dtk bila UI tidak meminta data >30 dtk)
- [x] Aksesibilitas dasar (ARIA otomatis, :focus-visible, aria-live); [ ] audit kontras/keyboard penuh dengan alat (axe/Lighthouse)
- [x] Tes: 80 tes pytest; UI diuji end-to-end via jsdom saat pengembangan (skrip belum masuk repo)
- [ ] i18n ID/EN untuk UI (string masih Indonesia; README sudah dua bahasa)
- [ ] Bandwidth per aplikasi (psutil tidak punya I/O jaringan per proses; butuh ETW/WFP di Windows)
- [ ] Deteksi duplikat IP/ARP spoofing selain perubahan MAC gateway (rawan false positive di jaringan mesh/proxy-ARP)
- [ ] Tes UI otomatis di CI (Playwright) dan screenshot otomatis
- [ ] Code signing; screenshot asli; uji manual Windows (lihat docs/RELEASING.md)

## Cara melanjutkan di sesi baru
Unggah zip repo ini lalu katakan "lanjutkan docs/PROGRESS.md". Mulai dari item `[ ]` teratas; jalankan `ruff check . && pytest` sebelum dan sesudah.
