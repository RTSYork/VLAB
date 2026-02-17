"""Integration tests: Redis state invariants (read-only checks on live data)."""

import time

import pytest

from vlabredis import MAX_LOCK_TIME


@pytest.mark.integration
@pytest.mark.live
class TestBoardMetadata:
    def test_registered_boards_have_server_and_port(self, live_redis):
        for bc in live_redis.smembers("vlab:boardclasses"):
            for board in live_redis.smembers(f"vlab:boardclass:{bc}:boards"):
                server = live_redis.get(f"vlab:board:{board}:server")
                port = live_redis.get(f"vlab:board:{board}:port")
                assert server is not None, f"{board} missing server key"
                assert port is not None, f"{board} missing port key"

    def test_known_boards_have_class_and_type(self, live_redis):
        for bc in live_redis.smembers("vlab:boardclasses"):
            for board in live_redis.smembers(f"vlab:boardclass:{bc}:boards"):
                bclass = live_redis.get(f"vlab:knownboard:{board}:class")
                btype = live_redis.get(f"vlab:knownboard:{board}:type")
                assert bclass is not None, f"{board} missing knownboard class"
                assert btype is not None, f"{board} missing knownboard type"

    def test_board_class_membership_consistent(self, live_redis):
        """A board's knownboard class should match the boardclass set it's in."""
        for bc in live_redis.smembers("vlab:boardclasses"):
            for board in live_redis.smembers(f"vlab:boardclass:{bc}:boards"):
                known_class = live_redis.get(f"vlab:knownboard:{board}:class")
                if known_class is not None:
                    assert known_class == bc, (
                        f"{board} in boardclass {bc} but knownboard class is {known_class}"
                    )


@pytest.mark.integration
@pytest.mark.live
class TestSessionInvariants:
    def test_available_boards_have_no_session(self, live_redis):
        for bc in live_redis.smembers("vlab:boardclasses"):
            available = live_redis.zrange(f"vlab:boardclass:{bc}:availableboards", 0, -1)
            for board in available:
                session_user = live_redis.get(f"vlab:board:{board}:session:username")
                assert session_user is None, (
                    f"{board} is available but has session:username={session_user}"
                )

    def test_lock_keys_consistent(self, live_redis):
        """Lock username and time should both be present or both absent."""
        for bc in live_redis.smembers("vlab:boardclasses"):
            for board in live_redis.smembers(f"vlab:boardclass:{bc}:boards"):
                lock_user = live_redis.get(f"vlab:board:{board}:lock:username")
                lock_time = live_redis.get(f"vlab:board:{board}:lock:time")
                if lock_user is not None:
                    assert lock_time is not None, (
                        f"{board} has lock:username but no lock:time"
                    )
                if lock_time is not None:
                    assert lock_user is not None, (
                        f"{board} has lock:time but no lock:username"
                    )

    def test_session_keys_consistent(self, live_redis):
        """Session username, starttime, and pingtime should all be present together."""
        for bc in live_redis.smembers("vlab:boardclasses"):
            for board in live_redis.smembers(f"vlab:boardclass:{bc}:boards"):
                sess_user = live_redis.get(f"vlab:board:{board}:session:username")
                sess_start = live_redis.get(f"vlab:board:{board}:session:starttime")
                sess_ping = live_redis.get(f"vlab:board:{board}:session:pingtime")
                vals = [sess_user, sess_start, sess_ping]
                present = [v for v in vals if v is not None]
                assert len(present) == 0 or len(present) == 3, (
                    f"{board} has incomplete session keys: user={sess_user}, "
                    f"start={sess_start}, ping={sess_ping}"
                )

    def test_no_stale_locks(self, live_redis):
        """No lock should exceed MAX_LOCK_TIME + 2 min grace."""
        now = int(time.time())
        grace = MAX_LOCK_TIME + 120
        for bc in live_redis.smembers("vlab:boardclasses"):
            for board in live_redis.smembers(f"vlab:boardclass:{bc}:boards"):
                lock_time = live_redis.get(f"vlab:board:{board}:lock:time")
                if lock_time is not None:
                    age = now - int(lock_time)
                    assert age <= grace, (
                        f"{board} has stale lock: age={age}s, max={grace}s"
                    )

    def test_no_stale_sessions(self, live_redis):
        """No session pingtime should be more than 90s old."""
        now = int(time.time())
        for bc in live_redis.smembers("vlab:boardclasses"):
            for board in live_redis.smembers(f"vlab:boardclass:{bc}:boards"):
                ping_time = live_redis.get(f"vlab:board:{board}:session:pingtime")
                if ping_time is not None:
                    age = now - int(ping_time)
                    assert age <= 90, (
                        f"{board} has stale session: pingtime age={age}s, max=90s"
                    )
