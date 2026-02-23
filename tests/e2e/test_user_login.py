"""E2E tests: SSH login as a real VLAB user.

These tests verify that shell.py starts up correctly when a student
connects via SSH, catching permission errors, missing dependencies,
and Redis connectivity issues.

Requires: --vlab-user and --vlab-key in addition to --run-live.
"""

import subprocess

import pytest


@pytest.mark.e2e
@pytest.mark.live
class TestUserLogin:
    def _ssh_command(self, pegasus_host, ssh_port, vlab_user, vlab_key, remote_cmd):
        """Run an SSH command against the relay and return (stdout, stderr, returncode)."""
        cmd = [
            "ssh",
            "-o", "PasswordAuthentication=no",
            "-o", "StrictHostKeyChecking=no",
            "-o", "ConnectTimeout=10",
            "-i", vlab_key,
            "-p", str(ssh_port),
            "-l", vlab_user,
            pegasus_host,
            remote_cmd,
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        return proc.stdout.strip(), proc.stderr.strip(), proc.returncode

    def test_shell_starts_successfully(self, pegasus_host, ssh_port, vlab_user, vlab_key):
        """shell.py should initialise without errors (logging, Redis, etc).

        The 'getport' command is the lightest operation — it just
        increments a Redis counter and prints VLABPORT:<n>.  If shell.py
        crashes during startup (e.g. PermissionError on the log file),
        we'll get a traceback on stderr and no VLABPORT on stdout.
        """
        stdout, stderr, rc = self._ssh_command(
            pegasus_host, ssh_port, vlab_user, vlab_key, "getport"
        )
        assert "Traceback" not in stderr, (
            f"shell.py crashed during startup:\n{stderr}"
        )
        assert stdout.startswith("VLABPORT:"), (
            f"Expected VLABPORT:<port>, got stdout={stdout!r}, stderr={stderr!r}"
        )

    def test_getport_returns_valid_port(self, pegasus_host, ssh_port, vlab_user, vlab_key):
        """The port returned by getport should be a number in the expected range."""
        stdout, stderr, rc = self._ssh_command(
            pegasus_host, ssh_port, vlab_user, vlab_key, "getport"
        )
        assert stdout.startswith("VLABPORT:"), (
            f"Expected VLABPORT response, got: {stdout!r}"
        )
        port = int(stdout.split(":")[1])
        assert 30000 <= port <= 35000, f"Port {port} outside expected range 30000-35000"

    def test_invalid_command_rejected(self, pegasus_host, ssh_port, vlab_user, vlab_key):
        """shell.py should exit cleanly (not crash) for an invalid command."""
        stdout, stderr, rc = self._ssh_command(
            pegasus_host, ssh_port, vlab_user, vlab_key, "nonsense"
        )
        assert "Traceback" not in stderr, (
            f"shell.py crashed on invalid input:\n{stderr}"
        )
        assert rc != 0, "Expected non-zero exit for invalid command"
