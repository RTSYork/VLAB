// VLAB Dashboard - auto-refreshing board status and usage charts

(function () {
    'use strict';

    // --- Utility functions ---

    function formatDuration(seconds) {
        if (!seconds || seconds < 0) return '-';
        var s = Math.floor(seconds);
        var h = Math.floor(s / 3600);
        var m = Math.floor((s % 3600) / 60);
        var sec = s % 60;
        if (h > 0) return h + 'h ' + m + 'm';
        if (m > 0) return m + 'm ' + sec + 's';
        return sec + 's';
    }

    function formatTime(isoOrUnix) {
        if (!isoOrUnix) return '-';
        var d;
        if (typeof isoOrUnix === 'number') {
            d = new Date(isoOrUnix * 1000);
        } else {
            d = new Date(isoOrUnix);
        }
        return d.toLocaleString();
    }

    function statusBadge(status) {
        var classes = {
            'available': 'bg-green-100 text-green-800',
            'in_use_locked': 'bg-red-100 text-red-800',
            'in_use_unlocked': 'bg-amber-100 text-amber-800',
            'hwtest_failed': 'bg-purple-100 text-purple-800',
            'unknown': 'bg-gray-100 text-gray-800'
        };
        var labels = {
            'available': 'Available',
            'in_use_locked': 'In Use (Locked)',
            'in_use_unlocked': 'In Use (Unlocked)',
            'hwtest_failed': 'HW Test Failed',
            'unknown': 'Unknown'
        };
        var cls = classes[status] || classes['unknown'];
        var label = labels[status] || status;
        return '<span class="inline-block px-2.5 py-0.5 rounded-full text-xs font-medium ' + cls + '">' + label + '</span>';
    }

    function hwtestBadge(board) {
        var st = board.hwtest_status;
        if (!st) {
            return '<span class="inline-block px-2 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-500">Untested</span>';
        }
        var ts = board.hwtest_time ? formatTime(Number(board.hwtest_time)) : '';
        if (st === 'pass') {
            return '<span class="inline-block px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">Pass</span>' +
                (ts ? '<span class="text-xs text-gray-400 ml-1">' + ts + '</span>' : '');
        }
        var msg = board.hwtest_message ? escapeHtml(board.hwtest_message) : 'Hardware test failed';
        return '<span class="inline-block px-2 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800" title="' + msg + '">Fail</span>' +
            (ts ? '<span class="text-xs text-gray-400 ml-1">' + ts + '</span>' : '');
    }

    function escapeHtml(s) {
        var div = document.createElement('div');
        div.textContent = s;
        return div.innerHTML;
    }

    // --- Board status polling (every 10s) ---

    function fetchBoards() {
        fetch('/api/boards')
            .then(function (r) { return r.json(); })
            .then(function (data) {
                updateSummaryCards(data.totals);
                updateBoardTable(data.boards);
                updateBoardclassSummary(data.summary);
                updateRedisStatus(data.redis_ok);
                updateHwtestButton(data.hwtest_running, data.hwtest_trigger);
                updateReloadConfigButton(data.config_reload_pending);
                document.getElementById('last-update').textContent =
                    'Updated ' + new Date().toLocaleTimeString();
            })
            .catch(function () {
                updateRedisStatus(false);
            });
    }

    function updateHwtestButton(running, trigger) {
        var btn = document.getElementById('hwtest-btn');
        if (!btn) return;
        if (running) {
            btn.textContent = 'Testing...';
            btn.disabled = true;
        } else if (trigger) {
            btn.textContent = 'Queued...';
            btn.disabled = true;
        } else {
            btn.textContent = 'Run HW Test';
            btn.disabled = false;
        }
    }

    function triggerHwTest() {
        var btn = document.getElementById('hwtest-btn');
        btn.disabled = true;
        btn.textContent = 'Queuing...';
        fetch('/api/hwtest/trigger', { method: 'POST' })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (data.ok) {
                    btn.textContent = 'Queued...';
                } else {
                    btn.textContent = data.error || 'Error';
                    setTimeout(function () { btn.disabled = false; btn.textContent = 'Run HW Test'; }, 3000);
                }
            })
            .catch(function () {
                btn.disabled = false;
                btn.textContent = 'Run HW Test';
            });
    }

    function updateReloadConfigButton(pending) {
        var btn = document.getElementById('reloadconfig-btn');
        if (!btn) return;
        if (pending) {
            btn.textContent = 'Reloading...';
            btn.disabled = true;
        } else {
            btn.textContent = 'Reload Config';
            btn.disabled = false;
        }
    }

    function triggerConfigReload() {
        var btn = document.getElementById('reloadconfig-btn');
        btn.disabled = true;
        btn.textContent = 'Queuing...';
        fetch('/api/config/reload', { method: 'POST' })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (data.ok) {
                    btn.textContent = 'Reloading...';
                } else {
                    btn.textContent = data.error || 'Error';
                    setTimeout(function () { btn.disabled = false; btn.textContent = 'Reload Config'; }, 3000);
                }
            })
            .catch(function () {
                btn.disabled = false;
                btn.textContent = 'Reload Config';
            });
    }

    function updateSummaryCards(totals) {
        if (!totals) return;
        document.getElementById('card-total').textContent = totals.total;
        document.getElementById('card-available').textContent = totals.available;
        document.getElementById('card-locked').textContent = totals.in_use_locked;
        document.getElementById('card-unlocked').textContent = totals.in_use_unlocked;
        document.getElementById('card-hwtest-failed').textContent = totals.hwtest_failed || 0;
    }

    function updateRedisStatus(ok) {
        var el = document.getElementById('redis-error');
        if (ok) {
            el.classList.add('hidden');
        } else {
            el.classList.remove('hidden');
        }
    }

    function updateBoardTable(boards) {
        var tbody = document.getElementById('board-table-body');
        if (!boards || boards.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" class="px-5 py-8 text-center text-gray-400">No boards registered</td></tr>';
            return;
        }
        var html = '';
        for (var i = 0; i < boards.length; i++) {
            var b = boards[i];
            var rowClass = '';
            if (b.status === 'hwtest_failed') rowClass = 'bg-purple-50/30';
            else if (b.status === 'available') rowClass = 'bg-green-50/50';
            else if (b.status === 'in_use_locked') rowClass = 'bg-red-50/30';
            else if (b.status === 'in_use_unlocked') rowClass = 'bg-amber-50/30';

            html += '<tr class="border-t border-gray-100 ' + rowClass + '">';
            html += '<td class="px-5 py-3 font-medium text-gray-900">' + escapeHtml(b.boardclass) + '</td>';
            html += '<td class="px-5 py-3 font-mono text-xs text-gray-600">' + escapeHtml(b.serial) + '</td>';
            html += '<td class="px-5 py-3 text-gray-600">' + escapeHtml(b.server) + ':' + escapeHtml(b.port) + '</td>';
            html += '<td class="px-5 py-3">' + statusBadge(b.status) + '</td>';
            html += '<td class="px-5 py-3">' + hwtestBadge(b) + '</td>';
            html += '<td class="px-5 py-3 text-gray-700">' + (b.user ? escapeHtml(b.user) : '-') + '</td>';
            html += '<td class="px-5 py-3 text-gray-600">' + (b.status !== 'available' && b.status !== 'hwtest_failed' && b.duration_s ? formatDuration(b.duration_s) : '-') + '</td>';
            html += '</tr>';
        }
        tbody.innerHTML = html;
    }

    function updateBoardclassSummary(summary) {
        var container = document.getElementById('boardclass-summary');
        if (!summary || Object.keys(summary).length === 0) {
            container.innerHTML = '<div class="text-gray-400 text-sm">No board classes</div>';
            return;
        }
        var html = '';
        var classes = Object.keys(summary).sort();
        for (var i = 0; i < classes.length; i++) {
            var bc = classes[i];
            var s = summary[bc];
            var pct = s.total > 0 ? Math.round((s.in_use / s.total) * 100) : 0;
            var barColor = pct > 80 ? 'bg-red-500' : (pct > 50 ? 'bg-amber-500' : 'bg-green-500');
            html += '<div class="border border-gray-100 rounded-lg p-3">';
            html += '<div class="flex justify-between items-center mb-2">';
            html += '<span class="font-medium text-gray-800">' + escapeHtml(bc) + '</span>';
            html += '<span class="text-xs text-gray-500">' + s.in_use + ' / ' + s.total + ' in use</span>';
            html += '</div>';
            html += '<div class="w-full bg-gray-100 rounded-full h-2">';
            html += '<div class="' + barColor + ' h-2 rounded-full transition-all" style="width: ' + pct + '%"></div>';
            html += '</div>';
            html += '<div class="flex gap-3 mt-2 text-xs text-gray-500">';
            html += '<span class="text-green-600">' + s.available + ' available</span>';
            html += '<span class="text-red-600">' + s.in_use_locked + ' locked</span>';
            html += '<span class="text-amber-600">' + s.in_use_unlocked + ' unlocked</span>';
            if (s.hwtest_failed) html += '<span class="text-purple-600">' + s.hwtest_failed + ' hw failed</span>';
            html += '</div>';
            html += '</div>';
        }
        container.innerHTML = html;
    }

    // --- Stats polling (every 60s) ---

    var hourlyChart = null;

    function initChart() {
        var ctx = document.getElementById('hourly-chart').getContext('2d');
        hourlyChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: [],
                datasets: [{
                    label: 'Sessions Started',
                    data: [],
                    backgroundColor: 'rgba(79, 70, 229, 0.6)',
                    borderColor: 'rgb(79, 70, 229)',
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: {
                        ticks: {
                            maxTicksAllowed: 12,
                            maxRotation: 45,
                            callback: function (val, idx) {
                                var label = this.getLabelForValue(val);
                                // Show only every Nth label to avoid crowding
                                var total = this.chart.data.labels.length;
                                var step = Math.max(1, Math.floor(total / 12));
                                if (idx % step === 0) {
                                    // Format: "Feb 16 14:00"
                                    try {
                                        var d = new Date(label.replace(' ', 'T') + ':00');
                                        return d.toLocaleDateString('en-GB', { month: 'short', day: 'numeric' }) +
                                            ' ' + d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' });
                                    } catch (e) { return label; }
                                }
                                return '';
                            }
                        },
                        grid: { display: false }
                    },
                    y: {
                        beginAtZero: true,
                        ticks: { stepSize: 1 }
                    }
                },
                plugins: {
                    tooltip: {
                        callbacks: {
                            title: function (items) {
                                if (!items.length) return '';
                                var label = items[0].label;
                                try {
                                    var d = new Date(label.replace(' ', 'T') + ':00');
                                    return d.toLocaleDateString('en-GB', { weekday: 'short', month: 'short', day: 'numeric' }) +
                                        ' ' + d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' });
                                } catch (e) { return label; }
                            }
                        }
                    },
                    legend: { display: false }
                }
            }
        });
    }

    function fetchStats() {
        fetch('/api/stats/hourly')
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (hourlyChart && data.hourly) {
                    var labels = [];
                    var values = [];
                    for (var i = 0; i < data.hourly.length; i++) {
                        labels.push(data.hourly[i].hour);
                        values.push(data.hourly[i].locks);
                    }
                    hourlyChart.data.labels = labels;
                    hourlyChart.data.datasets[0].data = values;
                    hourlyChart.update();
                }
            })
            .catch(function () { /* ignore */ });

        fetch('/api/stats/summary')
            .then(function (r) { return r.json(); })
            .then(function (data) {
                document.getElementById('card-denials').textContent = data.denials_today || 0;
            })
            .catch(function () { /* ignore */ });

        fetch('/api/stats/users')
            .then(function (r) { return r.json(); })
            .then(function (data) {
                updateUserTable(data.users);
            })
            .catch(function () { /* ignore */ });

        fetch('/api/stats/denials')
            .then(function (r) { return r.json(); })
            .then(function (data) {
                updateDenials(data.denials);
            })
            .catch(function () { /* ignore */ });
    }

    function updateUserTable(users) {
        var tbody = document.getElementById('user-table-body');
        if (!users || users.length === 0) {
            tbody.innerHTML = '<tr><td colspan="4" class="px-5 py-8 text-center text-gray-400">No session data available</td></tr>';
            return;
        }
        var html = '';
        for (var i = 0; i < users.length; i++) {
            var u = users[i];
            html += '<tr class="border-t border-gray-100">';
            html += '<td class="px-5 py-3 font-medium text-gray-900">' + escapeHtml(u.user) + '</td>';
            html += '<td class="px-5 py-3 text-gray-600">' + u.count + '</td>';
            html += '<td class="px-5 py-3 text-gray-600">' + formatDuration(u.total_time_s) + '</td>';
            html += '<td class="px-5 py-3 text-gray-600">' + formatDuration(u.avg_time_s) + '</td>';
            html += '</tr>';
        }
        tbody.innerHTML = html;
    }

    function updateDenials(denials) {
        var section = document.getElementById('denials-section');
        var tbody = document.getElementById('denials-table-body');
        if (!denials || denials.length === 0) {
            section.classList.add('hidden');
            return;
        }
        section.classList.remove('hidden');
        var html = '';
        // Show most recent first
        for (var i = denials.length - 1; i >= 0; i--) {
            var d = denials[i];
            html += '<tr class="border-t border-gray-100">';
            html += '<td class="px-5 py-3 text-gray-600">' + formatTime(d.timestamp) + '</td>';
            html += '<td class="px-5 py-3 font-medium text-gray-900">' + escapeHtml(d.user) + '</td>';
            html += '<td class="px-5 py-3 text-gray-600">' + escapeHtml(d.boardclass) + '</td>';
            html += '</tr>';
        }
        tbody.innerHTML = html;
    }

    // --- Initialization ---

    document.getElementById('reloadconfig-btn').addEventListener('click', triggerConfigReload);
    document.getElementById('hwtest-btn').addEventListener('click', triggerHwTest);
    initChart();
    fetchBoards();
    fetchStats();

    setInterval(fetchBoards, 10000);
    setInterval(fetchStats, 60000);

})();
