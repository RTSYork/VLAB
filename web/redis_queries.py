#!/usr/bin/env python3

"""
Query Redis for live VLAB board status.

Mirrors the logic from relay/checkboards.py but returns data structures
instead of printing/calling sys.exit().
"""

import os
import time

import redis

MAX_LOCK_TIME = 3600


def connect():
    """Connect to Redis, returning a client or None on failure."""
    host = os.environ.get('REDIS_HOST', 'relay')
    try:
        db = redis.Redis(host=host, port=6379, db=0, decode_responses=True)
        db.ping()
        return db
    except (redis.exceptions.ConnectionError, redis.exceptions.TimeoutError):
        return None


def get_board_status(db):
    """Return a list of board dicts with status info.

    Each board dict:
        serial, boardclass, server, port, status, user, start_time,
        lock_time, duration_s
    """
    if db is None:
        return []

    boards = []
    now = int(time.time())

    for bc in db.smembers('vlab:boardclasses'):
        for serial in db.smembers('vlab:boardclass:{}:boards'.format(bc)):
            board = {
                'serial': serial,
                'boardclass': bc,
                'server': db.get('vlab:board:{}:server'.format(serial)) or '',
                'port': db.get('vlab:board:{}:port'.format(serial)) or '',
                'status': 'unknown',
                'user': '',
                'start_time': '',
                'lock_time': '',
                'duration_s': 0,
            }

            available_since = db.zscore(
                'vlab:boardclass:{}:availableboards'.format(bc), serial)

            if available_since is not None:
                board['status'] = 'available'
                boards.append(board)
                continue

            # Not available — check for active session
            session_user = db.get('vlab:board:{}:session:username'.format(serial))
            session_start = db.get('vlab:board:{}:session:starttime'.format(serial))

            if session_user and session_start:
                board['user'] = session_user
                board['start_time'] = session_start
                try:
                    board['duration_s'] = now - int(session_start)
                except (ValueError, TypeError):
                    board['duration_s'] = 0

                # Check lock status
                lock_user = db.get('vlab:board:{}:lock:username'.format(serial))
                lock_time = db.get('vlab:board:{}:lock:time'.format(serial))

                unlocked_since = db.zscore(
                    'vlab:boardclass:{}:unlockedboards'.format(bc), serial)

                if lock_user and lock_time:
                    board['status'] = 'in_use_locked'
                    board['lock_time'] = lock_time
                elif unlocked_since is not None:
                    board['status'] = 'in_use_unlocked'
                else:
                    board['status'] = 'in_use_locked'
            else:
                # No session, not available — stale state
                board['status'] = 'available'

            boards.append(board)

    boards.sort(key=lambda b: (b['boardclass'], b['server'], b['port']))
    return boards


def get_summary(db):
    """Return per-boardclass summary counts."""
    if db is None:
        return {}

    summary = {}
    for bc in db.smembers('vlab:boardclasses'):
        total = db.scard('vlab:boardclass:{}:boards'.format(bc))
        available = db.zcard('vlab:boardclass:{}:availableboards'.format(bc))
        unlocked = db.zcard('vlab:boardclass:{}:unlockedboards'.format(bc))
        in_use = total - available

        # Boards can be in both unlockedboards and availableboards ZSETs
        # (unlock then end_session adds to both). Clamp to avoid negatives.
        in_use_unlocked = min(unlocked, in_use)
        in_use_locked = in_use - in_use_unlocked

        summary[bc] = {
            'total': total,
            'available': available,
            'in_use': in_use,
            'in_use_locked': in_use_locked,
            'in_use_unlocked': in_use_unlocked,
        }

    return summary
