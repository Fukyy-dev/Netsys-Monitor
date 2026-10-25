# Uji UI manual (jsdom)
Skrip `live_ui_check.js` memuat dashboard sungguhan dari server yang sedang berjalan dan menjalankan alur Pengaturan/tema/riwayat.
```bash
python -m netsys_monitor --no-browser --port 8794 --no-single --no-tray &
npm i jsdom && node tests/ui/live_ui_check.js http://127.0.0.1:8794/
```
Keluaran harus diakhiri `ERRORS []`. (Belum menjadi bagian CI; lihat docs/PROGRESS.md.)
