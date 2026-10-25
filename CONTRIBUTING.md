# Berkontribusi

```bash
git clone <repo> && cd netsys-monitor
python -m venv .venv && . .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
ruff check . && pytest
python -m netsys_monitor --tab                        # jalankan lokal
```

## Struktur
Lihat [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md). Backend ada di `netsys_monitor/*.py`, UI statis di `netsys_monitor/static/`.

## Aturan singkat
- Parser (netsh, tracert, LibreHardwareMonitor) harus punya tes dengan sampel nyata di `tests/data/` (hapus data pribadi).
- Jangan menambah dependensi berat tanpa alasan kuat; jangan menambah request jaringan keluar tanpa opsi mematikannya.
- UI tidak boleh memakai skrip/font dari CDN (CSP `script-src 'self'`).
- Perubahan yang terlihat pengguna dicatat di `CHANGELOG.md`.
