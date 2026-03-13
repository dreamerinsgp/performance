const API_BASE = window.location.origin;

function $(id) {
  return document.getElementById(id);
}

// Tab switching
document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.tab-btn').forEach(b => {
      b.classList.remove('border-blue-500', 'text-blue-600');
      b.classList.add('text-gray-500');
    });
    btn.classList.add('border-b-2', 'border-blue-500', 'text-blue-600');
    btn.classList.remove('text-gray-500');

    document.querySelectorAll('.tab-panel').forEach(p => p.classList.add('hidden'));
    const panel = $('panel-' + btn.dataset.tab);
    if (panel) panel.classList.remove('hidden');

    if (btn.dataset.tab === 'monitor') {
      fetchMetrics();
      clearInterval(metricsRefreshInterval);
      metricsRefreshInterval = setInterval(fetchMetrics, METRICS_REFRESH_SEC * 1000);
    } else if (btn.dataset.tab === 'perftest') {
      loadPerftestConfig();
    } else {
      clearInterval(metricsRefreshInterval);
      metricsRefreshInterval = null;
    }
  });
});

// Load config on load
async function loadConfig() {
  const res = await fetch(API_BASE + '/api/config');
  const data = await res.json();
  if (data.exists && data.config) {
    const c = data.config;
    $('redis-host').value = c.redis?.host || '';
    $('redis-port').value = c.redis?.port || 6379;
    $('redis-password').value = c.redis?.password || '';
    $('mysql-host').value = c.mysql?.host || '';
    $('mysql-port').value = c.mysql?.port || 3306;
    $('mysql-user').value = c.mysql?.user || 'root';
    $('mysql-password').value = c.mysql?.password || '';
    $('mysql-database').value = c.mysql?.database || 'jmeter_test';
    $('mysql-init-sql').value = c.mysql_init_sql || '';
    $('kafka-brokers').value = Array.isArray(c.kafka?.brokers) ? c.kafka.brokers.join(', ') : (c.kafka?.brokers || '');
    $('github-repo').value = c.github?.repo_url || '';
    $('github-branch').value = c.github?.branch || 'main';
    $('github-subpath').value = c.github?.subpath || '';
    $('gateway-url').value = c.gateway_url || (c.app_server?.host ? 'http://' + c.app_server.host + ':8081' : '');
    if (c.app_server) {
      $('app-server-host').value = c.app_server.host || '';
      $('app-server-ssh-port').value = c.app_server.ssh_port || 22;
      $('app-server-ssh-user').value = c.app_server.ssh_user || 'root';
      $('app-server-deploy-path').value = c.app_server.deploy_path || '/opt/dex';
    }
  }
}
loadConfig();

// Save config
$('config-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const body = {
    redis: { host: $('redis-host').value || '127.0.0.1', port: parseInt($('redis-port').value) || 6379, password: $('redis-password').value },
    mysql: { host: $('mysql-host').value || '127.0.0.1', port: parseInt($('mysql-port').value) || 3306, user: $('mysql-user').value, password: $('mysql-password').value, database: $('mysql-database').value },
    mysql_init_sql: $('mysql-init-sql').value?.trim() || '',
    kafka: { brokers: $('kafka-brokers').value || '127.0.0.1:9092' },
    app_server: { host: $('app-server-host').value, ssh_port: parseInt($('app-server-ssh-port').value) || 22, ssh_user: $('app-server-ssh-user').value || 'root', deploy_path: $('app-server-deploy-path').value || '/opt/dex' },
    github: { repo_url: $('github-repo').value, branch: $('github-branch').value, subpath: $('github-subpath').value },
    gateway_url: $('gateway-url').value || 'http://127.0.0.1:8080',
  };
  const res = await fetch(API_BASE + '/api/config', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  if (res.ok) alert('Config saved.');
  else alert('Failed: ' + (await res.text()));
});

// Validate
$('btn-validate').addEventListener('click', async () => {
  const res = await fetch(API_BASE + '/api/config/validate', { method: 'POST' });
  const data = await res.json();
  const el = $('validate-result');
  el.classList.remove('hidden');
  el.innerHTML = Object.entries(data).map(([k, v]) => {
    const ok = v.ok === true ? '✓' : (v.ok === false ? '✗' : '-');
    const color = v.ok === true ? 'text-green-600' : (v.ok === false ? 'text-red-600' : 'text-gray-500');
    return `<div class="${color}">${k}: ${ok} ${v.message || ''}</div>`;
  }).join('');
});

// Deploy
$('btn-deploy').addEventListener('click', async () => {
  $('btn-deploy').disabled = true;
  $('deploy-output').classList.remove('hidden');
  $('deploy-output').textContent = 'Deploying...';
  try {
    const pw = $('deploy-ssh-password').value?.trim() || undefined;
    const res = await fetch(API_BASE + '/api/deploy', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(pw ? { ssh_password: pw } : {}),
    });
    const data = await res.json();
    $('deploy-output').textContent = (data.stdout || '') + (data.stderr ? '\n\nSTDERR:\n' + data.stderr : '');
    if (data.ok) $('deploy-output').classList.add('text-green-400');
    else $('deploy-output').classList.add('text-red-400');
  } catch (e) {
    $('deploy-output').textContent = 'Error: ' + e.message;
  }
  $('btn-deploy').disabled = false;
});

// Metrics - 防缓存，每次请求最新数据；Monitor 激活时每 15 秒自动刷新
$('btn-refresh-metrics')?.addEventListener('click', () => fetchMetrics());

let metricsRefreshInterval = null;
const METRICS_REFRESH_SEC = 15;

async function fetchMetrics() {
  const res = await fetch(API_BASE + '/api/metrics?t=' + Date.now(), { cache: 'no-store' });
  const data = await res.json();
  const el = $('metrics-list');
  const lastEl = $('metrics-last-refresh');
  if (lastEl) lastEl.textContent = '上次更新: ' + new Date().toLocaleTimeString();
  if (!data.machines || data.machines.length === 0) {
    el.innerHTML = '<p class="text-gray-500">No machines configured. Save infra config first.</p>';
    return;
  }
  el.innerHTML = data.machines.map(m => {
    const statusCls = m.project_status === 'up' ? 'text-green-600' : (m.project_status === 'down' ? 'text-red-600' : 'text-gray-500');
    const statusText = m.project_status === 'up' ? '✓ 运行中' : (m.project_status === 'down' ? '✗ 未响应' : '-');
    return `
    <div class="border rounded p-3 ${m.error ? 'border-red-300' : ''}">
      <span class="font-medium">${m.name}</span>
      <span class="text-gray-500 text-sm ml-2">${m.host}${m.port ? ':'+m.port : ''}</span>
      ${m.project_status ? `<span class="ml-2 text-sm font-medium ${statusCls}">${statusText}${m.project_latency_ms != null ? ' ('+m.project_latency_ms+'ms)' : ''}</span>` : ''}
      ${m.error ? `<p class="text-red-600 text-sm mt-1">${m.error}</p>` : ''}
      ${m.cpu != null ? `<p class="text-sm mt-1"><strong>CPU:</strong> ${m.cpu}%</p>` : ''}
      ${m.memory ? `<p class="text-sm"><strong>内存:</strong> ${m.memory}</p>` : ''}
      ${m.project_procs != null ? `<p class="text-sm"><strong>进程数:</strong> ${m.project_procs}</p>` : ''}
      ${m.ports_listen ? `<p class="text-sm"><strong>监听端口:</strong> ${m.ports_listen}</p>` : ''}
      ${m.project_message && m.project_status !== 'up' ? `<p class="text-gray-500 text-xs mt-1">${m.project_message}</p>` : ''}
      ${m.disk_read != null ? `<p class="text-sm"><strong>Disk R/W:</strong> ${m.disk_read} / ${m.disk_write}</p>` : ''}
      ${m.note ? `<p class="text-gray-500 text-xs mt-1">${m.note}</p>` : ''}
    </div>
  `}).join('');
}

// Perf test config
function parseEndpointsText(text) {
  return text.split('\n').map(line => {
    const t = line.trim();
    if (!t) return null;
    const parts = t.split(',').map(s => s.trim());
    if (parts.length === 1) return { path: parts[0], method: 'GET', weight: 1 };
    if (parts.length === 2) return { path: parts[0], method: parts[1] || 'GET', weight: 1 };
    return { path: parts[0], method: parts[1] || 'GET', weight: parseInt(parts[2]) || 1 };
  }).filter(Boolean);
}

function formatEndpointsForTextarea(endpoints) {
  return (endpoints || []).map(e => `${e.path},${e.method || 'GET'},${e.weight || 1}`).join('\n');
}

async function loadPerftestConfig() {
  const res = await fetch(API_BASE + '/api/perftest/config');
  const data = await res.json();
  const c = data.config || {};
  $('perftest-users').value = c.users ?? 50;
  $('perftest-rampup').value = c.ramp_up_seconds ?? 10;
  $('perftest-duration').value = c.duration_seconds ?? 30;
  $('perftest-endpoints').value = formatEndpointsForTextarea(c.endpoints) || '/api/health';
}

$('btn-save-perftest').addEventListener('click', async () => {
  const endpoints = parseEndpointsText($('perftest-endpoints').value);
  if (endpoints.length === 0) {
    alert('请至少添加一个接口');
    return;
  }
  const body = {
    endpoints,
    users: parseInt($('perftest-users').value) || 50,
    ramp_up_seconds: parseInt($('perftest-rampup').value) || 10,
    duration_seconds: parseInt($('perftest-duration').value) || 30,
  };
  const res = await fetch(API_BASE + '/api/perftest/config', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  if (res.ok) alert('压测配置已保存');
  else alert('保存失败: ' + (await res.text()));
});

// Perf test - 运行前自动保存当前表单配置
$('btn-run-perftest').addEventListener('click', async () => {
  const endpoints = parseEndpointsText($('perftest-endpoints').value);
  if (endpoints.length === 0) {
    alert('请至少添加一个接口');
    return;
  }
  // 先保存配置
  await fetch(API_BASE + '/api/perftest/config', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      endpoints,
      users: parseInt($('perftest-users').value) || 50,
      ramp_up_seconds: parseInt($('perftest-rampup').value) || 10,
      duration_seconds: parseInt($('perftest-duration').value) || 30,
    }),
  });

  $('btn-run-perftest').disabled = true;
  $('perftest-result').classList.remove('hidden');
  const duration = parseInt($('perftest-duration').value) || 30;
  $('perftest-result').innerHTML = `<p class="text-gray-500">Running... (约 ${duration} 秒)</p>`;
  try {
    const res = await fetch(API_BASE + '/api/perftest/run', { method: 'POST' });
    const data = await res.json();
    if (data.result) {
      const r = data.result;
      const stats = r.stats || [];
      const total = stats.find(s => (s.Name || s.name || '').toLowerCase() === 'total') || stats.find(s => (s.Name || s.name || '').toLowerCase().includes('aggregat')) || stats[0];
      const fmt = (v) => (v != null && typeof v === 'number' ? v.toFixed(1) : (v || 'N/A'));
      const rows = stats.filter(s => {
        const n = (s.Name || s.name || '').toLowerCase();
        return n && n !== 'total' && !n.includes('aggregat');
      });
      $('perftest-result').innerHTML = `
        <div class="border rounded p-4 bg-gray-50">
          <h3 class="font-semibold mb-2">Results</h3>
          <p><strong>RPS:</strong> ${fmt(total?.['Requests/s'] ?? total?.avg_rps)}</p>
          <p><strong>Avg latency (ms):</strong> ${fmt(total?.['Average response time'] ?? total?.avg_response_time)}</p>
          <p><strong>Failures:</strong> ${total?.['# failures'] ?? total?.num_failures ?? 0}</p>
          <table class="mt-2 text-sm w-full border-collapse">
            <tr class="border-b"><th class="text-left py-1">Name</th><th>RPS</th><th>Avg (ms)</th><th>Failures</th></tr>
            ${rows.map(s => `
              <tr class="border-b"><td class="py-1">${s.Name || s.name || '-'}</td><td>${fmt(s['Requests/s'] ?? s.avg_rps)}</td><td>${fmt(s['Average response time'] ?? s.avg_response_time)}</td><td>${s['# failures'] ?? s.num_failures ?? 0}</td></tr>
            `).join('') || '<tr><td colspan="4">No endpoint stats</td></tr>'}
          </table>
          ${data.html_report ? '<p class="mt-2 text-sm"><a href="' + data.html_report + '" target="_blank" class="text-blue-600">View HTML report</a></p>' : ''}
        </div>
      `;
    } else {
      $('perftest-result').innerHTML = '<p class="text-yellow-600">Test completed. Check console for details. Install locust: pip install locust</p>';
    }
  } catch (e) {
    $('perftest-result').innerHTML = '<p class="text-red-600">Error: ' + e.message + '</p>';
  }
  $('btn-run-perftest').disabled = false;
});
