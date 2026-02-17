"""E2E tests: relay service health checks on pegasus."""

import socket

import pytest


def _tcp_connect(host, port, timeout=5):
    """Attempt a TCP connection, return the socket or raise."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    s.connect((host, port))
    return s


@pytest.mark.e2e
@pytest.mark.live
class TestRelayHealth:
    def test_ssh_port_accepts_connection(self, pegasus_host, ssh_port):
        s = _tcp_connect(pegasus_host, ssh_port)
        s.close()

    def test_ssh_banner(self, pegasus_host, ssh_port):
        s = _tcp_connect(pegasus_host, ssh_port)
        banner = s.recv(256).decode("utf-8", errors="replace")
        s.close()
        assert banner.startswith("SSH-"), f"Unexpected SSH banner: {banner!r}"

    def test_redis_ping(self, pegasus_host, redis_port):
        import redis
        db = redis.Redis(host=pegasus_host, port=redis_port, decode_responses=True)
        assert db.ping() is True

    def test_redis_info(self, pegasus_host, redis_port):
        import redis
        db = redis.Redis(host=pegasus_host, port=redis_port, decode_responses=True)
        info = db.info("server")
        assert "redis_version" in info

    def test_frontail_port(self, pegasus_host):
        """Port 9001 (supervisord/frontail) should accept connections."""
        s = _tcp_connect(pegasus_host, 9001)
        s.close()
