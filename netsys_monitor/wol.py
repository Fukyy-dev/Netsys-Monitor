"""Wake-on-LAN: kirim magic packet ke perangkat di LAN."""
from __future__ import annotations

import ipaddress
import socket

from .util import MAC_RE, norm_mac


def magic_packet(mac):
    b = bytes.fromhex(norm_mac(mac).replace(":", ""))
    return b"\xff" * 6 + b * 16


def send_wol(mac, subnet=None):
    """Kirim ke broadcast global dan broadcast subnet (jika diketahui). (ok, pesan)."""
    if not MAC_RE.fullmatch(str(mac or "")):
        return False, "MAC tidak valid"
    pkt = magic_packet(mac)
    targets = ["255.255.255.255"]
    try:
        if subnet:
            targets.append(str(ipaddress.ip_network(subnet, strict=False).broadcast_address))
    except ValueError:
        pass
    sent = 0
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        for t in dict.fromkeys(targets):
            for port in (9, 7):
                try:
                    s.sendto(pkt, (t, port))
                    sent += 1
                except OSError:
                    pass
    finally:
        s.close()
    if not sent:
        return False, "Gagal mengirim paket (jaringan tidak tersedia?)"
    return True, "Magic packet terkirim. Perangkat harus mengaktifkan Wake-on-LAN/WoWLAN di BIOS dan adapter."
