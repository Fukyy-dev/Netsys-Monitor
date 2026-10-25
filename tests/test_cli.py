import pytest

from netsys_monitor import __version__
from netsys_monitor.cli import build_parser


def test_defaults_are_safe():
    a = build_parser().parse_args([])
    assert a.host == "127.0.0.1" and a.port == 0 and not a.hosts and a.token is None


def test_version_flag(capsys):
    with pytest.raises(SystemExit):
        build_parser().parse_args(["--version"])
    assert __version__ in capsys.readouterr().out


def test_legacy_no_hosts_flag_still_accepted():
    assert build_parser().parse_args(["--no-hosts"]).no_hosts is True


def test_security_config():
    from netsys_monitor.server import SEC, configure_security
    assert configure_security("127.0.0.1", None, None) is None and not SEC["lan"]
    assert len(configure_security("0.0.0.0", None, None)) >= 16 and SEC["lan"]
    assert configure_security("127.0.0.1", None, "auto")
    assert configure_security("127.0.0.1", None, "rahasia") == "rahasia"
    configure_security("127.0.0.1", None, None)
