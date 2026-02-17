#!/usr/bin/env python3

"""
Periodic FPGA hardware test. For each idle board, programs a known test
bitstream and checks for expected serial output. Boards that fail are
removed from the available/unlocked pools until they pass a subsequent run.

Run manually:  testboards.py -v
Intended to be invoked every 4 hours via cron.

Ian Gray, 2025
"""

import argparse
import os
import subprocess
import time

from vlabredis import *

parser = argparse.ArgumentParser(description="VLAB hardware test script")
parser.add_argument('-v', action="store_true", default=False, dest='verbose')
parsed = parser.parse_args()

KEYS_DIR = "/vlab/keys/"
KEYFILE = KEYS_DIR + "id_rsa"
TEST_MAGIC = "VLAB_TEST_OK"
SERIAL_TIMEOUT = 15  # seconds to wait for serial output
SSH_TIMEOUT = 30     # seconds for SSH commands
TEST_TTL = 120       # TTL for the per-board testing flag
RUN_TTL = 14400      # TTL for the global run lock (4 hours)


def log(msg, verbose_only=False):
    if verbose_only and not parsed.verbose:
        return
    print("{} testboards.py: {}".format(time.strftime("%Y-%m-%d-%H:%M:%S"), msg))


def ssh_to_board(server, port, cmd, timeout=SSH_TIMEOUT):
    """Run a command on a board container via SSH. Returns (returncode, stdout, stderr)."""
    ssh_cmd = [
        "ssh", "-q", "-o", "StrictHostKeyChecking=no", "-i", KEYFILE,
        "-p", str(port), "root@{}".format(server), cmd
    ]
    try:
        result = subprocess.run(ssh_cmd, capture_output=True, text=True, timeout=timeout)
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "SSH command timed out after {}s".format(timeout)
    except Exception as e:
        return -1, "", str(e)


def board_is_idle(db, board):
    """Return True only if board has no active session and no lock."""
    session_user = db.get("vlab:board:{}:session:username".format(board))
    lock_user = db.get("vlab:board:{}:lock:username".format(board))
    return session_user is None and lock_user is None


def withdraw_board(db, board, bc):
    """Remove board from both availableboards and unlockedboards.
    Returns True if it was in at least one set."""
    r1 = db.zrem("vlab:boardclass:{}:availableboards".format(bc), board)
    r2 = db.zrem("vlab:boardclass:{}:unlockedboards".format(bc), board)
    return (r1 + r2) > 0


def return_board(db, board, bc):
    """Return board to both availableboards and unlockedboards."""
    now = int(time.time())
    db.zadd("vlab:boardclass:{}:availableboards".format(bc), {board: now})
    db.zadd("vlab:boardclass:{}:unlockedboards".format(bc), {board: now})


def program_and_read_serial(server, port):
    """Program the test bitstream and capture serial output in one SSH session.

    Starts reading /dev/ttyFPGA in the background before launching xsdb, so
    that any output from the ELF is captured even if it arrives early.
    Returns (success, serial_output, error_message).
    """
    cmd = (
        "killall -q screen; "
        "stty -F /dev/ttyFPGA 115200 raw -echo; "
        "cat /dev/ttyFPGA > /tmp/vlab_serial_test & CAT_PID=$!; "
        "/opt/xsct/bin/xsdb /vlab/test.tcl; XSDB_RC=$?; "
        "sleep 1; "
        "kill $CAT_PID 2>/dev/null; "
        "cat /tmp/vlab_serial_test; "
        "exit $XSDB_RC"
    )
    rc, stdout, stderr = ssh_to_board(server, port, cmd, timeout=90)
    if rc != 0:
        return False, "", "xsdb failed (rc={}): {} {}".format(rc, stdout.strip(), stderr.strip())
    return True, stdout, ""


def reset_board(db, board, server, port):
    """Reset the board after testing."""
    try:
        if db.get("vlab:knownboard:{}:reset".format(board)) == "true":
            cmd = "/opt/xsct/bin/xsdb /vlab/reset.tcl"
            ssh_to_board(server, port, cmd, timeout=30)
    except Exception as e:
        log("Exception resetting board {}: {}".format(board, e))


def record_result(db, board, status, message):
    """Record hardware test result in Redis."""
    db.set("vlab:board:{}:hwtest:status".format(board), status)
    db.set("vlab:board:{}:hwtest:time".format(board), int(time.time()))
    db.set("vlab:board:{}:hwtest:message".format(board), message)


def test_board(db, board, bc):
    """Test a single board. Returns True on pass, False on fail, None if skipped."""
    bd = get_board_details(db, board, ["server", "port"])
    server = bd["server"]
    port = bd["port"]

    # Check board is idle
    if not board_is_idle(db, board):
        log("Board {} is in use, skipping".format(board), verbose_only=True)
        return None

    # Withdraw from pools (atomic removal)
    was_in_pool = withdraw_board(db, board, bc)

    # For previously-failed boards: they won't be in either pool but we still
    # want to re-test them. Check if this was a known-failed board.
    prev_status = db.get("vlab:board:{}:hwtest:status".format(board))
    if not was_in_pool and prev_status != "fail":
        # Board wasn't in any pool and didn't previously fail — someone else
        # grabbed it between our idle check and withdrawal. Skip.
        log("Board {} was removed from pools by another process, skipping".format(board), verbose_only=True)
        return None

    # Set transient testing flag (prevents checkboards.py interference)
    db.set("vlab:board:{}:hwtest:testing".format(board), "1", ex=TEST_TTL)
    log("Testing board {} on {}:{}".format(board, server, port), verbose_only=True)

    passed = False
    message = ""

    try:
        # Program test bitstream and capture serial output in one SSH session
        ok, serial_output, err_msg = program_and_read_serial(server, port)
        if not ok:
            message = "Programming failed: {}".format(err_msg)
            log("Board {} FAIL: {}".format(board, message))
            record_result(db, board, "fail", message)
            reset_board(db, board, server, port)
            return False

        if TEST_MAGIC in serial_output:
            passed = True
            message = "OK"
            log("Board {} PASS".format(board), verbose_only=True)
        else:
            message = "Expected '{}' in serial output, got: '{}'".format(
                TEST_MAGIC, serial_output[:200].replace('\n', '\\n'))
            log("Board {} FAIL: {}".format(board, message))

    except Exception as e:
        message = "Exception: {}".format(e)
        log("Board {} FAIL: {}".format(board, message))

    # Record result
    record_result(db, board, "pass" if passed else "fail", message)

    # Always reset the board
    reset_board(db, board, server, port)

    # Return to pools on pass, leave out on fail
    if passed:
        return_board(db, board, bc)
    # On fail: board stays out of both pools

    # Clean up testing flag
    db.delete("vlab:board:{}:hwtest:testing".format(board))

    return passed


def test_all_boards(db):
    """Iterate all board classes and test idle boards."""
    results = {"tested": 0, "passed": 0, "failed": 0, "skipped": 0}

    for bc in db.smembers("vlab:boardclasses"):
        log("Board class: {}".format(bc), verbose_only=True)

        for board in db.smembers("vlab:boardclass:{}:boards".format(bc)):
            result = test_board(db, board, bc)
            if result is None:
                results["skipped"] += 1
            elif result:
                results["tested"] += 1
                results["passed"] += 1
            else:
                results["tested"] += 1
                results["failed"] += 1

    return results


# --- Main ---

redis_db = connect_to_redis('localhost')

# Prevent concurrent runs
if redis_db.get("vlab:hwtest:running"):
    log("Another hardware test is already running, exiting")
    sys.exit(0)

redis_db.set("vlab:hwtest:running", "1", ex=RUN_TTL)

log("Starting hardware test run")
try:
    results = test_all_boards(redis_db)
    log("Hardware test complete: {} tested ({} pass, {} fail), {} skipped".format(
        results["tested"], results["passed"], results["failed"], results["skipped"]))
finally:
    redis_db.delete("vlab:hwtest:running")
