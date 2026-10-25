# Changelog
Format mengikuti [Keep a Changelog](https://keepachangelog.com/id/1.1.0/); versi mengikuti SemVer.

## [Unreleased]
- Lihat `docs/PROGRESS.md` untuk daftar pekerjaan yang masih terbuka.

## [2.3.0]
### Ditambahkan
- **Pengaturan** (ikon gerigi): tema Terang/Gelap/Ikuti Windows, jam tenang, ambang peringatan per metrik, mode hemat; tersimpan di `settings.json`.
- **Webhook**: kirim peringatan kritis/perangkat asing ke Discord, Telegram, atau URL JSON; tombol tes; rahasia tidak pernah dikembalikan ke UI.
- **Riwayat** (SQLite, 30 hari): grafik CPU/RAM/latency/WiFi 6 jam-30 hari, log kejadian dan aksi perangkat; ekspor CSV/JSON.
- **Vendor MAC** (database OUI IEEE, diunduh atas permintaan) dan **Wake-on-LAN** di Penjaga WiFi.
- **Deteksi perubahan MAC gateway** (router diganti atau ARP spoofing) per SSID+subnet.
- Cek versi baru GitHub (opsional, mati secara default) dengan banner pembaruan.
- Mode hemat: proses/disk/koneksi dibaca jauh lebih jarang bila dashboard tidak dibuka.
- Aksesibilitas: label ARIA otomatis pada tombol ikon, indikator fokus, region `aria-live`.
### Berubah
- Folder data default sekarang per-pengguna (`%LOCALAPPDATA%/NetsysMonitor`, `~/.local/share/netsys-monitor`); data lama di samping skrip disalin otomatis sekali.
- Notifikasi desktop dipusatkan di `notify.py` (tray hanya sebagai kanal).

## [2.2.0]
### Ditambahkan
- Penjaga WiFi: deteksi perangkat asing (MAC baru) lewat pindai ARP berkala, daftar per jaringan, tombol Percayai/Tandai asing/Hapus/Reset.
- Info WiFi PC ini (sinyal, band, channel, link, BSSID) lewat `netsh wlan` / `nmcli`, plus peringatan sinyal lemah.
- Traceroute dan benchmark DNS (tanpa cache vs cache) di tab Jaringan.
- Suhu/fan CPU dan data GPU (VRAM, suhu, daya, fan, clock; iGPU + dGPU) lewat LibreHardwareMonitor (web server + cadangan WMI).
- Ikon system tray (tooltip live, notifikasi), auto-start Windows (HKCU), build `.exe` PyInstaller, instance tunggal dan fokus ke jendela yang sudah terbuka.
- Animasi splash, judul jendela memuat jumlah peringatan.
### Berubah (breaking)
- Kode dipecah menjadi paket `netsys_monitor/` dengan UI statis; jalankan dengan `python -m netsys_monitor` atau perintah `netsys-monitor`.
- Port default sekarang **8765** (bukan 80) dan hosts file **tidak lagi diubah secara default** (opsi `--hosts`).
- `--host 0.0.0.0` otomatis mewajibkan token. Server memeriksa `Host`/`Origin` dan membatasi laju aksi berat.
- Font di-host sendiri; tidak ada lagi request ke Google Fonts.
### Diperbaiki
- Nilai sensor seperti `0.004 V` tidak lagi salah terbaca sebagai `4` (heuristik pemisah ribuan LibreHardwareMonitor).
