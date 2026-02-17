"""Tests for web/logparser.py regex patterns and parsing."""

import os
import tempfile
from datetime import datetime

import pytest

import logparser


@pytest.mark.unit
class TestRegexPatterns:
    def test_start_re(self):
        msg = "START: ian, vlab_zybo-z7:210351A77F75"
        m = logparser.START_RE.match(msg)
        assert m is not None
        assert m.group(1) == "ian"
        assert m.group(2) == "vlab_zybo-z7"
        assert m.group(3) == "210351A77F75"

    def test_lock_re(self):
        msg = "LOCK: ian, vlab_zybo-z7:210351A77F75, 3 remaining in set"
        m = logparser.LOCK_RE.match(msg)
        assert m is not None
        assert m.group(1) == "ian"
        assert m.group(4) == "3"

    def test_end_re(self):
        msg = "END: ian, vlab_zybo-z7:210351A77F75"
        m = logparser.END_RE.match(msg)
        assert m is not None
        assert m.group(1) == "ian"

    def test_nofreeboards_re(self):
        msg = "NOFREEBOARDS: student1, vlab_zybo-z7"
        m = logparser.NOFREEBOARDS_RE.match(msg)
        assert m is not None
        assert m.group(1) == "student1"
        assert m.group(2) == "vlab_zybo-z7"

    def test_line_re(self):
        line = "2026-02-16 21:19:06,445 ; INFO ; shell.py ; START: ian, vlab_zybo-z7:210351A77F75"
        m = logparser.LINE_RE.match(line)
        assert m is not None
        assert m.group(1) == "2026-02-16 21:19:06,445"
        assert m.group(2) == "INFO"
        assert m.group(3).strip() == "shell.py"


@pytest.mark.unit
class TestParseTimestamp:
    def test_valid_timestamp(self):
        result = logparser._parse_timestamp("2026-02-16 21:19:06,445")
        assert result is not None
        assert result.year == 2026
        assert result.month == 2
        assert result.second == 6

    def test_invalid_timestamp(self):
        result = logparser._parse_timestamp("not a timestamp")
        assert result is None


@pytest.mark.unit
class TestParseLog:
    def _make_log(self, tmp_path, lines):
        logfile = tmp_path / "access.log"
        logfile.write_text("\n".join(lines) + "\n")
        return str(logfile)

    def test_empty_file(self, tmp_path):
        path = self._make_log(tmp_path, [])
        # Reset cache to avoid cross-test interference
        logparser._cache['result'] = None
        result = logparser.parse_log(path)
        assert result["total_sessions"] == 0
        assert result["total_denials"] == 0

    def test_complete_session(self, tmp_path):
        lines = [
            "2026-02-16 10:00:00,000 ; INFO ; shell.py ; START: alice, vlab_test:SN001",
            "2026-02-16 10:00:01,000 ; INFO ; shell.py ; LOCK: alice, vlab_test:SN001, 2 remaining in set",
            "2026-02-16 10:30:00,000 ; INFO ; shell.py ; END: alice, vlab_test:SN001",
        ]
        path = self._make_log(tmp_path, lines)
        logparser._cache['result'] = None
        result = logparser.parse_log(path)
        assert result["total_sessions"] == 1
        assert len(result["sessions"]) == 1
        sess = result["sessions"][0]
        assert sess["user"] == "alice"
        assert sess["duration_s"] == 1800.0

    def test_denial_counting(self, tmp_path):
        lines = [
            "2026-02-16 10:00:00,000 ; INFO ; shell.py ; NOFREEBOARDS: bob, vlab_test",
            "2026-02-16 10:05:00,000 ; INFO ; shell.py ; NOFREEBOARDS: bob, vlab_test",
        ]
        path = self._make_log(tmp_path, lines)
        logparser._cache['result'] = None
        result = logparser.parse_log(path)
        assert result["total_denials"] == 2

    def test_missing_file_returns_empty(self):
        logparser._cache['result'] = None
        result = logparser.parse_log("/nonexistent/access.log")
        assert result["total_sessions"] == 0
        assert result["sessions"] == []
