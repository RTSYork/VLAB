#!/usr/bin/env python3

"""
VLAB Web Dashboard — Flask application.
"""

import time

from flask import Flask, jsonify, render_template

import logparser
import redis_queries

app = Flask(__name__)


@app.route('/')
def dashboard():
    return render_template('dashboard.html')


@app.route('/api/boards')
def api_boards():
    db = redis_queries.connect()
    boards = redis_queries.get_board_status(db)
    summary = redis_queries.get_summary(db)

    # Flatten summary for the dashboard
    totals = {'total': 0, 'available': 0, 'in_use': 0,
              'in_use_locked': 0, 'in_use_unlocked': 0}
    for bc, counts in summary.items():
        for k in totals:
            totals[k] += counts.get(k, 0)

    return jsonify({
        'boards': boards,
        'summary': summary,
        'totals': totals,
        'timestamp': int(time.time()),
        'redis_ok': db is not None,
    })


@app.route('/api/stats/summary')
def api_stats_summary():
    stats = logparser.parse_log()
    return jsonify({
        'total_sessions': stats['total_sessions'],
        'total_denials': stats['total_denials'],
        'denials_today': stats.get('denials_today', 0),
    })


@app.route('/api/stats/hourly')
def api_stats_hourly():
    stats = logparser.parse_log()
    return jsonify({'hourly': stats['hourly']})


@app.route('/api/stats/users')
def api_stats_users():
    stats = logparser.parse_log()
    return jsonify({'users': stats['users']})


@app.route('/api/stats/denials')
def api_stats_denials():
    stats = logparser.parse_log()
    return jsonify({'denials': stats['denials']})
