# Pemberitahuan pihak ketiga

Netsys Monitor sendiri berlisensi MIT (lihat `LICENSE`). Komponen berikut dipakai/disertakan:

| Komponen | Lisensi | Catatan |
|---|---|---|
| [psutil](https://github.com/giampaolo/psutil) | BSD-3-Clause | dependensi runtime |
| [speedtest-cli](https://github.com/sivel/speedtest-cli) | Apache-2.0 | dependensi runtime (hanya dipakai saat tombol speedtest ditekan) |
| [nvidia-ml-py](https://pypi.org/project/nvidia-ml-py/) | BSD-3-Clause | opsional, pembacaan GPU NVIDIA |
| [pystray](https://github.com/moses-palmer/pystray) | LGPL-3.0-or-later | opsional (ikon tray). Dipakai sebagai pustaka terpisah yang diimpor; pada build `.exe` ia ikut terbungkus oleh PyInstaller, kode sumbernya tersedia di tautan tersebut |
| [Pillow](https://python-pillow.org) | HPND | opsional (menggambar ikon tray) |
| [LibreHardwareMonitor](https://github.com/LibreHardwareMonitor/LibreHardwareMonitor) | MPL-2.0 | **tidak disertakan**; dibaca lewat Remote Web Server/WMI miliknya bila Anda menjalankannya sendiri |
| [Chakra Petch](https://fonts.google.com/specimen/Chakra+Petch) | SIL OFL 1.1 | font di `static/fonts/` (disubset ke Latin). Teks lisensi: `static/fonts/OFL-ChakraPetch.txt` |
| [IBM Plex Sans](https://github.com/IBM/plex) | SIL OFL 1.1 | font di `static/fonts/` (disubset ke Latin). Teks lisensi: `static/fonts/OFL-IBMPlexSans.txt` |
| [PyInstaller](https://pyinstaller.org) | GPL-2.0 dengan pengecualian bootloader | hanya alat build; hasil build tidak terkena GPL |
