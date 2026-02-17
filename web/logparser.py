#!/usr/bin/env python3

"""
Parse the VLAB access.log to extract usage statistics.

Replaces the broken relay/logparse.py which splits on ':' and fails
when boardclass:serial contains a colon (e.g. vlab_zybo-z7:210351A77F75).
This version uses regex patterns instead.
"""

import os
import re
import time
from collections import defaultdict
from datetime import datetime, timedelta

LOG_PATH = os.environ.get('VLAB_LOG_PATH', '/vlab/log/access.log')

# Regex for the overall log line format:
# 2026-02-16 21:19:06,445 ; INFO ; shell.py ; START: ian, vlab_zybo-z7:210351A77F75
LINE_RE = re.compile(
    r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d+)\s*;\s*(\w+)\s*;\s*(\S+)\s*;(.*)'
)

# Event-specific regexes applied to the message body
START_RE = re.compile(r'START:\s*(\S+),\s*(\S+):(\S+)')
LOCK_RE = re.compile(r'LOCK:\s*(\S+),\s*(\S+):(\S+),\s*(\d+)\s+remaining in set')
RELEASE_RE = re.compile(r'RELEASE:\s*(\S+),\s*(\S+):(\S+)')
END_RE = re.compile(r'END:\s*(\S+),\s*(\S+):(\S+)')
NOFREEBOARDS_RE = re.compile(r'NOFREEBOARDS:\s*(\S+),\s*(\S+)')

# Cache state
_cache = {
    'mtime': 0,
    'size': 0,
    'result': None,
}


def _parse_timestamp(ts_str):
    """Parse '2026-02-16 21:19:06,445' to a datetime."""
    try:
        return datetime.strptime(ts_str, '%Y-%m-%d %H:%M:%S,%f')
    except ValueError:
        return None


def parse_log(log_path=None):
    """Parse the access log and return computed statistics.

    Uses file mtime/size for cache invalidation - returns cached result
    if the file hasn't changed.
    """
    if log_path is None:
        log_path = LOG_PATH

    try:
        st = os.stat(log_path)
    except OSError:
        return _empty_stats()

    if (_cache['result'] is not None
            and st.st_mtime == _cache['mtime']
            and st.st_size == _cache['size']):
        return _cache['result']

    result = _do_parse(log_path)
    _cache['mtime'] = st.st_mtime
    _cache['size'] = st.st_size
    _cache['result'] = result
    return result


def _empty_stats():
    return {
        'sessions': [],
        'hourly': [],
        'users': [],
        'denials': [],
        'total_sessions': 0,
        'total_denials': 0,
    }


def _do_parse(log_path):
    # Track open sessions: key = (username, boardclass) -> {start_time, serial}
    open_sessions = {}

    # Completed sessions: list of {user, boardclass, serial, start, end, duration_s}
    completed = []

    # Denials: list of {timestamp, user, boardclass}
    denials = []

    # Hourly usage buckets: hour_key -> count of LOCK events
    hourly_locks = defaultdict(int)

    # Per-user stats
    user_counts = defaultdict(int)
    user_total_time = defaultdict(float)

    try:
        with open(log_path, 'r') as f:
            for line in f:
                m = LINE_RE.match(line)
                if not m:
                    continue

                ts_str, level, source, message = m.groups()
                message = message.strip()

                if source.strip() != 'shell.py':
                    continue

                ts = _parse_timestamp(ts_str)
                if ts is None:
                    continue

                # Try each event pattern
                sm = START_RE.match(message)
                if sm:
                    user, bc, serial = sm.groups()
                    key = (user, bc)
                    open_sessions[key] = {'start': ts, 'serial': serial}
                    continue

                lm = LOCK_RE.match(message)
                if lm:
                    user, bc, serial, remaining = lm.groups()
                    hour_key = ts.strftime('%Y-%m-%d %H:00')
                    hourly_locks[hour_key] += 1
                    continue

                rm = RELEASE_RE.match(message)
                if rm:
                    user, bc, serial = rm.groups()
                    # Release doesn't end session, just unlock
                    continue

                em = END_RE.match(message)
                if em:
                    user, bc, serial = em.groups()
                    key = (user, bc)
                    if key in open_sessions:
                        sess = open_sessions.pop(key)
                        duration = (ts - sess['start']).total_seconds()
                        if duration < 0:
                            duration = 0
                        completed.append({
                            'user': user,
                            'boardclass': bc,
                            'serial': serial,
                            'start': sess['start'].isoformat(),
                            'end': ts.isoformat(),
                            'duration_s': duration,
                        })
                        user_counts[user] += 1
                        user_total_time[user] += duration
                    continue

                nm = NOFREEBOARDS_RE.match(message)
                if nm:
                    user, bc = nm.groups()
                    denials.append({
                        'timestamp': ts.isoformat(),
                        'user': user,
                        'boardclass': bc,
                    })
                    continue

    except OSError:
        return _empty_stats()

    # Build per-user summary
    users = []
    for user in sorted(user_counts.keys()):
        total = user_total_time[user]
        count = user_counts[user]
        users.append({
            'user': user,
            'count': count,
            'total_time_s': total,
            'avg_time_s': total / count if count > 0 else 0,
        })
    users.sort(key=lambda u: u['total_time_s'], reverse=True)

    # Build hourly data (last 7 days)
    now = datetime.now()
    cutoff = now - timedelta(days=7)
    hourly = []
    for hour_key in sorted(hourly_locks.keys()):
        try:
            hour_dt = datetime.strptime(hour_key, '%Y-%m-%d %H:%M')
        except ValueError:
            continue
        if hour_dt >= cutoff:
            hourly.append({
                'hour': hour_key,
                'locks': hourly_locks[hour_key],
            })

    # Today's denials
    today = now.strftime('%Y-%m-%d')
    today_denials = [d for d in denials if d['timestamp'].startswith(today)]

    return {
        'sessions': completed[-100:],  # Last 100 sessions
        'hourly': hourly,
        'users': users,
        'denials': denials[-50:],  # Last 50 denials
        'denials_today': len(today_denials),
        'total_sessions': len(completed),
        'total_denials': len(denials),
    }
