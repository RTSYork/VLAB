"""Tests for web/redis_queries.py using fakeredis."""

import time

import pytest

import redis_queries


@pytest.mark.unit
class TestGetBoardStatus:
    def test_returns_list(self, populated_redis):
        boards = redis_queries.get_board_status(populated_redis)
        assert isinstance(boards, list)
        assert len(boards) == 2

    def test_available_board_status(self, populated_redis):
        boards = redis_queries.get_board_status(populated_redis)
        b001 = next(b for b in boards if b["serial"] == "BOARD001")
        assert b001["status"] == "available"
        assert b001["server"] == "boardserver1"
        assert b001["port"] == "30001"

    def test_in_use_locked_status(self, populated_redis):
        boards = redis_queries.get_board_status(populated_redis)
        b002 = next(b for b in boards if b["serial"] == "BOARD002")
        assert b002["status"] == "in_use_locked"
        assert b002["user"] == "testuser"

    def test_duration_calculated(self, populated_redis):
        boards = redis_queries.get_board_status(populated_redis)
        b002 = next(b for b in boards if b["serial"] == "BOARD002")
        # Session started ~600s ago
        assert b002["duration_s"] > 500

    def test_sorted_output(self, populated_redis):
        boards = redis_queries.get_board_status(populated_redis)
        # Should be sorted by (boardclass, server, port)
        servers = [b["server"] for b in boards]
        assert servers == sorted(servers)

    def test_none_db_returns_empty(self):
        assert redis_queries.get_board_status(None) == []


@pytest.mark.unit
class TestGetSummary:
    def test_returns_dict(self, populated_redis):
        summary = redis_queries.get_summary(populated_redis)
        assert isinstance(summary, dict)
        assert "vlab_test" in summary

    def test_counts(self, populated_redis):
        summary = redis_queries.get_summary(populated_redis)
        s = summary["vlab_test"]
        assert s["total"] == 2
        assert s["available"] == 1
        assert s["in_use"] == 1

    def test_none_db_returns_empty(self):
        assert redis_queries.get_summary(None) == {}
