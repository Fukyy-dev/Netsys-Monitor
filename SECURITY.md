# Kebijakan keamanan

## Model ancaman
Netsys Monitor adalah aplikasi lokal. Secara default server hanya mendengarkan di `127.0.0.1`, memeriksa header `Host`
(melawan DNS rebinding), mewajibkan header `X-Netsys` dan `Origin` yang sama untuk semua aksi (melawan CSRF), dan
membatasi laju aksi berat (traceroute, benchmark DNS, speedtest, pindai).

- `--host 0.0.0.0` (akses dari LAN) **otomatis mewajibkan token** yang tercetak di console; jangan bagikan tautannya.
- Dashboard tidak memakai HTTPS. Jangan membukanya ke internet.
- Tidak ada telemetri. Satu-satunya request keluar: cek IP publik (`api.ipify.org`, bisa dimatikan dengan `--no-public-ip`),
  speedtest (hanya saat Anda menekan tombolnya), dan fitur opsional yang Anda aktifkan sendiri (webhook, cek update).
- File data (`known_devices.json`, `devices.json`, `usage_log.json`) berisi IP/MAC jaringan Anda dan disimpan hanya di folder data lokal.

## Melaporkan kerentanan
Jangan membuka issue publik. Gunakan *Security → Report a vulnerability* di halaman repo GitHub ini (private advisory),
atau hubungi pemelihara lewat email di profil GitHub. Kami berusaha merespons dalam 7 hari.
