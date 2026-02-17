"""E2E tests: board server SSH reachability."""

import socket

import pytest


@pytest.mark.e2e
@pytest.mark.live
class TestBoardConnectivity:
    def test_at_least_one_board_registered(self, live_redis):
        total = 0
        for bc in live_redis.smembers("vlab:boardclasses"):
            total += live_redis.scard(f"vlab:boardclass:{bc}:boards")
        assert total > 0, "No boards registered in Redis"

    def test_registered_boards_reachable(self, live_redis, pegasus_host):
        """All registered boards should have reachable SSH ports on pegasus."""
        failures = []
        for bc in live_redis.smembers("vlab:boardclasses"):
            for board in live_redis.smembers(f"vlab:boardclass:{bc}:boards"):
                server = live_redis.get(f"vlab:board:{board}:server")
                port = live_redis.get(f"vlab:board:{board}:port")
                if server is None or port is None:
                    failures.append(f"{board}: missing server/port metadata")
                    continue
                try:
                    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    s.settimeout(5)
                    s.connect((pegasus_host, int(port)))
                    s.close()
                except (socket.error, ValueError) as e:
                    failures.append(f"{board} on {server}:{port}: {e}")
        if failures:
            pytest.fail("Unreachable boards:\n" + "\n".join(failures))
