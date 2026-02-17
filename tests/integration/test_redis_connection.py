"""Integration tests: basic Redis connectivity and key structure on pegasus."""

import pytest


@pytest.mark.integration
@pytest.mark.live
class TestRedisConnection:
    def test_ping(self, live_redis):
        assert live_redis.ping() is True

    def test_users_set_exists(self, live_redis):
        users = live_redis.smembers("vlab:users")
        assert len(users) > 0, "vlab:users set is empty"

    def test_ian_is_overlord(self, live_redis):
        assert live_redis.sismember("vlab:users", "ian"), "User 'ian' not in vlab:users"
        overlord = live_redis.get("vlab:user:ian:overlord")
        assert overlord == "true", f"ian overlord flag is {overlord!r}, expected 'true'"

    def test_port_counter_in_range(self, live_redis):
        port = live_redis.get("vlab:port")
        assert port is not None, "vlab:port key missing"
        assert 30000 <= int(port) <= 35000, f"Port counter {port} out of expected range"

    def test_boardclasses_type(self, live_redis):
        key_type = live_redis.type("vlab:boardclasses")
        assert key_type == "set", f"vlab:boardclasses is {key_type}, expected set"

    def test_boardclasses_not_empty(self, live_redis):
        classes = live_redis.smembers("vlab:boardclasses")
        assert len(classes) > 0, "vlab:boardclasses is empty"
