"""Tests for vlabcommon/vlabconfig.py:open_log()."""

import json
import logging
import os
import tempfile

import pytest

import vlabconfig


@pytest.mark.unit
class TestOpenLogValid:
    """Valid configuration files should parse correctly."""

    def test_minimal_valid_config(self, tmp_path):
        conf = tmp_path / "vlab.conf"
        conf.write_text(json.dumps({
            "users": {"alice": {}},
            "boards": {"B001": {"class": "cls", "type": "typ"}},
        }))
        log = logging.getLogger("test")
        result = vlabconfig.open_log(log, str(conf))
        assert result is not None
        assert "alice" in result["users"]
        assert "B001" in result["boards"]

    def test_config_with_comments(self, tmp_path):
        conf = tmp_path / "vlab.conf"
        conf.write_text(
            "# this is a comment\n"
            '{"users": {"bob": {}}, '
            '"boards": {"B001": {"class": "c", "type": "t"}}}\n'
        )
        log = logging.getLogger("test")
        result = vlabconfig.open_log(log, str(conf))
        assert result is not None
        assert "bob" in result["users"]

    def test_multiline_config_with_comments(self, tmp_path):
        conf = tmp_path / "vlab.conf"
        conf.write_text(
            "# header comment\n"
            "{\n"
            '  # inline comment\n'
            '  "users": {"u1": {}},\n'
            '  "boards": {"B1": {"class": "c", "type": "t"}}\n'
            "}\n"
        )
        log = logging.getLogger("test")
        result = vlabconfig.open_log(log, str(conf))
        assert result is not None

    def test_overlord_user(self, tmp_path):
        conf = tmp_path / "vlab.conf"
        conf.write_text(json.dumps({
            "users": {"admin": {"overlord": True}},
            "boards": {"B1": {"class": "c", "type": "t"}},
        }))
        log = logging.getLogger("test")
        result = vlabconfig.open_log(log, str(conf))
        assert result is not None
        assert result["users"]["admin"]["overlord"] is True

    def test_user_with_allowedboards(self, tmp_path):
        conf = tmp_path / "vlab.conf"
        conf.write_text(json.dumps({
            "users": {"stu": {"allowedboards": ["vlab_test"]}},
            "boards": {"B1": {"class": "c", "type": "t"}},
        }))
        log = logging.getLogger("test")
        result = vlabconfig.open_log(log, str(conf))
        assert result is not None

    def test_empty_users_section(self, tmp_path):
        """An empty users dict is technically valid (has the key)."""
        conf = tmp_path / "vlab.conf"
        conf.write_text(json.dumps({
            "users": {},
            "boards": {"B1": {"class": "c", "type": "t"}},
        }))
        log = logging.getLogger("test")
        result = vlabconfig.open_log(log, str(conf))
        assert result is not None

    def test_optional_reset_property_on_board(self, tmp_path):
        """Boards may have extra properties beyond class/type."""
        conf = tmp_path / "vlab.conf"
        conf.write_text(json.dumps({
            "users": {"u1": {}},
            "boards": {"B1": {"class": "c", "type": "t", "reset": True}},
        }))
        log = logging.getLogger("test")
        result = vlabconfig.open_log(log, str(conf))
        assert result is not None


@pytest.mark.unit
class TestOpenLogInvalid:
    """Invalid configs should return None."""

    def test_missing_users(self, tmp_path):
        conf = tmp_path / "vlab.conf"
        conf.write_text(json.dumps({
            "boards": {"B1": {"class": "c", "type": "t"}},
        }))
        log = logging.getLogger("test")
        assert vlabconfig.open_log(log, str(conf)) is None

    def test_missing_boards(self, tmp_path):
        conf = tmp_path / "vlab.conf"
        conf.write_text(json.dumps({
            "users": {"u1": {}},
        }))
        log = logging.getLogger("test")
        assert vlabconfig.open_log(log, str(conf)) is None

    def test_unknown_user_property(self, tmp_path):
        conf = tmp_path / "vlab.conf"
        conf.write_text(json.dumps({
            "users": {"u1": {"badprop": True}},
            "boards": {"B1": {"class": "c", "type": "t"}},
        }))
        log = logging.getLogger("test")
        assert vlabconfig.open_log(log, str(conf)) is None

    def test_missing_board_class(self, tmp_path):
        conf = tmp_path / "vlab.conf"
        conf.write_text(json.dumps({
            "users": {"u1": {}},
            "boards": {"B1": {"type": "t"}},
        }))
        log = logging.getLogger("test")
        assert vlabconfig.open_log(log, str(conf)) is None

    def test_missing_board_type(self, tmp_path):
        conf = tmp_path / "vlab.conf"
        conf.write_text(json.dumps({
            "users": {"u1": {}},
            "boards": {"B1": {"class": "c"}},
        }))
        log = logging.getLogger("test")
        assert vlabconfig.open_log(log, str(conf)) is None

    def test_invalid_json(self, tmp_path):
        conf = tmp_path / "vlab.conf"
        conf.write_text("{ this is not valid json }")
        log = logging.getLogger("test")
        assert vlabconfig.open_log(log, str(conf)) is None
