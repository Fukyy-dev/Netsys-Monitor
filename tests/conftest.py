import json
import os
import tempfile
import threading
from pathlib import Path

import pytest

# Folder data harus ditentukan SEBELUM paket diimpor (DATA_DIR dihitung saat impor)
_TMP = tempfile.mkdtemp(prefix="netsys-test-")
os.environ["NETSYS_DATA"] = _TMP

DATA = Path(__file__).parent / "data"


@pytest.fixture(scope="session")
def data_dir():
    return DATA


@pytest.fixture()
def lhm_json(data_dir):
    def load(name):
        return json.loads((data_dir / name).read_text(encoding="utf-8"))
    return load


@pytest.fixture()
def server():
    """Server HTTP sungguhan di port acak (loopback)."""
    from netsys_monitor import server as srv
    srv.configure_security("127.0.0.1", None, None)
    srv._RATE.clear()
    httpd = srv.Server(("127.0.0.1", 0), srv.Handler)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    yield httpd.server_address[1]
    httpd.shutdown()
    httpd.server_close()
    srv.configure_security("127.0.0.1", None, None)
