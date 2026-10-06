/* Interactive Dashboard Logic */

let currentRange = 'today';
let timelineChart = null;
let categoryChart = null;
let activityLogCache = [];

function getAuthHeaders() {
  const params = new URLSearchParams(window.location.search);
  const token = params.get('token') || localStorage.getItem('activity_api_token') || '';
  const headers = {};
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  return headers;
}

function handleAuthError(res) {
  if (res.status === 401) {
    const token = prompt('Authentication required. Enter your API Bearer token:');
    if (token) {
      localStorage.setItem('activity_api_token', token.trim());
      refreshAll();
    }
  }
}

// Compute start and end dates according to preset
function getDateRange(range) {
  const now = new Date();
  let fromDate = new Date();
  let toDate = new Date();

  if (range === 'today') {
    fromDate.setHours(0, 0, 0, 0);
  } else if (range === 'yesterday') {
    fromDate.setDate(now.getDate() - 1);
    fromDate.setHours(0, 0, 0, 0);
    toDate.setDate(now.getDate() - 1);
    toDate.setHours(23, 59, 59, 999);
  } else if (range === '7days') {
    fromDate.setDate(now.getDate() - 7);
    fromDate.setHours(0, 0, 0, 0);
  } else if (range === '30days') {
    fromDate.setDate(now.getDate() - 30);
    fromDate.setHours(0, 0, 0, 0);
  }

  return {
    from: fromDate.toISOString(),
    to: toDate.toISOString()
  };
}

async function checkHealth() {
  const pill = document.getElementById('statusPill');
  const text = document.getElementById('statusText');
  try {
    const res = await fetch('/api/v1/health');
    if (res.ok) {
      text.innerText = 'Connected';
      pill.style.background = 'rgba(16, 185, 129, 0.1)';
      pill.style.color = '#10b981';
      pill.style.borderColor = 'rgba(16, 185, 129, 0.2)';
    } else {
      text.innerText = 'Server Degraded';
      pill.style.color = '#f59e0b';
    }
  } catch (err) {
    text.innerText = 'Offline';
    pill.style.background = 'rgba(244, 63, 94, 0.1)';
    pill.style.color = '#f43f5e';
    pill.style.borderColor = 'rgba(244, 63, 94, 0.2)';
  }
}

async function loadSummary() {
  const { from, to } = getDateRange(currentRange);
  try {
    const res = await fetch(
      `/api/v1/analytics/summary?date_from=${encodeURIComponent(from)}&date_to=${encodeURIComponent(to)}`,
      { headers: getAuthHeaders() }
    );
    if (!res.ok) {
      handleAuthError(res);
      return;
    }
    const data = await res.json();

    // Populate KPI cards
    document.getElementById('valActiveTime').innerText = data.formatted_active_time || '0h 00m';
    document.getElementById('valProdScore').innerText = `Score: ${data.productivity_score}% productive`;
    document.getElementById('valIdleTime').innerText = data.formatted_idle_time || '0h 00m';

    const idlePct = data.total_tracked_seconds > 0
      ? Math.round((data.idle_seconds / data.total_tracked_seconds) * 100)
      : 0;
    document.getElementById('valIdlePct').innerText = `${idlePct}% of monitored time`;

    document.getElementById('valTotalTime').innerText = data.formatted_total_time || '0h 00m';
    document.getElementById('valTotalEvents').innerText = `${data.total_events} interval events`;
    document.getElementById('valAppsCount').innerText = data.top_apps ? data.top_apps.length : 0;

    // Render Top Applications
    renderTopApps(data.top_apps || []);

    // Render Category Donut
    renderCategoryChart(data.categories || []);
  } catch (e) {
    console.error('Error loading summary:', e);
  }
}

function renderTopApps(apps) {
  const container = document.getElementById('topAppsList');
  const countBadge = document.getElementById('topAppsCount');
  countBadge.innerText = `${apps.length} apps`;

  if (!apps || apps.length === 0) {
    container.innerHTML = '<p class="empty-state">No app activity recorded for this period.</p>';
    return;
  }

  container.innerHTML = apps.map(app => `
    <div class="app-rank-item">
      <div class="app-rank-meta">
        <div class="app-name-wrap">
          <span>${escapeHtml(app.process_name)}</span>
          <span class="app-cat-tag">${escapeHtml(app.category)}</span>
        </div>
        <div>
          <strong>${app.formatted_duration}</strong>
          <span style="color:#94a3b8; font-size:0.75rem;">(${app.percentage}%)</span>
        </div>
      </div>
      <div class="progress-bar-bg">
        <div class="progress-bar-fill" style="width: ${Math.min(100, Math.max(2, app.percentage))}%;"></div>
      </div>
    </div>
  `).join('');
}

function renderCategoryChart(categories) {
  const canvas = document.getElementById('categoryChart');
  if (!canvas) return;

  if (typeof Chart === 'undefined') {
    canvas.parentElement.innerHTML = '<p class="empty-state" style="padding:1.5rem;">Chart.js CDN is unavailable in offline mode. See summary above and log below.</p>';
    return;
  }

  const ctx = canvas.getContext('2d');
  const labels = categories.map(c => c.category);
  const data = categories.map(c => Math.round(c.duration_seconds / 60)); // minutes

  const palette = [
    '#38bdf8', '#818cf8', '#34d399', '#f43f5e',
    '#fbbf24', '#a855f7', '#94a3b8', '#06b6d4'
  ];

  if (categoryChart) {
    categoryChart.destroy();
  }

  if (labels.length === 0) {
    categoryChart = new Chart(ctx, {
      type: 'doughnut',
      data: {
        labels: ['No Data'],
        datasets: [{ data: [1], backgroundColor: ['#334155'] }]
      },
      options: { responsive: true, maintainAspectRatio: false }
    });
    return;
  }

  categoryChart = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: labels,
      datasets: [{
        data: data,
        backgroundColor: palette.slice(0, labels.length),
        borderWidth: 0
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          position: 'bottom',
          labels: { color: '#94a3b8', boxWidth: 12, font: { size: 11 } }
        },
        tooltip: {
          callbacks: {
            label: (ctx) => ` ${ctx.label}: ${ctx.raw} mins`
          }
        }
      }
    }
  });
}

async function loadTimeline() {
  const { from, to } = getDateRange(currentRange);
  let bucketHours = 1;
  if (currentRange === '7days') bucketHours = 6;
  if (currentRange === '30days') bucketHours = 24;

  try {
    const res = await fetch(
      `/api/v1/analytics/timeline?date_from=${encodeURIComponent(from)}&date_to=${encodeURIComponent(to)}&bucket_hours=${bucketHours}`,
      { headers: getAuthHeaders() }
    );
    if (!res.ok) {
      handleAuthError(res);
      return;
    }
    const buckets = await res.json();

    const canvas = document.getElementById('timelineChart');
    if (!canvas) return;

    if (typeof Chart === 'undefined') {
      canvas.parentElement.innerHTML = '<p class="empty-state" style="padding:1.5rem;">Chart.js CDN is unavailable in offline mode. See activity stream below.</p>';
      return;
    }

    const ctx = canvas.getContext('2d');
    const labels = buckets.map(b => b.label);
    const activeData = buckets.map(b => Math.round(b.active_seconds / 60));
    const idleData = buckets.map(b => Math.round(b.idle_seconds / 60));

    if (timelineChart) {
      timelineChart.destroy();
    }

    timelineChart = new Chart(ctx, {
      type: 'bar',
      data: {
        labels: labels.length ? labels : ['00:00', '06:00', '12:00', '18:00'],
        datasets: [
          {
            label: 'Active (mins)',
            data: activeData.length ? activeData : [0, 0, 0, 0],
            backgroundColor: '#3b82f6',
            borderRadius: 4
          },
          {
            label: 'Idle (mins)',
            data: idleData.length ? idleData : [0, 0, 0, 0],
            backgroundColor: 'rgba(245, 158, 11, 0.6)',
            borderRadius: 4
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          x: {
            stacked: true,
            grid: { display: false },
            ticks: { color: '#94a3b8', font: { size: 10 } }
          },
          y: {
            stacked: true,
            grid: { color: 'rgba(51, 65, 85, 0.5)' },
            ticks: { color: '#94a3b8', font: { size: 10 } }
          }
        },
        plugins: {
          legend: {
            labels: { color: '#cbd5e1', font: { size: 11 } }
          }
        }
      }
    });
  } catch (e) {
    console.error('Error loading timeline:', e);
  }
}

async function loadActivityLog() {
  const { from, to } = getDateRange(currentRange);
  try {
    const res = await fetch(
      `/api/v1/activities?date_from=${encodeURIComponent(from)}&date_to=${encodeURIComponent(to)}&limit=100`,
      { headers: getAuthHeaders() }
    );
    if (!res.ok) {
      handleAuthError(res);
      return;
    }
    const data = await res.json();
    activityLogCache = data.items || [];
    renderActivityLog(activityLogCache);
  } catch (e) {
    console.error('Error loading activity log:', e);
  }
}

function renderActivityLog(items) {
  const tbody = document.getElementById('activityLogBody');
  if (!tbody) return;

  if (!items || items.length === 0) {
    tbody.innerHTML = '<tr><td colspan="6" class="text-center empty-state">No activity records match the selected filter.</td></tr>';
    return;
  }

  tbody.innerHTML = items.map(item => {
    const durMins = Math.round(item.duration_seconds / 60);
    const durText = durMins > 0 ? `${durMins}m` : `${Math.round(item.duration_seconds)}s`;
    const timeFormatted = item.start_time.substring(11, 16);

    const isRedacted = item.window_title.includes('[REDACTED]') || item.window_title.includes('[Private');

    return `
      <tr>
        <td>${timeFormatted}</td>
        <td><strong>${durText}</strong></td>
        <td>${escapeHtml(item.process_name)}</td>
        <td><span class="app-cat-tag">${escapeHtml(item.category)}</span></td>
        <td title="${escapeHtml(item.window_title)}">
          ${isRedacted ? '🔒 ' : ''}${escapeHtml(item.window_title.substring(0, 50))}${item.window_title.length > 50 ? '...' : ''}
        </td>
        <td>
          <span class="badge-state ${item.is_idle ? 'state-idle' : 'state-active'}">
            ${item.is_idle ? '☕ Idle' : '⚡ Active'}
          </span>
        </td>
      </tr>
    `;
  }).join('');
}

function escapeHtml(str) {
  if (!str) return '';
  return str.replace(/[&<>"']/g, m => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;'
  }[m]));
}

function setupEventListeners() {
  document.querySelectorAll('.preset-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
      document.querySelectorAll('.preset-btn').forEach(b => b.classList.remove('active'));
      e.target.classList.add('active');
      currentRange = e.target.getAttribute('data-range');
      refreshAll();
    });
  });

  const refreshBtn = document.getElementById('refreshBtn');
  if (refreshBtn) {
    refreshBtn.addEventListener('click', refreshAll);
  }

  const searchInput = document.getElementById('logSearchInput');
  if (searchInput) {
    searchInput.addEventListener('input', (e) => {
      const query = e.target.value.toLowerCase().trim();
      if (!query) {
        renderActivityLog(activityLogCache);
      } else {
        const filtered = activityLogCache.filter(item =>
          item.process_name.toLowerCase().includes(query) ||
          item.window_title.toLowerCase().includes(query) ||
          item.category.toLowerCase().includes(query)
        );
        renderActivityLog(filtered);
      }
    });
  }
}

async function loadMachines() {
  const tbody = document.getElementById('machinesTableBody');
  if (!tbody) return;
  try {
    const res = await fetch('/api/v1/machines', { headers: getAuthHeaders() });
    if (!res.ok) return;
    const machines = await res.json();
    if (!machines || machines.length === 0) {
      tbody.innerHTML = `<tr><td colspan="6" class="text-center empty-state">Chưa có máy tính nào kết nối. Hãy chạy tracker trên máy tính để tạo vùng nhớ!</td></tr>`;
      return;
    }
    tbody.innerHTML = machines.map(m => {
      const lastSeen = m.last_seen ? new Date(m.last_seen).toLocaleTimeString() : 'N/A';
      const mName = escapeHtml(m.machine_name || m.client_id || 'Unknown');
      const folder = escapeHtml(m.storage_folder || m.client_id || 'Unknown');
      const records = m.total_records || 0;
      const mb = m.disk_mb || 0;
      const app = escapeHtml(m.last_active_app || '-');
      const title = escapeHtml(m.last_active_title ? m.last_active_title.slice(0, 35) : '');
      return `
        <tr>
          <td><strong style="color:#60a5fa">💻 ${mName}</strong></td>
          <td><code style="background:#1e293b;padding:2px 6px;border-radius:4px;color:#38bdf8">data/machines/${folder}/</code></td>
          <td>${lastSeen}</td>
          <td><span class="badge" style="background:#1e3a8a;color:#93c5fd">${records} bản ghi</span></td>
          <td><span style="color:#a7f3d0">${mb} MB</span></td>
          <td><span class="proc-name">${app}</span> ${title}</td>
        </tr>
      `;
    }).join('');
  } catch (e) {
    console.error('Failed to load machines:', e);
  }
}

async function loadLiveTasks() {
  const container = document.getElementById('liveTaskbarList');
  const mBadge = document.getElementById('liveMachineBadge');
  const cBadge = document.getElementById('liveCountBadge');
  const tBadge = document.getElementById('liveTimeBadge');
  if (!container) return;

  try {
    const res = await fetch('/api/v1/machines/live', { headers: getAuthHeaders() });
    if (!res.ok) return;
    const machines = await res.json();

    if (!machines || machines.length === 0) {
      if (mBadge) mBadge.innerText = '💻 Chưa có máy kết nối';
      if (cBadge) cBadge.innerText = '0 tasks';
      return;
    }

    // Select primary machine (online first, or latest)
    const machine = machines[0];
    const onlineTag = machine.is_online ? '🟢 Online' : '⚪ Offline';
    const lastTime = machine.last_updated ? new Date(machine.last_updated).toLocaleTimeString() : 'N/A';
    const tasks = machine.tasks || [];

    if (mBadge) mBadge.innerHTML = `💻 <strong>${escapeHtml(machine.client_id)}</strong> (${onlineTag})`;
    if (cBadge) cBadge.innerText = `${tasks.length} tasks taskbar`;
    if (tBadge) tBadge.innerText = `Cập nhật: ${lastTime}`;

    if (tasks.length === 0) {
      container.innerHTML = `
        <div class="empty-state" style="grid-column: 1 / -1; text-align: center; color: #94a3b8; padding: 2rem;">
          Không có ứng dụng nào trên thanh taskbar lúc ${lastTime}.
        </div>
      `;
      return;
    }

    container.innerHTML = tasks.map(t => {
      const isFocused = Boolean(t.is_focused);
      const borderStyle = isFocused
        ? 'border: 1.5px solid #10b981; background: rgba(16, 185, 129, 0.1); box-shadow: 0 0 15px rgba(16, 185, 129, 0.2);'
        : 'border: 1px solid #334155; background: rgba(30, 41, 59, 0.7);';
      const badgeHtml = isFocused
        ? `<span style="background:rgba(16,185,129,0.25); color:#34d399; border:1px solid rgba(16,185,129,0.5); padding:2px 8px; border-radius:12px; font-size:0.75rem; font-weight:700;">🟢 ĐANG SỬ DỤNG [FOCUS]</span>`
        : `<span style="background:rgba(148,163,184,0.15); color:#94a3b8; border:1px solid rgba(148,163,184,0.3); padding:2px 8px; border-radius:12px; font-size:0.75rem;">⚪ ĐANG MỞ [OPEN]</span>`;

      const title = escapeHtml(t.window_title || '(Không có tiêu đề)');
      const proc = escapeHtml(t.process_name || 'unknown.exe');
      const pidText = t.pid ? `PID: ${t.pid}` : '';

      return `
        <div style="border-radius:10px; padding:12px 14px; display:flex; flex-direction:column; gap:6px; transition: all 0.2s ease; ${borderStyle}">
          <div style="display:flex; justify-content:space-between; align-items:center; gap:8px;">
            <div style="display:flex; align-items:center; gap:6px; overflow:hidden;">
              <span style="font-size:1.1rem;">💻</span>
              <strong style="color:#f8fafc; font-size:0.95rem; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">${proc}</strong>
              <span style="font-size:0.75rem; color:#64748b;">${pidText}</span>
            </div>
            <div>${badgeHtml}</div>
          </div>
          <div style="font-size:0.85rem; color:#cbd5e1; line-height:1.3; overflow:hidden; text-overflow:ellipsis; display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical;" title="${title}">
            ${title}
          </div>
        </div>
      `;
    }).join('');

  } catch (err) {
    console.error('Failed to load live taskbar tasks:', err);
  }
}

async function refreshAll() {
  await Promise.all([
    checkHealth(),
    loadSummary(),
    loadTimeline(),
    loadActivityLog(),
    loadMachines(),
    loadLiveTasks()
  ]);
}

// Initialize on page load
window.addEventListener('DOMContentLoaded', () => {
  setupEventListeners();
  refreshAll();
  // Auto-refresh summary, logs and machines every 30 seconds
  setInterval(refreshAll, 30000);
  // Real-time live taskbar updates every 3 seconds (3000ms)
  setInterval(loadLiveTasks, 3000);
});
