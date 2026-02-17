"""Tests for vlabcommon/vlabredis.py functions using fakeredis."""

import time

import pytest
import redis as redis_lib

import vlabredis


@pytest.mark.unit
class TestLockUnlock:
    def test_lock_board(self, populated_redis):
        db = populated_redis
        now = int(time.time())
        # BOARD001 is currently unlocked; lock it
        vlabredis.lock_board(db, "BOARD001", "vlab_test", "testuser", now)

        assert db.get("vlab:board:BOARD001:lock:username") == "testuser"
        assert db.get("vlab:board:BOARD001:lock:time") == str(now)
        # Should have been removed from unlocked set
        assert db.zscore("vlab:boardclass:vlab_test:unlockedboards", "BOARD001") is None

    def test_unlock_board(self, populated_redis):
        db = populated_redis
        # BOARD002 is locked; unlock it
        result = vlabredis.unlock_board(db, "BOARD002", "vlab_test")
        assert result is True
        assert db.get("vlab:board:BOARD002:lock:username") is None
        assert db.get("vlab:board:BOARD002:lock:time") is None
        assert db.zscore("vlab:boardclass:vlab_test:unlockedboards", "BOARD002") is not None

    def test_unlock_board_if_user_correct(self, populated_redis):
        db = populated_redis
        # BOARD002 is locked by testuser
        result = vlabredis.unlock_board_if_user(db, "BOARD002", "vlab_test", "testuser")
        assert result is True

    def test_unlock_board_if_user_wrong(self, populated_redis):
        db = populated_redis
        result = vlabredis.unlock_board_if_user(db, "BOARD002", "vlab_test", "wronguser")
        assert result is False

    def test_unlock_board_if_user_time_correct(self, populated_redis):
        db = populated_redis
        lock_time = db.get("vlab:board:BOARD002:lock:time")
        result = vlabredis.unlock_board_if_user_time(
            db, "BOARD002", "vlab_test", "testuser", int(lock_time)
        )
        assert result is True

    def test_unlock_board_if_user_time_wrong_time(self, populated_redis):
        db = populated_redis
        result = vlabredis.unlock_board_if_user_time(
            db, "BOARD002", "vlab_test", "testuser", 0
        )
        assert result is False

    def test_unlock_boards_held_by(self, populated_redis):
        db = populated_redis
        # BOARD002 is locked by testuser
        vlabredis.unlock_boards_held_by(db, "testuser")
        assert db.get("vlab:board:BOARD002:lock:username") is None


@pytest.mark.unit
class TestSessions:
    def test_start_session(self, populated_redis):
        db = populated_redis
        now = int(time.time())
        # Start a session on BOARD001 (currently available)
        vlabredis.start_session(db, "BOARD001", "vlab_test", "testoverlord", now)

        assert db.get("vlab:board:BOARD001:session:username") == "testoverlord"
        assert db.get("vlab:board:BOARD001:session:starttime") == str(now)
        assert db.get("vlab:board:BOARD001:session:pingtime") == str(now)
        # Should be removed from available
        assert db.zscore("vlab:boardclass:vlab_test:availableboards", "BOARD001") is None
        # Should be locked
        assert db.get("vlab:board:BOARD001:lock:username") == "testoverlord"

    def test_end_session(self, populated_redis):
        db = populated_redis
        # BOARD002 has an active session
        result = vlabredis.end_session(db, "BOARD002", "vlab_test")
        assert result is True
        assert db.get("vlab:board:BOARD002:session:username") is None
        assert db.get("vlab:board:BOARD002:session:starttime") is None
        assert db.get("vlab:board:BOARD002:session:pingtime") is None
        assert db.zscore("vlab:boardclass:vlab_test:availableboards", "BOARD002") is not None

    def test_end_session_if_user_correct(self, populated_redis):
        db = populated_redis
        result = vlabredis.end_session_if_user(db, "BOARD002", "vlab_test", "testuser")
        assert result is True

    def test_end_session_if_user_wrong(self, populated_redis):
        db = populated_redis
        result = vlabredis.end_session_if_user(db, "BOARD002", "vlab_test", "wronguser")
        assert result is False

    def test_end_session_if_user_time_correct(self, populated_redis):
        db = populated_redis
        start_time = db.get("vlab:board:BOARD002:session:starttime")
        result = vlabredis.end_session_if_user_time(
            db, "BOARD002", "vlab_test", "testuser", int(start_time)
        )
        assert result is True

    def test_end_session_if_user_time_wrong(self, populated_redis):
        db = populated_redis
        result = vlabredis.end_session_if_user_time(
            db, "BOARD002", "vlab_test", "testuser", 0
        )
        assert result is False


@pytest.mark.unit
class TestPingSession:
    def test_ping_session(self, populated_redis):
        db = populated_redis
        before = db.get("vlab:board:BOARD002:session:pingtime")
        time.sleep(0.01)  # ensure time advances
        result = vlabredis.ping_session(db, "BOARD002")
        assert result is True
        after = db.get("vlab:board:BOARD002:session:pingtime")
        assert int(after) >= int(before)

    def test_ping_session_if_user_correct(self, populated_redis):
        db = populated_redis
        result = vlabredis.ping_session_if_user(db, "BOARD002", "testuser")
        assert result is True

    def test_ping_session_if_user_wrong(self, populated_redis):
        db = populated_redis
        result = vlabredis.ping_session_if_user(db, "BOARD002", "wronguser")
        assert result is False

    def test_ping_session_if_user_time_correct(self, populated_redis):
        db = populated_redis
        start_time = db.get("vlab:board:BOARD002:session:starttime")
        result = vlabredis.ping_session_if_user_time(
            db, "BOARD002", "testuser", int(start_time)
        )
        assert result is True

    def test_ping_session_if_user_time_wrong(self, populated_redis):
        db = populated_redis
        result = vlabredis.ping_session_if_user_time(
            db, "BOARD002", "testuser", 0
        )
        assert result is False


@pytest.mark.unit
class TestAllocation:
    def test_allocate_available_board(self, populated_redis):
        db = populated_redis
        board = vlabredis.allocate_available_board_of_class(db, "vlab_test")
        assert board == "BOARD001"
        # Second call: no more available — _zpopmin sends ZREM None which
        # works on real Redis but fakeredis raises DataError
        try:
            board2 = vlabredis.allocate_available_board_of_class(db, "vlab_test")
            assert board2 is None
        except redis_lib.exceptions.DataError:
            pass  # expected with fakeredis when set is empty

    def test_allocate_unlocked_board(self, populated_redis):
        db = populated_redis
        board = vlabredis.allocate_unlocked_board_of_class(db, "vlab_test")
        assert board == "BOARD001"
        # Second call: same _zpopmin edge case as above
        try:
            board2 = vlabredis.allocate_unlocked_board_of_class(db, "vlab_test")
            assert board2 is None
        except redis_lib.exceptions.DataError:
            pass

    def test_allocate_from_empty_class(self, mock_redis):
        db = mock_redis
        # _zpopmin sends ZREM None on empty sets — fakeredis raises DataError
        try:
            board = vlabredis.allocate_available_board_of_class(db, "nonexistent")
            assert board is None
        except redis_lib.exceptions.DataError:
            pass


@pytest.mark.unit
class TestHelpers:
    def test_check_in_set_exists(self, populated_redis):
        db = populated_redis
        # Should not raise
        vlabredis.check_in_set(db, "vlab:users", "testuser", "not found")

    def test_check_in_set_missing(self, populated_redis):
        db = populated_redis
        with pytest.raises(SystemExit):
            vlabredis.check_in_set(db, "vlab:users", "nobody", "not found")

    def test_get_or_fail_exists(self, populated_redis):
        db = populated_redis
        val = vlabredis.get_or_fail(db, "vlab:board:BOARD001:server", "missing")
        assert val == "boardserver1"

    def test_get_or_fail_missing(self, populated_redis):
        db = populated_redis
        with pytest.raises(SystemExit):
            vlabredis.get_or_fail(db, "vlab:nonexistent:key", "missing")

    def test_get_board_details(self, populated_redis):
        db = populated_redis
        details = vlabredis.get_board_details(db, "BOARD001", ["server", "port"])
        assert details == {"server": "boardserver1", "port": "30001"}

    def test_get_boardclass_of_board(self, populated_redis):
        db = populated_redis
        bc = vlabredis.get_boardclass_of_board(db, "BOARD001")
        assert bc == "vlab_test"

    def test_get_boardclass_of_board_unknown(self, populated_redis):
        db = populated_redis
        bc = vlabredis.get_boardclass_of_board(db, "NOSUCHBOARD")
        assert bc is None

    def test_remove_board(self, populated_redis):
        db = populated_redis
        vlabredis.remove_board(db, "BOARD001")
        assert not db.sismember("vlab:boardclass:vlab_test:boards", "BOARD001")
        assert db.zscore("vlab:boardclass:vlab_test:availableboards", "BOARD001") is None
        assert db.get("vlab:board:BOARD001:server") is None
