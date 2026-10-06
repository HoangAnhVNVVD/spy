/* Interactive Dashboard Logic */

const urlParams = new URLSearchParams(window.location.search);
let currentMachine = urlParams.get('machine') || '';
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
  let summaryUrl = `/api/v1/analytics/summary?date_from=${encodeURIComponent(from)}&date_to=${encodeURIComponent(to)}`;
  if (currentMachine) {
    summaryUrl += `&client_id=${encodeURIComponent(currentMachine)}`;
  }
  try {
    const res = await fetch(summaryUrl, { headers: getAuthHeaders() });
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

  let timelineUrl = `/api/v1/analytics/timeline?date_from=${encodeURIComponent(from)}&date_to=${encodeURIComponent(to)}&bucket_hours=${bucketHours}`;
  if (currentMachine) {
    timelineUrl += `&client_id=${encodeURIComponent(currentMachine)}`;
  }

  try {
    const res = await fetch(timelineUrl, { headers: getAuthHeaders() });
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
  let logUrl = `/api/v1/activities?date_from=${encodeURIComponent(from)}&date_to=${encodeURIComponent(to)}&limit=100`;
  if (currentMachine) {
    logUrl += `&client_id=${encodeURIComponent(currentMachine)}`;
  }
  try {
    const res = await fetch(logUrl, { headers: getAuthHeaders() });
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

function populateMachineSelector(machines) {
  const select = document.getElementById('machineSelect');
  if (!select) return;

  const currentVal = currentMachine;
  let optionsHtml = `<option value="">🌐 Tất cả máy tính (Tổng hợp)</option>`;
  if (machines && machines.length > 0) {
    optionsHtml += machines.map(m => {
      const isOnline = Boolean(m.is_online);
      const statusIcon = isOnline ? '🟢' : '⚪';
      const mName = escapeHtml(m.machine_name || m.client_id || 'Unknown');
      const recs = m.total_records ? ` (${m.total_records} logs)` : '';
      return `<option value="${mName}">${statusIcon} 💻 ${mName}${recs}</option>`;
    }).join('');
  }

  select.innerHTML = optionsHtml;
  select.value = currentVal;
}

window.selectMachine = function(machineName) {
  currentMachine = machineName || '';
  const select = document.getElementById('machineSelect');
  if (select) select.value = currentMachine;

  const url = new URL(window.location.href);
  if (currentMachine) {
    url.searchParams.set('machine', currentMachine);
  } else {
    url.searchParams.delete('machine');
  }
  window.history.replaceState({}, '', url.toString());

  refreshAll();
  window.scrollTo({ top: 0, behavior: 'smooth' });
};

let currentModalMachine = '';

window.openDiskLogModal = async function(machineName) {
  currentModalMachine = machineName;
  const modal = document.getElementById('diskLogModal');
  const title = document.getElementById('modalMachineTitle');
  const content = document.getElementById('modalLogContent');
  const lineCount = document.getElementById('modalLineCount');
  if (!modal || !content) return;

  modal.style.display = 'flex';
  if (title) title.innerText = `Nhật ký ổ đĩa máy: ${machineName}`;
  content.innerText = 'Đang đọc trực tiếp file log từ ổ đĩa Railway...';
  if (lineCount) lineCount.innerText = 'Đang tải...';

  try {
    const res = await fetch(`/api/v1/machines/${encodeURIComponent(machineName)}/logs?limit=300`, {
      headers: getAuthHeaders()
    });
    if (!res.ok) {
      content.innerText = `Không tìm thấy file log trên đĩa cho máy '${machineName}'.`;
      return;
    }
    const data = await res.json();
    if (!data.lines || data.lines.length === 0) {
      content.innerText = `Chưa có bản ghi nào trong daily/*.log của máy '${machineName}'.`;
      if (lineCount) lineCount.innerText = '0 dòng';
      return;
    }
    content.innerText = data.lines.join('\n');
    if (lineCount) lineCount.innerText = `${data.lines.length} dòng gần nhất`;
  } catch (err) {
    content.innerText = `Lỗi đọc log: ${err}`;
  }
};

function setupEventListeners() {
  document.querySelectorAll('.preset-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
      document.querySelectorAll('.preset-btn').forEach(b => b.classList.remove('active'));
      e.target.classList.add('active');
      currentRange = e.target.getAttribute('data-range');
      refreshAll();
    });
  });

  const machineSelect = document.getElementById('machineSelect');
  if (machineSelect) {
    machineSelect.addEventListener('change', (e) => {
      selectMachine(e.target.value);
    });
  }

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

  // Modal event listeners
  const closeModalBtn = document.getElementById('closeModalBtn');
  const diskLogModal = document.getElementById('diskLogModal');
  if (closeModalBtn && diskLogModal) {
    closeModalBtn.addEventListener('click', () => {
      diskLogModal.style.display = 'none';
    });
    diskLogModal.addEventListener('click', (e) => {
      if (e.target === diskLogModal) {
        diskLogModal.style.display = 'none';
      }
    });
  }

  const modalRefreshBtn = document.getElementById('modalRefreshBtn');
  if (modalRefreshBtn) {
    modalRefreshBtn.addEventListener('click', () => {
      if (currentModalMachine) {
        openDiskLogModal(currentModalMachine);
      }
    });
  }

  // Security sub-tabs switcher
  document.querySelectorAll('.sec-tab-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
      document.querySelectorAll('.sec-tab-btn').forEach(b => b.classList.remove('active'));
      const target = e.currentTarget;
      target.classList.add('active');
      const tabName = target.getAttribute('data-sectab');
      const tabAlerts = document.getElementById('secTabAlerts');
      const tabPlaybook = document.getElementById('secTabPlaybook');
      const tabKnowledge = document.getElementById('secTabKnowledge');
      if (tabAlerts) tabAlerts.style.display = tabName === 'alerts' ? 'block' : 'none';
      if (tabPlaybook) tabPlaybook.style.display = tabName === 'playbook' ? 'block' : 'none';
      if (tabKnowledge) tabKnowledge.style.display = tabName === 'knowledge' ? 'block' : 'none';
    });
  });

  // Security actions
  const btnRunTriage = document.getElementById('btnRunTriage');
  if (btnRunTriage) btnRunTriage.addEventListener('click', runAutomatedTriage);

  const btnToggleIso = document.getElementById('btnToggleIsolation');
  if (btnToggleIso) btnToggleIso.addEventListener('click', toggleMachineIsolation);

  const btnExportForensic = document.getElementById('btnExportForensics');
  if (btnExportForensic) btnExportForensic.addEventListener('click', openForensicModal);

  const closeForensicBtn = document.getElementById('closeForensicModalBtn');
  const forensicModal = document.getElementById('forensicModal');
  if (closeForensicBtn && forensicModal) {
    closeForensicBtn.addEventListener('click', () => { forensicModal.style.display = 'none'; });
    forensicModal.addEventListener('click', (e) => {
      if (e.target === forensicModal) forensicModal.style.display = 'none';
    });
  }

  const btnDownloadForensic = document.getElementById('btnDownloadForensicsJson');
  if (btnDownloadForensic) {
    btnDownloadForensic.addEventListener('click', downloadForensicJson);
  }

  const kbSearchInput = document.getElementById('kbSearchInput');
  if (kbSearchInput) {
    let kbDebounce = null;
    kbSearchInput.addEventListener('input', (e) => {
      clearTimeout(kbDebounce);
      kbDebounce = setTimeout(() => {
        loadSecurityKnowledge(e.target.value);
      }, 250);
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

    // Sync selector options
    populateMachineSelector(machines);

    if (!machines || machines.length === 0) {
      tbody.innerHTML = `<tr><td colspan="7" class="text-center empty-state">Chưa có máy tính nào kết nối. Hãy chạy tracker trên máy tính để tạo vùng nhớ!</td></tr>`;
      return;
    }
    tbody.innerHTML = machines.map(m => {
      const lastSeen = m.last_seen ? new Date(m.last_seen).toLocaleTimeString() : 'N/A';
      const mName = escapeHtml(m.machine_name || m.client_id || 'Unknown');
      const folder = escapeHtml(m.storage_folder || m.client_id || 'Unknown');
      const records = m.total_records || 0;
      const mb = m.disk_mb || 0;
      const app = escapeHtml(m.last_active_app || '-');
      const title = escapeHtml(m.last_active_title ? m.last_active_title.slice(0, 30) : '');
      const isSelected = (currentMachine && currentMachine === mName);
      const rowHighlight = isSelected ? 'background: rgba(59, 130, 246, 0.12);' : '';

      return `
        <tr style="${rowHighlight}">
          <td><strong style="color:#60a5fa">💻 ${mName}</strong> ${isSelected ? '<span class="badge" style="background:#10b981; color:#fff; font-size:10px;">Đang chọn</span>' : ''}</td>
          <td><code style="background:#1e293b;padding:2px 6px;border-radius:4px;color:#38bdf8">data/machines/${folder}/</code></td>
          <td>${lastSeen}</td>
          <td><span class="badge" style="background:#1e3a8a;color:#93c5fd">${records} bản ghi</span></td>
          <td><span style="color:#a7f3d0">${mb} MB</span></td>
          <td><span class="proc-name">${app}</span> ${title}</td>
          <td>
            <button class="btn-action-view" onclick="selectMachine('${mName}')" title="Chỉ xem dữ liệu của máy này">👁️ Xem riêng</button>
            <button class="btn-action-log" onclick="openDiskLogModal('${mName}')" title="Xem file log daily/*.log trên ổ đĩa">📄 Log đĩa</button>
          </td>
        </tr>
      `;
    }).join('');
  } catch (e) {
    console.error('Failed to load machines:', e);
  }
}

function renderTaskCard(t) {
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
}

async function loadLiveTasks() {
  const container = document.getElementById('liveTaskbarList');
  const mBadge = document.getElementById('liveMachineBadge');
  const cBadge = document.getElementById('liveCountBadge');
  const tBadge = document.getElementById('liveTimeBadge');
  const subTitle = document.getElementById('liveTaskbarSubtitle');
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

    // 1. ISOLATED SINGLE MACHINE VIEW
    if (currentMachine) {
      const targetMachine = machines.find(m => m.client_id === currentMachine);
      if (!targetMachine) {
        if (mBadge) mBadge.innerHTML = `💻 <strong>${escapeHtml(currentMachine)}</strong> (⚪ Offline)`;
        if (cBadge) cBadge.innerText = '0 tasks';
        if (subTitle) subTitle.innerHTML = `Đang theo dõi riêng máy: <strong style="color:#60a5fa">${escapeHtml(currentMachine)}</strong>`;
        container.innerHTML = `
          <div class="empty-state" style="grid-column: 1 / -1; text-align: center; color: #94a3b8; padding: 2rem;">
            Máy tính <strong>${escapeHtml(currentMachine)}</strong> hiện chưa có phiên làm việc trực tuyến nào.
          </div>
        `;
        return;
      }

      const onlineTag = targetMachine.is_online ? '🟢 Online' : '⚪ Offline';
      const lastTime = targetMachine.last_updated ? new Date(targetMachine.last_updated).toLocaleTimeString() : 'N/A';
      const tasks = targetMachine.tasks || [];

      if (mBadge) mBadge.innerHTML = `💻 <strong>${escapeHtml(targetMachine.client_id)}</strong> (${onlineTag})`;
      if (cBadge) cBadge.innerText = `${tasks.length} tasks taskbar`;
      if (tBadge) tBadge.innerText = `Cập nhật: ${lastTime}`;
      if (subTitle) subTitle.innerHTML = `Đang theo dõi riêng máy: <strong style="color:#60a5fa">${escapeHtml(targetMachine.client_id)}</strong> (cô lập 100%)`;

      if (tasks.length === 0) {
        container.innerHTML = `
          <div class="empty-state" style="grid-column: 1 / -1; text-align: center; color: #94a3b8; padding: 2rem;">
            Không có ứng dụng nào trên thanh taskbar lúc ${lastTime}.
          </div>
        `;
        return;
      }

      container.innerHTML = tasks.map(t => renderTaskCard(t)).join('');
      return;
    }

    // 2. MULTI-MACHINE ALL-IN-ONE VIEW
    const totalTasks = machines.reduce((sum, m) => sum + (m.tasks ? m.tasks.length : 0), 0);
    const onlineCount = machines.filter(m => m.is_online).length;
    if (mBadge) mBadge.innerHTML = `🌐 <strong>Tất cả máy</strong> (${onlineCount}/${machines.length} Online)`;
    if (cBadge) cBadge.innerText = `${totalTasks} tasks tổng`;
    if (subTitle) subTitle.innerText = `Hiển thị danh sách ứng dụng trên thanh Taskbar của tất cả ${machines.length} máy tính kết nối`;

    container.innerHTML = machines.map(m => {
      const isOnline = Boolean(m.is_online);
      const onlineTag = isOnline ? '🟢 Online' : '⚪ Offline';
      const lastTime = m.last_updated ? new Date(m.last_updated).toLocaleTimeString() : 'N/A';
      const tasks = m.tasks || [];

      return `
        <div style="grid-column: 1 / -1; background: rgba(15, 23, 42, 0.6); border: 1px solid #334155; border-radius: 12px; padding: 14px; margin-bottom: 8px;">
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom: 12px; border-bottom: 1px solid rgba(51, 65, 85, 0.4); padding-bottom: 8px;">
            <div style="display:flex; align-items:center; gap:8px;">
              <strong style="color:#60a5fa; font-size:1rem;">💻 ${escapeHtml(m.client_id)}</strong>
              <span class="badge" style="background:${isOnline ? 'rgba(16,185,129,0.15)' : 'rgba(148,163,184,0.1)'}; color:${isOnline ? '#34d399' : '#94a3b8'};">${onlineTag}</span>
              <span style="font-size:0.8rem; color:#64748b;">(Cập nhật: ${lastTime})</span>
            </div>
            <button class="btn-action-view" onclick="selectMachine('${escapeHtml(m.client_id)}')">👁️ Chỉ xem máy này</button>
          </div>
          <div style="display:grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 10px;">
            ${tasks.length > 0 ? tasks.map(t => renderTaskCard(t)).join('') : '<p class="empty-state" style="padding:1rem;">Không có ứng dụng nào đang mở.</p>'}
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
    loadLiveTasks(),
    loadSecurityOverview(),
    loadSecurityPlaybook(),
    loadSecurityKnowledge()
  ]);
}

let currentForensicData = null;
let currentMachineIsIsolated = false;

async function loadSecurityOverview() {
  try {
    const url = `/api/v1/security/alerts${currentMachine ? '?client_id=' + encodeURIComponent(currentMachine) : ''}`;
    const res = await fetch(url, { headers: getAuthHeaders() });
    if (!res.ok) return;
    const data = await res.json();

    const riskBadge = document.getElementById('securityRiskBadge');
    const alertCount = document.getElementById('alertCountBadge');
    const alertsList = document.getElementById('securityAlertsList');

    if (alertCount) alertCount.innerText = data.alert_count || 0;

    if (riskBadge) {
      const score = data.risk_score || 0;
      const level = data.risk_level || 'NORMAL';
      let badgeBg = 'rgba(16, 185, 129, 0.2)';
      let badgeColor = '#34d399';
      let label = `🟢 ${score}/100 - An Toàn`;

      if (level === 'CRITICAL') {
        badgeBg = 'rgba(239, 68, 68, 0.25)';
        badgeColor = '#f87171';
        label = `🔴 ${score}/100 - NGUY CẤP`;
      } else if (level === 'HIGH') {
        badgeBg = 'rgba(249, 115, 22, 0.25)';
        badgeColor = '#fb923c';
        label = `🟠 ${score}/100 - Rủi Ro Cao`;
      } else if (level === 'MEDIUM') {
        badgeBg = 'rgba(234, 179, 8, 0.25)';
        badgeColor = '#facc15';
        label = `🟡 ${score}/100 - Cảnh Báo Vừa`;
      } else if (level === 'LOW') {
        badgeBg = 'rgba(59, 130, 246, 0.2)';
        badgeColor = '#60a5fa';
        label = `🔵 ${score}/100 - Rủi Ro Thấp`;
      }

      riskBadge.style.background = badgeBg;
      riskBadge.style.color = badgeColor;
      riskBadge.innerText = label;
    }

    if (alertsList) {
      if (!data.alerts || data.alerts.length === 0) {
        alertsList.innerHTML = `
          <div class="empty-state" style="padding: 1.5rem; text-align: center; color: #34d399; background: rgba(16, 185, 129, 0.05); border: 1px solid rgba(16, 185, 129, 0.2); border-radius: 8px;">
            ✅ Không phát hiện dấu hiệu tấn công (IOA/IOC) nào. Hệ thống hoạt động an toàn theo nguyên tắc phòng thủ.
          </div>
        `;
      } else {
        alertsList.innerHTML = data.alerts.map(a => {
          const sevClass = `sev-${(a.severity || 'low').toLowerCase()}`;
          return `
            <div class="alert-item-card ${sevClass}">
              <div class="alert-header">
                <div style="display:flex; align-items:center; gap:8px;">
                  <span class="badge" style="background:#0f172a; font-weight:700;">${escapeHtml(a.id || 'IOA')}</span>
                  <span class="badge" style="background:${a.severity === 'CRITICAL' ? '#ef4444' : a.severity === 'HIGH' ? '#f97316' : '#eab308'}; color:#fff; font-weight:700;">
                    ${escapeHtml(a.severity)}
                  </span>
                  <strong style="color:#f8fafc; font-size:0.95rem;">${escapeHtml(a.process_name || 'System')}</strong>
                </div>
                <span style="font-size:0.8rem; color:#94a3b8;">${escapeHtml(a.timestamp || '')}</span>
              </div>
              <p style="margin:4px 0; font-size:0.9rem; color:#e2e8f0;">${escapeHtml(a.message)}</p>
              <div style="font-size:0.82rem; color:#cbd5e1; background:rgba(0,0,0,0.25); padding:6px 10px; border-radius:6px;">
                💡 <strong>Hành động khuyến nghị:</strong> ${escapeHtml(a.recommendation || 'Kiểm tra chi tiết tiến trình.')}
              </div>
            </div>
          `;
        }).join('');
      }
    }
  } catch (err) {
    console.error('Failed to load security overview:', err);
  }
}

async function loadSecurityPlaybook() {
  const container = document.getElementById('playbookStepsList');
  if (!container) return;
  try {
    const res = await fetch('/api/v1/security/workflow', { headers: getAuthHeaders() });
    if (!res.ok) return;
    const data = await res.json();
    const steps = data.steps || [];

    const targetLabel = document.getElementById('playbookTargetLabel');
    if (targetLabel) {
      targetLabel.innerText = currentMachine ? `Đích: Máy ${currentMachine}` : 'Đích: Tất cả máy tính';
    }

    container.innerHTML = steps.map(s => {
      return `
        <div class="playbook-step-card" id="stepCard_${s.step_number}">
          <div class="step-card-header">
            <span class="badge" style="background: rgba(59, 130, 246, 0.2); color: #60a5fa; font-weight: 700;">Bước ${s.step_number}</span>
            <span class="badge" style="background: rgba(148, 163, 184, 0.1); color: #94a3b8; font-size:0.75rem;">${escapeHtml(s.category)}</span>
          </div>
          <h4 style="margin: 2px 0; color: #f1f5f9; font-size: 0.95rem;">${escapeHtml(s.title)}</h4>
          <p class="step-finding" style="margin: 0; font-size: 0.82rem; color: #94a3b8;">${escapeHtml(s.description || 'Chưa chạy triage.')}</p>
        </div>
      `;
    }).join('');
  } catch (err) {
    console.error('Failed to load security playbook:', err);
  }
}

async function runAutomatedTriage() {
  const target = currentMachine || (document.getElementById('machineSelect') ? document.getElementById('machineSelect').value : '');
  if (!target) {
    alert('Vui lòng chọn một máy tính cụ thể ở dropdown góc trên để chạy Triage 20 bước chuyên sâu!');
    return;
  }

  const btn = document.getElementById('btnRunTriage');
  if (btn) btn.innerText = '⏳ Đang phân tích triage...';

  try {
    const res = await fetch(`/api/v1/machines/${encodeURIComponent(target)}/security-triage`, { headers: getAuthHeaders() });
    if (!res.ok) {
      alert('Không thể thực hiện triage: ' + res.statusText);
      return;
    }
    const triage = await res.json();

    // Switch to playbook tab
    const tabPlaybookBtn = document.querySelector('[data-sectab="playbook"]');
    if (tabPlaybookBtn) tabPlaybookBtn.click();

    // Update isolation status
    currentMachineIsIsolated = Boolean(triage.is_isolated);
    updateIsolationUI(currentMachineIsIsolated, target);

    // Update steps findings
    const steps = triage.workflow_steps || [];
    steps.forEach(s => {
      const card = document.getElementById(`stepCard_${s.step_number}`);
      if (card) {
        const findingEl = card.querySelector('.step-finding');
        if (findingEl) {
          findingEl.innerHTML = `<strong style="color:${s.status === 'FLAGGED' ? '#ef4444' : s.status === 'WARNING' ? '#f59e0b' : '#34d399'}">[${escapeHtml(s.status)}]</strong> ${escapeHtml(s.finding)}`;
        }
      }
    });

    alert(`Hoàn thành Triage 20 bước cho máy '${target}'! Đánh giá rủi ro: ${triage.risk_label} (Điểm: ${triage.risk_score}/100)`);
  } catch (err) {
    console.error('Failed to run triage:', err);
    alert('Lỗi khi chạy triage: ' + err.message);
  } finally {
    if (btn) btn.innerText = '⚡ Chạy Triage 20 Bước';
  }
}

function updateIsolationUI(isIsolated, target) {
  const badge = document.getElementById('isolationStatusBadge');
  const btn = document.getElementById('btnToggleIsolation');
  if (badge) {
    if (isIsolated) {
      badge.style.background = 'rgba(239, 68, 68, 0.25)';
      badge.style.color = '#f87171';
      badge.innerText = '🔴 ĐÃ BỊ CÔ LẬP / QUARANTINED';
    } else {
      badge.style.background = 'rgba(59, 130, 246, 0.15)';
      badge.style.color = '#60a5fa';
      badge.innerText = '[Bình thường - Mở]';
    }
  }
  if (btn) {
    btn.innerText = isIsolated ? '🟢 Hủy Cô Lập Endpoint' : '🔴 Cô lập Endpoint';
    btn.style.background = isIsolated ? '#10b981' : '#dc2626';
  }
}

async function toggleMachineIsolation() {
  const target = currentMachine || (document.getElementById('machineSelect') ? document.getElementById('machineSelect').value : '');
  if (!target) {
    alert('Vui lòng chọn một máy tính cụ thể để thực hiện cô lập/hủy cô lập!');
    return;
  }

  const action = currentMachineIsIsolated ? 'unisolate' : 'isolate';
  const confirmMsg = currentMachineIsIsolated
    ? `Bạn có chắc chắn muốn HỦY CÔ LẬP cho máy '${target}' không?`
    : `CẢNH BÁO: Bạn có chắc chắn muốn CÔ LẬP (Quarantine) máy '${target}' theo Bước 11 của Playbook không?`;

  if (!confirm(confirmMsg)) return;

  try {
    const res = await fetch(`/api/v1/machines/${encodeURIComponent(target)}/${action}`, {
      method: 'POST',
      headers: getAuthHeaders()
    });
    if (res.status === 401) {
      handleAuthError(res);
      return;
    }
    const data = await res.json();
    currentMachineIsIsolated = Boolean(data.is_isolated);
    updateIsolationUI(currentMachineIsIsolated, target);
    alert(data.message || 'Thao tác cô lập thành công!');
    refreshAll();
  } catch (err) {
    console.error('Failed to toggle isolation:', err);
    alert('Lỗi khi thay đổi trạng thái cô lập: ' + err.message);
  }
}

async function loadSecurityKnowledge(query = '') {
  const grid = document.getElementById('kbTopicsGrid');
  const countLabel = document.getElementById('kbTopicCount');
  if (!grid) return;
  try {
    const url = `/api/v1/security/knowledge${query ? '?q=' + encodeURIComponent(query) : ''}`;
    const res = await fetch(url, { headers: getAuthHeaders() });
    if (!res.ok) return;
    const data = await res.json();
    const topics = data.topics || [];

    if (countLabel) countLabel.innerText = `${topics.length} chủ đề indexed`;

    if (topics.length === 0) {
      grid.innerHTML = `<p class="empty-state" style="grid-column: 1 / -1; text-align: center;">Không tìm thấy chủ đề phù hợp với '${escapeHtml(query)}'.</p>`;
      return;
    }

    grid.innerHTML = topics.map(t => {
      const desc = t.descriptions ? t.descriptions.join('<br>') : '';
      const def = t.defensive_interpretations ? t.defensive_interpretations.join(' ') : '';
      const tele = t.telemetry_sources ? t.telemetry_sources.join(' ') : '';

      return `
        <div class="kb-card">
          <div style="display:flex; justify-content:space-between; align-items:center;">
            <span class="badge" style="background:rgba(56, 189, 248, 0.2); color:#38bdf8; font-weight:700;">CHỦ ĐỀ: ${escapeHtml(t.topic.toUpperCase())}</span>
          </div>
          <div style="font-size:0.88rem; color:#f1f5f9; line-height:1.45;">
            ${escapeHtml(desc)}
          </div>
          ${def ? `
            <div style="font-size:0.8rem; color:#cbd5e1; background:rgba(30, 41, 59, 0.6); padding:8px; border-radius:6px; border-left:3px solid #3b82f6;">
              🛡️ <strong>Nguyên tắc phòng thủ:</strong> ${escapeHtml(def)}
            </div>
          ` : ''}
          ${tele ? `
            <div style="font-size:0.78rem; color:#94a3b8;">
              📡 <strong>Telemetry:</strong> ${escapeHtml(tele)}
            </div>
          ` : ''}
        </div>
      `;
    }).join('');
  } catch (err) {
    console.error('Failed to load security knowledge:', err);
  }
}

async function openForensicModal() {
  const target = currentMachine || (document.getElementById('machineSelect') ? document.getElementById('machineSelect').value : '');
  if (!target) {
    alert('Vui lòng chọn một máy tính cụ thể ở dropdown góc trên để xuất báo cáo Forensic!');
    return;
  }

  const modal = document.getElementById('forensicModal');
  const header = document.getElementById('modalForensicHeader');
  const timelineEl = document.getElementById('modalForensicTimeline');
  const countEl = document.getElementById('modalForensicEventsCount');

  if (modal) modal.style.display = 'flex';
  if (header) header.innerText = `Đang trích xuất dữ liệu điều tra cho máy '${target}'...`;
  if (timelineEl) timelineEl.innerText = 'Đang đọc và tính toán mã băm SHA-256...';

  try {
    const res = await fetch(`/api/v1/machines/${encodeURIComponent(target)}/forensics`, { headers: getAuthHeaders() });
    if (!res.ok) {
      if (timelineEl) timelineEl.innerText = 'Lỗi trích xuất: ' + res.statusText;
      return;
    }
    const data = await res.json();
    currentForensicData = data;

    if (header) {
      header.innerHTML = `
        <div style="display:flex; justify-content:space-between; flex-wrap:wrap; gap:8px;">
          <div>
            <strong>💻 Máy điều tra:</strong> <span style="color:#60a5fa">${escapeHtml(data.client_id)}</span><br>
            <strong>🔒 Mã băm tính toàn vẹn (SHA-256):</strong> <code style="color:#34d399; font-size:0.8rem;">${escapeHtml(data.evidence_hash_sha256 || 'N/A')}</code>
          </div>
          <div>
            <strong>Dung lượng tệp:</strong> ${(data.evidence_file_size_bytes / 1024).toFixed(1)} KB<br>
            <strong>Thời điểm xuất:</strong> ${new Date(data.exported_at).toLocaleString()}
          </div>
        </div>
      `;
    }

    if (countEl) countEl.innerText = `${data.total_timeline_events || 0} sự kiện được xác thực`;

    if (timelineEl) {
      const lines = (data.timeline || []).map(ev => {
        const flag = ev.forensic_flag === 'SUSPICIOUS_IOA' ? '[⚠️ IOA_DETECTED]' : '[NORMAL]';
        return `[${ev.timestamp}] ${flag} [${ev.process_name}] (${ev.duration_seconds}s) "${ev.window_title}" | Cat: ${ev.category}`;
      });
      timelineEl.innerText = lines.length > 0 ? lines.join('\n') : 'Chưa có sự kiện nào trong timeline.';
    }
  } catch (err) {
    console.error('Failed to load forensic data:', err);
    if (timelineEl) timelineEl.innerText = 'Lỗi: ' + err.message;
  }
}

function downloadForensicJson() {
  if (!currentForensicData) {
    alert('Chưa có dữ liệu Forensic để tải xuống.');
    return;
  }
  const blob = new Blob([JSON.stringify(currentForensicData, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `forensic_report_${currentForensicData.client_id || 'machine'}_${Date.now()}.json`;
  a.click();
  URL.revokeObjectURL(url);
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
