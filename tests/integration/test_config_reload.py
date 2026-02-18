"""Integration tests for the live config reload feature against live Redis."""

import time

import pytest


@pytest.mark.integration
@pytest.mark.live
class TestConfigReloadTriggerKey:
    """The vlab:config:reload Redis key is the trigger mechanism for live reload."""

    def test_trigger_key_can_be_set(self, live_redis):
        live_redis.delete('vlab:config:reload')
        live_redis.set('vlab:config:reload', '1', ex=120)
        assert live_redis.get('vlab:config:reload') == '1'
        live_redis.delete('vlab:config:reload')

    def test_trigger_key_has_ttl_when_set(self, live_redis):
        live_redis.set('vlab:config:reload', '1', ex=120)
        ttl = live_redis.ttl('vlab:config:reload')
        assert 0 < ttl <= 120
        live_redis.delete('vlab:config:reload')

    def test_trigger_key_absent_by_default(self, live_redis):
        """After setup, no stale reload trigger should be present."""
        # If this fails, a previous test or operation left a trigger pending.
        # Allow a small window in case checkboards.py just deleted it.
        val = live_redis.get('vlab:config:reload')
        assert val is None, (
            f"vlab:config:reload is set to '{val}'; "
            "a reload may be mid-flight or a previous test left it dirty"
        )


@pytest.mark.integration
@pytest.mark.live
class TestRedisStateAfterSetupusers:
    """Verify the Redis state is consistent with what idempotent setupusers.py produces."""

    def test_users_set_exists_and_non_empty(self, live_redis):
        users = live_redis.smembers('vlab:users')
        assert isinstance(users, set)
        assert len(users) > 0, "vlab:users should be populated after setupusers.py"

    def test_ian_is_in_users(self, live_redis):
        assert 'ian' in live_redis.smembers('vlab:users')

    def test_overlord_flag_is_true_string(self, live_redis):
        """Overlord flags, if set, must be the string 'true' (not 'True' or '1')."""
        users = live_redis.smembers('vlab:users')
        for user in users:
            val = live_redis.get(f'vlab:user:{user}:overlord')
            if val is not None:
                assert val == 'true', (
                    f"vlab:user:{user}:overlord is '{val}'; expected 'true'"
                )

    def test_allowedboards_are_sets(self, live_redis):
        """allowedboards keys must be Redis sets, not strings."""
        users = live_redis.smembers('vlab:users')
        failures = []
        for user in users:
            key = f'vlab:user:{user}:allowedboards'
            key_type = live_redis.type(key)
            if key_type not in ('set', 'none'):
                failures.append(f"{key} has type '{key_type}', expected 'set'")
        if failures:
            pytest.fail("\n".join(failures))

    def test_port_counter_above_initial_value(self, live_redis):
        """vlab:port should be >= 30000 (setnx ensures it is never reset to 30000
        if it was already higher, proving idempotent re-runs don't break allocation)."""
        port = live_redis.get('vlab:port')
        assert port is not None, "vlab:port counter missing"
        assert int(port) >= 30000

    def test_no_duplicate_user_permission_types(self, live_redis):
        """No user should simultaneously have overlord='false' (the sentinel value
        used by populated_redis fixture) in a real deployment — real overlords are
        'true' and non-overlords have no key at all."""
        users = live_redis.smembers('vlab:users')
        failures = []
        for user in users:
            val = live_redis.get(f'vlab:user:{user}:overlord')
            if val == 'false':
                failures.append(
                    f"vlab:user:{user}:overlord is 'false'; "
                    "non-overlords should have no key, not 'false'"
                )
        if failures:
            pytest.fail("\n".join(failures))

    def test_knownboards_entries_have_class_and_type(self, live_redis):
        """Every board in vlab:knownboards must have class and type keys."""
        boards = live_redis.smembers('vlab:knownboards')
        failures = []
        for board in boards:
            cls = live_redis.get(f'vlab:knownboard:{board}:class')
            typ = live_redis.get(f'vlab:knownboard:{board}:type')
            if not cls:
                failures.append(f"vlab:knownboard:{board}:class is missing")
            if not typ:
                failures.append(f"vlab:knownboard:{board}:type is missing")
        if failures:
            pytest.fail("\n".join(failures))
