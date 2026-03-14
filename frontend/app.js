const API_BASE = window.location.origin;

function $(id) {
  return document.getElementById(id);
}

// MySQL Ops 事件委托：容器内点击由父元素统一处理，支持静态 HTML 与动态渲染
document.addEventListener('click', (e) => {
  const cards = document.getElementById('mysql-ops-cards');
  if (!cards || !cards.contains(e.target)) return;
  if (e.target.closest('.mysql-ops-toggle')) {
    const btn = e.target.closest('.mysql-ops-toggle');
    const card = btn.closest('.border.rounded-lg');
    if (card) {
      const body = card.querySelector('.mysql-ops-body');
      const chevron = card.querySelector('.mysql-ops-chevron');
      if (body && chevron) {
        const isOpen = !body.classList.contains('hidden');
        body.classList.toggle('hidden', isOpen);
        chevron.style.transform = isOpen ? 'rotate(0deg)' : 'rotate(180deg)';
      }
    }
  } else if (e.target.closest('.mysql-ops-run-btn')) {
    const btn = e.target.closest('.mysql-ops-run-btn');
    e.preventDefault();
    e.stopPropagation();
    if (typeof runMysqlOps === 'function') runMysqlOps(btn.dataset.problem, btn.dataset.action, btn);
  } else if (e.target.closest('.mysql-case-link')) {
    e.preventDefault();
    e.stopPropagation();
    const link = e.target.closest('.mysql-case-link');
    if (typeof openMysqlCaseModal === 'function') openMysqlCaseModal(link.dataset.problem);
  } else if (e.target.closest('.mysql-code-link')) {
    e.preventDefault();
    e.stopPropagation();
    const link = e.target.closest('.mysql-code-link');
    if (typeof openMysqlCodeModal === 'function') openMysqlCodeModal(link.dataset.problem);
  }
});

// Redis Ops 事件委托
document.addEventListener('click', (e) => {
  const cards = document.getElementById('redis-ops-cards');
  if (!cards || !cards.contains(e.target)) return;
  if (e.target.closest('.redis-ops-toggle')) {
    const btn = e.target.closest('.redis-ops-toggle');
    const card = btn.closest('.border.rounded-lg');
    if (card) {
      const body = card.querySelector('.redis-ops-body');
      const chevron = card.querySelector('.redis-ops-chevron');
      if (body && chevron) {
        const isOpen = !body.classList.contains('hidden');
        body.classList.toggle('hidden', isOpen);
        chevron.style.transform = isOpen ? 'rotate(0deg)' : 'rotate(180deg)';
      }
    }
  } else if (e.target.closest('.redis-ops-run-btn')) {
    const btn = e.target.closest('.redis-ops-run-btn');
    e.preventDefault();
    e.stopPropagation();
    if (typeof runRedisOps === 'function') runRedisOps(btn.dataset.problem, btn.dataset.action, btn);
  } else if (e.target.closest('.redis-case-link')) {
    e.preventDefault();
    e.stopPropagation();
    const link = e.target.closest('.redis-case-link');
    if (typeof openRedisCaseModal === 'function') openRedisCaseModal(link.dataset.problem);
  } else if (e.target.closest('.redis-code-link')) {
    e.preventDefault();
    e.stopPropagation();
    const link = e.target.closest('.redis-code-link');
    if (typeof openRedisCodeModal === 'function') openRedisCodeModal(link.dataset.problem);
  }
});

// Kafka Ops 事件委托
document.addEventListener('click', (e) => {
  const cards = document.getElementById('kafka-ops-cards');
  if (!cards || !cards.contains(e.target)) return;
  if (e.target.closest('.kafka-ops-toggle')) {
    const btn = e.target.closest('.kafka-ops-toggle');
    const card = btn.closest('.border.rounded-lg');
    if (card) {
      const body = card.querySelector('.kafka-ops-body');
      const chevron = card.querySelector('.kafka-ops-chevron');
      if (body && chevron) {
        const isOpen = !body.classList.contains('hidden');
        body.classList.toggle('hidden', isOpen);
        chevron.style.transform = isOpen ? 'rotate(0deg)' : 'rotate(180deg)';
      }
    }
  } else if (e.target.closest('.kafka-case-link')) {
    e.preventDefault();
    e.stopPropagation();
    const link = e.target.closest('.kafka-case-link');
    if (typeof openKafkaCaseModal === 'function') openKafkaCaseModal(link.dataset.problem);
  } else if (e.target.closest('.kafka-ops-run-btn')) {
    const btn = e.target.closest('.kafka-ops-run-btn');
    e.preventDefault();
    e.stopPropagation();
    if (typeof runKafkaOps === 'function') runKafkaOps(btn.dataset.problem, btn.dataset.action, btn);
  } else if (e.target.closest('.kafka-code-link')) {
    e.preventDefault();
    e.stopPropagation();
    const link = e.target.closest('.kafka-code-link');
    if (typeof openKafkaCodeModal === 'function') openKafkaCodeModal(link.dataset.problem);
  }
});

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
    } else if (btn.dataset.tab === 'mysqlops') {
      loadMysqlOpsStatus();
      updateMysqlOpsActions();
    } else if (btn.dataset.tab === 'redisops') {
      loadRedisOpsStatus();
    } else if (btn.dataset.tab === 'kafkaops') {
      loadKafkaOpsStatus();
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
    $('redis-username').value = c.redis?.username || '';
    $('redis-password').value = c.redis?.password || '';
    $('mysql-host').value = c.mysql?.host || '';
    $('mysql-port').value = c.mysql?.port || 3306;
    $('mysql-user').value = c.mysql?.user || 'root';
    $('mysql-password').value = c.mysql?.password || '';
    $('mysql-database').value = c.mysql?.database || 'jmeter_test';
    $('mysql-init-sql').value = c.mysql_init_sql || '';
    $('kafka-brokers').value = Array.isArray(c.kafka?.brokers) ? c.kafka.brokers.join(', ') : (c.kafka?.brokers || '');
    $('kafka-username').value = c.kafka?.username || '';
    $('kafka-password').value = c.kafka?.password || '';
    $('github-repo').value = c.github?.repo_url || '';
    $('github-branch').value = c.github?.branch || 'main';
    $('github-subpath').value = c.github?.subpath || '';
    $('gateway-url').value = c.gateway_url || (c.app_server?.host ? 'http://' + c.app_server.host + ':8081' : '');
    const ocUrl = $('openclaw-gateway-url');
    const ocToken = $('openclaw-hooks-token');
    if (ocUrl && ocToken) {
      if (c.openclaw) {
        ocUrl.value = c.openclaw.gateway_url || 'http://127.0.0.1:18789';
        ocToken.value = c.openclaw.hooks_token || '';
      } else {
        ocUrl.value = 'http://127.0.0.1:18789';
        ocToken.value = '';
      }
    }
    if (c.app_server) {
      $('app-server-host').value = c.app_server.host || '';
      $('app-server-ssh-port').value = c.app_server.ssh_port || 22;
      $('app-server-ssh-user').value = c.app_server.ssh_user || 'root';
      $('app-server-deploy-path').value = c.app_server.deploy_path || '/opt/dex';
      $('app-server-mysql-ops-path').value = c.app_server.mysql_ops_path || '/opt/dex/mysql-ops-learning';
    }
  }
}
loadConfig();

// Save config
$('config-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const body = {
    redis: { host: $('redis-host').value || '127.0.0.1', port: parseInt($('redis-port').value) || 6379, username: ($('redis-username').value || '').trim(), password: $('redis-password').value },
    mysql: { host: $('mysql-host').value || '127.0.0.1', port: parseInt($('mysql-port').value) || 3306, user: $('mysql-user').value, password: $('mysql-password').value, database: $('mysql-database').value },
    mysql_init_sql: $('mysql-init-sql').value?.trim() || '',
    kafka: {
      brokers: $('kafka-brokers').value || '127.0.0.1:9092',
      username: ($('kafka-username').value || '').trim(),
      password: $('kafka-password').value || '',
    },
    app_server: {
      host: $('app-server-host').value,
      ssh_port: parseInt($('app-server-ssh-port').value) || 22,
      ssh_user: $('app-server-ssh-user').value || 'root',
      deploy_path: $('app-server-deploy-path').value || '/opt/dex',
      mysql_ops_path: $('app-server-mysql-ops-path').value || '/opt/dex/mysql-ops-learning',
    },
    github: { repo_url: $('github-repo').value, branch: $('github-branch').value, subpath: $('github-subpath').value },
    gateway_url: $('gateway-url').value || 'http://127.0.0.1:8080',
    openclaw: {
      gateway_url: ($('openclaw-gateway-url')?.value || 'http://127.0.0.1:18789').trim(),
      hooks_token: ($('openclaw-hooks-token')?.value || '').trim(),
    },
  };
  const res = await fetch(API_BASE + '/api/config', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  if (res.ok) alert('Config saved.');
  else alert('Failed: ' + (await res.text()));
});

// Validate Kafka (quick test without saving)
$('btn-validate-kafka')?.addEventListener('click', async () => {
  const el = $('kafka-test-result');
  if (!el) return;
  const brokers = ($('kafka-brokers').value || '').trim();
  if (!brokers) {
    el.textContent = '请先填写 Brokers';
    el.className = 'ml-2 text-sm text-amber-600';
    return;
  }
  el.textContent = '测试中...';
  el.className = 'ml-2 text-sm text-gray-500';
  try {
    const res = await fetch(API_BASE + '/api/config/validate/kafka', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ brokers }),
    });
    let data;
    try {
      data = await res.json();
    } catch (_) {
      data = { ok: false, message: (await res.text()) || 'Server error' };
    }
    el.textContent = data.ok ? '✓ ' + data.message : '✗ ' + data.message;
    el.className = 'ml-2 text-sm ' + (data.ok ? 'text-green-600' : 'text-red-600');
  } catch (e) {
    el.textContent = 'Error: ' + e.message;
    el.className = 'ml-2 text-sm text-red-600';
  }
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

// MySQL Ops - 业务场景 / 现象 / 问题 / 解决方案（前端静态数据作为回退，确保 Run 按钮始终可见）
const MYSQL_OPS_PROBLEMS_FALLBACK = [
  { id: "01-max-connections", name: "最大连接数耗尽", business_scenario: "电商平台大促秒杀：双11 活动开始瞬间每秒 5000+ 请求，应用每次新建 MySQL 连接且未归还，max_connections=500 约 10 秒后新请求全部报 Too many connections，用户界面显示「系统繁忙，请稍后再试」，活动被迫暂停。", scenario: "应用未正确复用连接，不断创建新连接而不释放。", phenomenon: "新连接报错 Too many connections；Threads_connected 接近 max_connections。", problem: "MySQL 连接数达到上限。", solution: "调整 max_connections；使用连接池；修复连接泄漏。", actions: [{ id: "reproduce", name: "模拟耗尽" }, { id: "monitor", name: "查看状态" }] },
  { id: "02-slow-log", name: "慢查询监控", business_scenario: "O2O 平台用户搜索订单：输入订单号或手机号查询，要等十几秒才能出结果，有时直接超时。DBA 发现数据库 CPU 偶发飙高，但未开慢查询日志，无法定位是哪条 SQL 导致。", scenario: "线上偶发接口变慢，需定位慢 SQL。", phenomenon: "接口响应时间不稳定；数据库负载波动。", problem: "部分 SQL 执行时间过长，未开启慢日志无法定位。", solution: "开启 slow_query_log；设置 long_query_time；用 pt-query-digest 分析。", actions: [{ id: "reproduce", name: "模拟慢查询" }, { id: "enable", name: "开启慢日志" }, { id: "view", name: "查看慢日志" }] },
  { id: "03-large-transaction", name: "大事务", business_scenario: "积分商城周年庆：运营给 10 万用户每人加 100 积分，单事务内 UPDATE 10 万行，执行约 5 分钟才提交。这 5 分钟内所有涉及 user_points 的操作（登录校验、下单扣积分、查询余额）全被阻塞，前台业务几乎停滞。", scenario: "批量更新在单事务内执行过多行。", phenomenon: "其他会话长时间等待；复制延迟；锁等待超时。", problem: "单事务修改大量行，长时间持锁阻塞其他事务。", solution: "拆分为小批次；缩短事务；通过 INNODB_TRX 监控。", actions: [{ id: "reproduce", name: "模拟大事务" }, { id: "detect", name: "检测长事务" }] },
  { id: "04-large-table", name: "大表问题", business_scenario: "订单表 5000 万行需新增 coupon_id 字段。DBA 执行 ALTER TABLE 使用默认 COPY 算法，重建整表约 2 小时，期间表被锁定，用户无法下单、无法查订单，大促前夜执行导致活动推迟。", scenario: "单表数据量持续增长，DDL 耗时过长。", phenomenon: "查询变慢；ALTER TABLE 执行数小时；锁表。", problem: "表过大导致全表扫描、DDL 锁表时间长。", solution: "分区；在线 DDL（pt-osc、gh-ost）；数据归档；合理建索引。", actions: [{ id: "reproduce", name: "模拟大表" }, { id: "analyze", name: "分析表大小" }] },
  { id: "05-deadlock", name: "死锁", business_scenario: "用户 A 给 B 转 100 元、B 同时给 A 转 50 元。两事务均为先锁转出方再锁转入方，形成 A 等 B、B 等 A 的环路，MySQL 检测到死锁回滚其一，用户看到「交易失败，请重试」。", scenario: "多事务并发更新，加锁顺序不一致。", phenomenon: "事务报错 Deadlock found；部分事务被自动回滚。", problem: "事务互相等待对方持有的锁，形成环路。", solution: "统一加锁顺序；死锁后自动重试；缩短事务。", actions: [{ id: "reproduce", name: "模拟死锁" }, { id: "analyze", name: "查看死锁信息" }] },
  { id: "06-lock-wait-timeout", name: "锁等待超时", business_scenario: "SaaS 平台运营导出全部用户报表：事务内 SELECT * FROM users 全表扫描且长时间不提交。前台用户尝试更新头像、昵称需要排他锁，等待超过 50 秒后返回 Lock wait timeout exceeded，用户看到「修改失败，请重试」。", scenario: "事务 A 持锁未提交，事务 B 等待同一行锁。", phenomenon: "报错 Lock wait timeout exceeded；更新/删除失败。", problem: "持锁事务长时间不提交，阻塞其他事务。", solution: "缩短持锁时间；调整 innodb_lock_wait_timeout；定位并 KILL 阻塞会话。", actions: [{ id: "reproduce", name: "模拟等待" }] },
  { id: "07-index-misuse", name: "索引使用不当", business_scenario: "外卖订单表 1000 万行，用户按手机号查订单。WHERE phone=? 无索引，MySQL 全表扫描，单次查询 20~30 秒，接口超时，用户看到「加载失败」，数据库 CPU 长期偏高。", scenario: "查询条件列无索引或索引未被使用。", phenomenon: "单条 SQL 执行很慢；EXPLAIN 显示 type=ALL。", problem: "未建索引或索引不符合查询，导致全表扫描。", solution: "对 WHERE/ORDER BY 列建索引；避免 SELECT *；通过 EXPLAIN 检查。", actions: [{ id: "reproduce", name: "模拟全表扫描" }, { id: "explain", name: "查看执行计划" }] },
  { id: "08-replication-lag", name: "主从复制延迟", business_scenario: "订单系统主从架构，主库写、从库读报表。大促时从库 Seconds_Behind_Master 持续 30 分钟以上，报表数据严重滞后。", scenario: "主库写入激增，从库单线程 apply binlog 缓慢。", phenomenon: "从库延迟 30+ 分钟；relay log 堆积。", problem: "从库默认单线程复制，大事务导致 binlog 应用跟不上。", solution: "开启 slave_parallel_workers；slave_parallel_type=LOGICAL_CLOCK；拆分大事务。", actions: [{ id: "reproduce", name: "模拟大事务" }, { id: "monitor", name: "监控延迟" }, { id: "detect", name: "检测配置" }] },
];
let MYSQL_OPS_LAST_PROBLEMS = MYSQL_OPS_PROBLEMS_FALLBACK;
const MYSQL_CODE_MODAL_STATE = { problemId: '', filePath: '' };
const MYSQL_CODE_HIGHLIGHT_STATE = { lines: [] };

function escapeHtml(str) {
  return (str || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

function getProblemHighlightRules(problemId) {
  const rules = {
    '01-max-connections': [
      { keyword: /Opening connections until limit|connections open|Ping failed/i, reason: '连接耗尽压测/报错日志' },
      { keyword: /sql\.Open\(|db\.Ping\(/, reason: '频繁建连/探活调用' },
      { keyword: /append\(|holders|conns|for\s*\{/, reason: '连接持续累积循环' },
    ],
    '02-slow-log': [
      { keyword: /slow_query_log|long_query_time|SLEEP\(/i, reason: '慢查询配置或模拟语句' },
      { keyword: /SELECT .*FROM|ORDER BY|LIKE/i, reason: '潜在慢 SQL' },
    ],
    '03-large-transaction': [
      { keyword: /BEGIN|START TRANSACTION|COMMIT|ROLLBACK/i, reason: '事务边界' },
      { keyword: /UPDATE|INSERT|DELETE/i, reason: '大批量 DML 语句' },
    ],
    '04-large-table': [
      { keyword: /ALTER TABLE|CREATE TABLE/i, reason: '大表 DDL 语句' },
      { keyword: /COUNT\(\*\)|ANALYZE|INFORMATION_SCHEMA/i, reason: '大表分析语句' },
    ],
    '05-deadlock': [
      { keyword: /FOR UPDATE|BEGIN|COMMIT/i, reason: '加锁事务逻辑' },
      { keyword: /Deadlock|1213/i, reason: '死锁报错或检测' },
    ],
    '06-lock-wait-timeout': [
      { keyword: /FOR UPDATE|UPDATE|LOCK|innodb_lock_wait_timeout/i, reason: '锁等待超时相关语句' },
      { keyword: /Lock wait timeout|1205/i, reason: '超时报错处理' },
    ],
    '07-index-misuse': [
      { keyword: /EXPLAIN|WHERE|ORDER BY|LIKE/i, reason: '索引使用关键 SQL' },
      { keyword: /type=ALL|full scan|全表扫描/i, reason: '全表扫描风险点' },
    ],
    '08-replication-lag': [
      { keyword: /SHOW SLAVE STATUS|Seconds_Behind_Master/i, reason: '从库复制状态' },
      { keyword: /slave_parallel|binlog|relay/i, reason: '复制相关配置' },
    ],
  };
  return rules[problemId] || [];
}

function computeHighlightLines(problemId, content) {
  const lines = (content || '').split('\n');
  const rules = getProblemHighlightRules(problemId);
  const hits = [];
  rules.forEach((r) => {
    lines.forEach((line, idx) => {
      if (r.keyword.test(line)) {
        hits.push({ line: idx + 1, reason: r.reason, text: line });
      }
    });
  });
  const dedup = [];
  const seen = new Set();
  hits.forEach((h) => {
    if (!seen.has(h.line)) {
      seen.add(h.line);
      dedup.push(h);
    }
  });
  return dedup.slice(0, 16);
}

function renderHighlightPreview(problemId, content) {
  const preview = $('mysql-code-highlight-preview');
  if (!preview) return;
  const lines = (content || '').split('\n');
  const hits = computeHighlightLines(problemId, content);
  MYSQL_CODE_HIGHLIGHT_STATE.lines = hits.map(h => h.line);
  if (!hits.length) {
    preview.innerHTML = '<span class="text-gray-500">未自动识别到明显问题行，可手动查看关键 SQL/事务/连接处理代码。</span>';
    return;
  }
  const body = hits.map((h) => {
    const raw = lines[h.line - 1] || '';
    const text = escapeHtml(raw);
    return `<div><span class="text-amber-700 font-medium">L${h.line}</span> <mark class="bg-yellow-200 px-1 rounded">${text || '&nbsp;'}</mark> <span class="text-gray-500">(${escapeHtml(h.reason)})</span></div>`;
  }).join('');
  preview.innerHTML = body;
}

function renderMysqlOpsCards(problems) {
  const cardsEl = $('mysql-ops-cards');
  if (!cardsEl) return;
  const list = (problems && problems.length) ? problems : MYSQL_OPS_PROBLEMS_FALLBACK;
  const esc = (s) => (s || '').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  cardsEl.innerHTML = list.map((p, i) => {
    const biz = p.business_scenario || p.businessScenario;
    const expanded = i === 0; // 默认展开第一项
    return `
      <div class="border rounded-lg bg-white border-l-4 border-indigo-500 shadow-sm overflow-hidden">
        <button type="button" class="mysql-ops-toggle w-full text-left px-4 py-3 flex items-center justify-between hover:bg-indigo-50 transition-colors" data-idx="${i}">
          <span class="font-semibold text-indigo-700">${String(i + 1).padStart(2, '0')} ${p.name}</span>
          <span class="mysql-ops-chevron text-gray-400 text-sm transform transition-transform" style="transform: rotate(${expanded ? 180 : 0}deg)">▼</span>
        </button>
        <div class="mysql-ops-body border-t border-gray-100 ${expanded ? '' : 'hidden'}">
          <div class="p-4 space-y-4">
            ${biz ? `
            <div class="p-3 bg-sky-50 border-l-4 border-sky-400 rounded text-sm text-gray-700">
              <span class="font-medium text-sky-800 block mb-1">真实业务场景</span>
              <p>${esc(biz)}</p>
            </div>
            ` : ''}
            <div class="space-y-3 text-sm">
              <div class="flex gap-2">
                <span class="shrink-0 inline-block px-2 py-0.5 rounded bg-blue-100 text-blue-800 text-xs font-medium">1</span>
                <div><span class="font-medium text-gray-700">业务场景：</span><span class="text-gray-600">${esc(p.scenario)}</span></div>
              </div>
              <div class="flex gap-2">
                <span class="shrink-0 inline-block px-2 py-0.5 rounded bg-amber-100 text-amber-800 text-xs font-medium">2</span>
                <div><span class="font-medium text-gray-700">现象：</span><span class="text-gray-600">${esc(p.phenomenon)}</span></div>
              </div>
              <div class="flex gap-2">
                <span class="shrink-0 inline-block px-2 py-0.5 rounded bg-red-100 text-red-800 text-xs font-medium">3</span>
                <div><span class="font-medium text-gray-700">问题：</span><span class="text-gray-600">${esc(p.problem)}</span></div>
              </div>
              <div class="flex gap-2">
                <span class="shrink-0 inline-block px-2 py-0.5 rounded bg-green-100 text-green-800 text-xs font-medium">4</span>
                <div><span class="font-medium text-gray-700">解决方案建议：</span><span class="text-gray-600">${esc(p.solution)}</span></div>
              </div>
            </div>
            <div class="flex flex-wrap gap-2 pt-2 border-t items-center">
              ${(p.actions || []).map(a => `
                <button class="mysql-ops-run-btn px-3 py-1.5 bg-indigo-600 text-white rounded text-sm hover:bg-indigo-700 disabled:opacity-50" data-problem="${p.id}" data-action="${a.id}">Run: ${a.name}</button>
              `).join('')}
              <a href="#" class="mysql-case-link text-sky-600 hover:text-sky-800 text-sm ml-2" data-problem="${p.id}">查看完整案例</a>
              <button class="mysql-code-link px-3 py-1.5 bg-gray-100 text-gray-700 rounded text-sm hover:bg-gray-200" data-problem="${p.id}">查看/修改代码</button>
            </div>
          </div>
        </div>
      </div>
    `;
  }).join('');
  // 点击由 document 事件委托统一处理，此处无需再绑定
}

// 将 Markdown 转为 HTML：mermaid 块单独提取，避免 marked 转义；其余用 marked 解析
function renderMysqlCaseContent(md) {
  if (!md) return '';
  const parts = [];
  let rest = md;
  const re = /```mermaid\r?\n([\s\S]*?)\r?\n```/gi;
  let lastIdx = 0;
  let m;
  while ((m = re.exec(md)) !== null) {
    parts.push({ type: 'md', text: md.slice(lastIdx, m.index) });
    parts.push({ type: 'mermaid', code: m[1].trim() });
    lastIdx = re.lastIndex;
  }
  parts.push({ type: 'md', text: md.slice(lastIdx) });
  let out = '';
  for (const p of parts) {
    if (p.type === 'mermaid') {
      out += '<div class="mermaid my-4">' + p.code + '</div>';
    } else if (p.type === 'md' && p.text) {
      out += typeof marked !== 'undefined' ? marked.parse(p.text) : p.text.replace(/</g, '&lt;');
    }
  }
  return out;
}

async function openMysqlCaseModal(problemId) {
  const modal = document.getElementById('mysql-case-modal');
  const titleEl = document.getElementById('mysql-case-modal-title');
  const bodyEl = document.getElementById('mysql-case-modal-body');
  const closeBtn = document.getElementById('mysql-case-modal-close');
  const backdrop = document.getElementById('mysql-case-modal-backdrop');
  if (!modal || !titleEl || !bodyEl) return;
  titleEl.textContent = '加载中...';
  bodyEl.innerHTML = '';
  modal.classList.remove('hidden');
  try {
    const res = await fetch(API_BASE + '/api/mysql-ops/case/' + encodeURIComponent(problemId));
    const data = await res.json();
    titleEl.textContent = '完整业务案例 - ' + problemId;
    const html = renderMysqlCaseContent(data.content || '无内容');
    bodyEl.innerHTML = html;
    if (typeof mermaid !== 'undefined') {
      const mermaidNodes = bodyEl.querySelectorAll('.mermaid');
      if (mermaidNodes.length) {
        try {
          mermaid.initialize({ startOnLoad: false, theme: 'neutral' });
          await new Promise(r => requestAnimationFrame(r)); // 等待 DOM 绘制
          await mermaid.run({ nodes: mermaidNodes, suppressErrors: true });
        } catch (err) {
          console.warn('Mermaid render:', err);
          mermaidNodes.forEach(n => { n.innerHTML = '<pre class="text-xs text-amber-600">' + n.textContent + '</pre>'; });
        }
      }
    }
  } catch (e) {
    titleEl.textContent = '加载失败';
    bodyEl.innerHTML = '<p class="text-red-600">Error: ' + (e.message || e) + '</p>';
  }
  function closeModal() {
    modal.classList.add('hidden');
    document.removeEventListener('keydown', onEsc);
  }
  function onEsc(e) {
    if (e.key === 'Escape') closeModal();
  }
  closeBtn.onclick = closeModal;
  backdrop.onclick = (e) => { if (e.target === backdrop) closeModal(); };
  document.addEventListener('keydown', onEsc);
}

function getMysqlProblemById(problemId) {
  return (MYSQL_OPS_LAST_PROBLEMS || []).find(p => p.id === problemId)
    || MYSQL_OPS_PROBLEMS_FALLBACK.find(p => p.id === problemId);
}

async function loadMysqlCodeFile(problemId, filePath) {
  const editor = $('mysql-code-editor');
  const status = $('mysql-code-status');
  if (!editor || !status) return;
  status.textContent = '加载文件中...';
  const res = await fetch(API_BASE + '/api/mysql-ops/code/' + encodeURIComponent(problemId) + '?path=' + encodeURIComponent(filePath));
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || '加载失败');
  editor.value = data.content || '';
  MYSQL_CODE_MODAL_STATE.filePath = data.path || filePath;
  renderHighlightPreview(problemId, editor.value);
  status.textContent = '已加载：' + MYSQL_CODE_MODAL_STATE.filePath;
}

async function openMysqlCodeModal(problemId) {
  const modal = $('mysql-code-modal');
  const title = $('mysql-code-modal-title');
  const fileSel = $('mysql-code-file-select');
  const runSel = $('mysql-code-run-action');
  const status = $('mysql-code-status');
  const editor = $('mysql-code-editor');
  if (!modal || !title || !fileSel || !runSel || !status || !editor) return;

  MYSQL_CODE_MODAL_STATE.problemId = problemId;
  MYSQL_CODE_MODAL_STATE.filePath = '';
  const p = getMysqlProblemById(problemId);
  title.textContent = `问题代码 - ${p ? p.name : problemId}`;
  editor.value = '';
  fileSel.innerHTML = '';
  runSel.innerHTML = ((p && p.actions) || []).map(a => `<option value="${a.id}">${a.name}</option>`).join('');

  modal.classList.remove('hidden');
  status.textContent = '正在获取文件列表...';
  const res = await fetch(API_BASE + '/api/mysql-ops/code/' + encodeURIComponent(problemId) + '/files');
  const data = await res.json();
  if (!res.ok) {
    status.textContent = '获取文件失败：' + (data.detail || 'unknown');
    return;
  }
  const files = data.files || [];
  if (!files.length) {
    status.textContent = '当前问题目录下没有可编辑文件。';
    return;
  }
  fileSel.innerHTML = files.map(f => `<option value="${f}">${f}</option>`).join('');
  await loadMysqlCodeFile(problemId, files[0]);
}

async function saveMysqlCodeModal() {
  const problemId = MYSQL_CODE_MODAL_STATE.problemId;
  const fileSel = $('mysql-code-file-select');
  const editor = $('mysql-code-editor');
  const status = $('mysql-code-status');
  if (!problemId || !fileSel || !editor || !status) return;
  const path = fileSel.value;
  status.textContent = '保存中...';
  const res = await fetch(API_BASE + '/api/mysql-ops/code/' + encodeURIComponent(problemId), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ path, content: editor.value }),
  });
  const data = await res.json();
  if (!res.ok) {
    status.textContent = '保存失败：' + (data.detail || 'unknown');
    return;
  }
  renderHighlightPreview(problemId, editor.value);
  status.textContent = '保存成功：' + (data.path || path);
}

function initMysqlCodeModal() {
  const modal = $('mysql-code-modal');
  const backdrop = $('mysql-code-modal-backdrop');
  const closeBtn = $('mysql-code-close');
  const fileSel = $('mysql-code-file-select');
  const saveBtn = $('mysql-code-save-btn');
  const runBtn = $('mysql-code-run-btn');
  const runSel = $('mysql-code-run-action');
  const focusBtn = $('mysql-code-focus-first');
  const editor = $('mysql-code-editor');
  if (!modal || !backdrop || !closeBtn || !fileSel || !saveBtn || !runBtn || !runSel || !focusBtn || !editor) return;
  if (modal.dataset.bound === '1') return;
  modal.dataset.bound = '1';

  const closeModal = () => modal.classList.add('hidden');
  closeBtn.addEventListener('click', closeModal);
  backdrop.addEventListener('click', (e) => { if (e.target === backdrop) closeModal(); });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && !modal.classList.contains('hidden')) closeModal();
  });
  fileSel.addEventListener('change', async () => {
    if (!MYSQL_CODE_MODAL_STATE.problemId || !fileSel.value) return;
    try {
      await loadMysqlCodeFile(MYSQL_CODE_MODAL_STATE.problemId, fileSel.value);
    } catch (e) {
      const status = $('mysql-code-status');
      if (status) status.textContent = '加载失败：' + e.message;
    }
  });
  editor.addEventListener('input', () => {
    renderHighlightPreview(MYSQL_CODE_MODAL_STATE.problemId, editor.value);
  });
  focusBtn.addEventListener('click', () => {
    const first = MYSQL_CODE_HIGHLIGHT_STATE.lines[0];
    if (!first) return;
    const all = editor.value || '';
    const arr = all.split('\n');
    let start = 0;
    for (let i = 0; i < Math.max(0, first - 1); i += 1) start += arr[i].length + 1;
    const end = start + (arr[first - 1] || '').length;
    editor.focus();
    editor.setSelectionRange(start, end);
    const approxLineHeight = 24;
    editor.scrollTop = Math.max(0, (first - 3) * approxLineHeight);
  });
  saveBtn.addEventListener('click', saveMysqlCodeModal);
  runBtn.addEventListener('click', async () => {
    await saveMysqlCodeModal();
    const action = runSel.value;
    if (!MYSQL_CODE_MODAL_STATE.problemId || !action) return;
    await runMysqlOps(MYSQL_CODE_MODAL_STATE.problemId, action, runBtn);
  });
}

async function loadMysqlOpsStatus() {
  const statusEl = $('mysql-ops-status');
  const cardsEl = $('mysql-ops-cards');
  if (!statusEl || !cardsEl) return;
  let problems = MYSQL_OPS_PROBLEMS_FALLBACK;
  try {
    const res = await fetch(API_BASE + '/api/mysql-ops/problems');
    const data = await res.json();
    if (data.problems && data.problems.length) problems = data.problems;
    if (data.mysql_ops_available) {
      statusEl.innerHTML = '<span class="text-green-700">✓ mysql-ops-learning 已就绪。使用 Infra 配置的 MySQL 运行。请先保存 Infra 中的 MySQL 配置。</span>';
    } else {
      statusEl.innerHTML = '<span class="text-amber-700">⚠ mysql-ops-learning 未找到。请确保项目位于 performance 同级目录。下方 Run 按钮仍可点击尝试。</span>';
    }
  } catch (e) {
    statusEl.innerHTML = '<span class="text-amber-700">API 加载失败，使用本地数据。' + e.message + '</span>';
  }
  MYSQL_OPS_LAST_PROBLEMS = problems;
  renderMysqlOpsCards(problems);
  loadMysqlConnectionLimits();
}

function updateMysqlOpsActions() {
  loadMysqlOpsStatus();
}

async function runMysqlOps(problem, action, btn) {
  const out = $('mysql-ops-output');
  if (!out) return;
  if (btn) btn.disabled = true;
  out.classList.remove('hidden');
  out.textContent = 'Running...';
  try {
    const res = await fetch(API_BASE + '/api/mysql-ops/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ problem, action }),
    });
    const data = await res.json();
    let text = data.stdout || '';
    if (data.stderr) text += (text ? '\n\n' : '') + 'STDERR:\n' + data.stderr;
    if (!text && data.detail) text = 'ERROR:\n' + data.detail;
    out.textContent = text || '(no output)';
    out.classList.remove('text-red-400');
    if (!data.ok) out.classList.add('text-red-400');
    out.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  } catch (e) {
    out.textContent = 'Error: ' + e.message;
    out.classList.add('text-red-400');
  }
  if (btn) btn.disabled = false;
}

async function copyMysqlOpsOutput() {
  const out = $('mysql-ops-output');
  const btn = $('btn-mysql-ops-copy');
  if (!out || !btn) return;
  const text = out.textContent || '';
  if (!text.trim()) {
    btn.textContent = '无可复制内容';
    setTimeout(() => { btn.textContent = '复制输出'; }, 1200);
    return;
  }
  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text);
    } else {
      const ta = document.createElement('textarea');
      ta.value = text;
      ta.style.position = 'fixed';
      ta.style.left = '-9999px';
      document.body.appendChild(ta);
      ta.focus();
      ta.select();
      document.execCommand('copy');
      document.body.removeChild(ta);
    }
    btn.textContent = '已复制';
    setTimeout(() => { btn.textContent = '复制输出'; }, 1200);
  } catch (e) {
    btn.textContent = '复制失败';
    setTimeout(() => { btn.textContent = '复制输出'; }, 1200);
  }
}

async function loadMysqlConnectionLimits() {
  const status = $('mysql-conn-limit-status');
  const maxConnInput = $('mysql-max-connections-input');
  const maxUserConnInput = $('mysql-max-user-connections-input');
  const maxConnValue = $('mysql-max-connections-value');
  const maxUserConnValue = $('mysql-max-user-connections-value');
  const threadsConnectedValue = $('mysql-threads-connected-value');
  const threadsRunningValue = $('mysql-threads-running-value');
  if (!status) return;
  status.textContent = '读取中...';
  try {
    const res = await fetch(API_BASE + '/api/mysql-ops/connection-limits');
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || '读取失败');
    const mc = data.max_connections ?? '-';
    const muc = data.max_user_connections ?? '-';
    const tc = data.threads_connected ?? '-';
    const tr = data.threads_running ?? '-';
    if (maxConnValue) maxConnValue.textContent = mc;
    if (maxUserConnValue) maxUserConnValue.textContent = muc;
    if (threadsConnectedValue) threadsConnectedValue.textContent = tc;
    if (threadsRunningValue) threadsRunningValue.textContent = tr;
    if (maxConnInput) maxConnInput.value = data.max_connections ?? '';
    if (maxUserConnInput) maxUserConnInput.value = data.max_user_connections ?? '';
    status.innerHTML = `<span class="text-green-700">当前：max_connections=${mc}，max_user_connections=${muc}，Threads_connected=${tc}，Threads_running=${tr}</span>`;
  } catch (e) {
    status.innerHTML = `<span class="text-red-600">读取失败：${e.message}</span>`;
    if (maxConnValue) maxConnValue.textContent = '-';
    if (maxUserConnValue) maxUserConnValue.textContent = '-';
    if (threadsConnectedValue) threadsConnectedValue.textContent = '-';
    if (threadsRunningValue) threadsRunningValue.textContent = '-';
  }
}

async function applyMysqlConnectionLimits() {
  const status = $('mysql-conn-limit-status');
  const maxConnInput = $('mysql-max-connections-input');
  const maxUserConnInput = $('mysql-max-user-connections-input');
  const btn = $('btn-mysql-conn-apply');
  if (!status || !maxConnInput || !maxUserConnInput || !btn) return;
  const maxConnections = parseInt(maxConnInput.value, 10);
  const maxUserRaw = (maxUserConnInput.value || '').trim();
  if (!Number.isFinite(maxConnections) || maxConnections < 1) {
    status.innerHTML = '<span class="text-red-600">请输入合法的 max_connections（>=1）</span>';
    return;
  }
  const payload = { max_connections: maxConnections };
  if (maxUserRaw !== '') {
    const v = parseInt(maxUserRaw, 10);
    if (!Number.isFinite(v) || v < 0) {
      status.innerHTML = '<span class="text-red-600">max_user_connections 必须 >= 0</span>';
      return;
    }
    payload.max_user_connections = v;
  }
  btn.disabled = true;
  status.textContent = '应用中...';
  try {
    const res = await fetch(API_BASE + '/api/mysql-ops/connection-limits', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || '修改失败');
    maxConnInput.value = data.max_connections ?? '';
    maxUserConnInput.value = data.max_user_connections ?? '';
    status.innerHTML = `<span class="text-green-700">已更新：max_connections=${data.max_connections}，max_user_connections=${data.max_user_connections}（Threads_connected=${data.threads_connected}）</span>`;
  } catch (e) {
    status.innerHTML = `<span class="text-red-600">修改失败：${e.message}</span>`;
  }
  btn.disabled = false;
}

function initMysqlConnectionLimitControls() {
  const refreshBtn = $('btn-mysql-conn-refresh');
  const applyBtn = $('btn-mysql-conn-apply');
  if (refreshBtn && refreshBtn.dataset.bound !== '1') {
    refreshBtn.dataset.bound = '1';
    refreshBtn.addEventListener('click', loadMysqlConnectionLimits);
  }
  if (applyBtn && applyBtn.dataset.bound !== '1') {
    applyBtn.dataset.bound = '1';
    applyBtn.addEventListener('click', applyMysqlConnectionLimits);
  }
}

function initMysqlOpsOutputCopy() {
  const btn = $('btn-mysql-ops-copy');
  if (!btn || btn.dataset.bound === '1') return;
  btn.dataset.bound = '1';
  btn.addEventListener('click', copyMysqlOpsOutput);
}

function openMysqlAddModal() {
  const modal = $('mysql-add-modal');
  if (!modal) return;
  modal.classList.remove('hidden');
  const problemEl = $('mysql-add-problem');
  if (problemEl) problemEl.value = '';
  const statusEl = $('mysql-add-status');
  if (statusEl) statusEl.textContent = '';
}

let _mysqlAddGeneratePollTimer = null;

function closeMysqlAddModal() {
  if (_mysqlAddGeneratePollTimer) {
    clearInterval(_mysqlAddGeneratePollTimer);
    _mysqlAddGeneratePollTimer = null;
  }
  const modal = $('mysql-add-modal');
  if (modal) modal.classList.add('hidden');
}

function initMysqlAddModal() {
  const addBtn = $('btn-mysql-ops-add');
  const modal = $('mysql-add-modal');
  const closeBtn = $('mysql-add-modal-close');
  const cancelBtn = $('mysql-add-cancel');
  const backdrop = document.getElementById('mysql-add-modal-backdrop');
  const form = $('mysql-add-form');
  if (!addBtn || !form || addBtn.dataset.bound === '1') return;
  addBtn.dataset.bound = '1';
  addBtn.addEventListener('click', openMysqlAddModal);
  const refreshBtn = $('btn-mysql-ops-refresh-list');
  if (refreshBtn && refreshBtn.dataset.bound !== '1') {
    refreshBtn.dataset.bound = '1';
    refreshBtn.addEventListener('click', () => {
      if (typeof loadMysqlOpsStatus === 'function') loadMysqlOpsStatus();
    });
  }
  if (closeBtn) closeBtn.addEventListener('click', closeMysqlAddModal);
  if (cancelBtn) cancelBtn.addEventListener('click', closeMysqlAddModal);
  if (backdrop) backdrop.addEventListener('click', (e) => { if (e.target === backdrop) closeMysqlAddModal(); });
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const problem = $('mysql-add-problem').value?.trim();
    const statusEl = $('mysql-add-status');
    const submitBtn = $('mysql-add-submit');
    if (!problem) {
      statusEl.textContent = '请填写问题名称';
      statusEl.className = 'text-sm text-red-600';
      return;
    }
    submitBtn.disabled = true;
    statusEl.textContent = '提交中...';
    statusEl.className = 'text-sm text-gray-600';
    try {
      const res = await fetch(API_BASE + '/api/mysql-ops/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ problem }),
      });
      const data = await res.json().catch(() => ({}));
      if (res.ok && data.ok) {
        const initialCount = (MYSQL_OPS_LAST_PROBLEMS || []).length;
        statusEl.textContent = '已提交。正在检测新案例（约 1–3 分钟）…';
        statusEl.className = 'text-sm text-green-600';
        const maxPolls = 12;
        let pollCount = 0;
        const doPoll = async () => {
          pollCount++;
          try {
            if (typeof loadMysqlOpsStatus === 'function') await loadMysqlOpsStatus();
            const current = MYSQL_OPS_LAST_PROBLEMS || [];
            if (current.length > initialCount) {
              if (_mysqlAddGeneratePollTimer) {
                clearInterval(_mysqlAddGeneratePollTimer);
                _mysqlAddGeneratePollTimer = null;
              }
              const newProblem = current.find((p, i) => i >= initialCount);
              statusEl.textContent = '✓ 新案例已生成：' + (newProblem ? newProblem.id + ' - ' + (newProblem.name || '') : '');
              statusEl.className = 'text-sm text-green-600 font-medium';
              setTimeout(closeMysqlAddModal, 2500);
              return;
            }
          } catch (_) {}
          if (pollCount >= maxPolls) {
            if (_mysqlAddGeneratePollTimer) {
              clearInterval(_mysqlAddGeneratePollTimer);
              _mysqlAddGeneratePollTimer = null;
            }
            statusEl.textContent = '超时。若已生成请点击「刷新列表」查看。';
            statusEl.className = 'text-sm text-amber-600';
          } else {
            statusEl.textContent = `正在检测…（${pollCount}/${maxPolls}，每 25 秒）`;
          }
        };
        _mysqlAddGeneratePollTimer = setInterval(doPoll, 25000);
        doPoll();
      } else {
        statusEl.textContent = data.detail || data.message || '提交失败（请检查 Infra Config 中的 OpenClaw 配置）';
        statusEl.className = 'text-sm text-red-600';
      }
    } catch (err) {
      statusEl.textContent = '请求失败：' + (err.message || String(err));
      statusEl.className = 'text-sm text-red-600';
    }
    submitBtn.disabled = false;
  });
}

// 页面加载时立即渲染问题列表，确保列表始终可见（不依赖 tab 切换或 API）
function initMysqlOpsCardsOnLoad() {
  const cardsEl = document.getElementById('mysql-ops-cards');
  const statusEl = document.getElementById('mysql-ops-status');
  initMysqlCodeModal();
  initMysqlAddModal();
  initMysqlConnectionLimitControls();
  if (cardsEl) renderMysqlOpsCards(MYSQL_OPS_PROBLEMS_FALLBACK);
  initMysqlOpsOutputCopy();
  if (statusEl && !statusEl.textContent) statusEl.innerHTML = '<span class="text-gray-600">点击问题标题展开查看业务场景与详情。切换到此 Tab 后将尝试加载服务端数据。</span>';
}

// ========== Redis Ops ==========
let REDIS_OPS_LAST_PROBLEMS = [];

function renderRedisOpsCards(problems) {
  const cardsEl = $('redis-ops-cards');
  if (!cardsEl) return;
  const list = (problems && problems.length) ? problems : (REDIS_OPS_LAST_PROBLEMS || []);
  const esc = (s) => (s || '').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  cardsEl.innerHTML = list.map((p, i) => {
    const expanded = i === 0;
    return `
      <div class="border rounded-lg bg-white border-l-4 border-red-500 shadow-sm overflow-hidden">
        <button type="button" class="redis-ops-toggle w-full text-left px-4 py-3 flex items-center justify-between hover:bg-red-50 transition-colors" data-idx="${i}">
          <span class="font-semibold text-red-700">${String(i + 1).padStart(2, '0')} ${p.name}</span>
          <span class="redis-ops-chevron text-gray-400 text-sm transform transition-transform" style="transform: rotate(${expanded ? 180 : 0}deg)">▼</span>
        </button>
        <div class="redis-ops-body border-t border-gray-100 ${expanded ? '' : 'hidden'}">
          <div class="p-4 space-y-4">
            ${(p.business_scenario || p.businessScenario) ? `
            <div class="p-3 bg-sky-50 border-l-4 border-sky-400 rounded text-sm text-gray-700">
              <span class="font-medium text-sky-800 block mb-1">真实业务场景</span>
              <p>${esc(p.business_scenario || p.businessScenario)}</p>
            </div>
            ` : ''}
            <div class="space-y-3 text-sm">
              <div class="flex gap-2">
                <span class="shrink-0 px-2 py-0.5 rounded bg-blue-100 text-blue-800 text-xs font-medium">1</span>
                <div><span class="font-medium text-gray-700">业务场景：</span><span class="text-gray-600">${esc(p.scenario)}</span></div>
              </div>
              <div class="flex gap-2">
                <span class="shrink-0 px-2 py-0.5 rounded bg-amber-100 text-amber-800 text-xs font-medium">2</span>
                <div><span class="font-medium text-gray-700">现象：</span><span class="text-gray-600">${esc(p.phenomenon)}</span></div>
              </div>
              <div class="flex gap-2">
                <span class="shrink-0 px-2 py-0.5 rounded bg-red-100 text-red-800 text-xs font-medium">3</span>
                <div><span class="font-medium text-gray-700">问题：</span><span class="text-gray-600">${esc(p.problem)}</span></div>
              </div>
              <div class="flex gap-2">
                <span class="shrink-0 px-2 py-0.5 rounded bg-green-100 text-green-800 text-xs font-medium">4</span>
                <div><span class="font-medium text-gray-700">解决方案：</span><span class="text-gray-600">${esc(p.solution)}</span></div>
              </div>
            </div>
            <div class="flex flex-wrap gap-2 pt-2 border-t items-center">
              ${(p.actions || []).map(a => `
                <button class="redis-ops-run-btn px-3 py-1.5 bg-red-600 text-white rounded text-sm hover:bg-red-700 disabled:opacity-50" data-problem="${p.id}" data-action="${a.id}">Run: ${a.name}</button>
              `).join('')}
              <a href="#" class="redis-case-link text-sky-600 hover:text-sky-800 text-sm ml-2" data-problem="${p.id}">查看完整案例</a>
              <button class="redis-code-link px-3 py-1.5 bg-gray-100 text-gray-700 rounded text-sm hover:bg-gray-200" data-problem="${p.id}">查看/修改代码</button>
            </div>
          </div>
        </div>
      </div>
    `;
  }).join('');
  if (!list.length) {
    cardsEl.innerHTML = '<p class="text-gray-500 text-sm py-4">暂无问题列表，请检查 Redis 配置后点击刷新。</p>';
  }
}

// ========== Kafka Ops ==========
let KAFKA_OPS_LAST_PROBLEMS = [];

function renderKafkaOpsCards(problems) {
  const cardsEl = $('kafka-ops-cards');
  if (!cardsEl) return;
  const list = (problems && problems.length) ? problems : (KAFKA_OPS_LAST_PROBLEMS || []);
  const esc = (s) => (s || '').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  cardsEl.innerHTML = list.map((p, i) => {
    const expanded = i === 0;
    return `
      <div class="border rounded-lg bg-white border-l-4 border-emerald-600 shadow-sm overflow-hidden">
        <button type="button" class="kafka-ops-toggle w-full text-left px-4 py-3 flex items-center justify-between hover:bg-emerald-50 transition-colors" data-idx="${i}">
          <span class="font-semibold text-emerald-700">${String(i + 1).padStart(2, '0')} ${p.name}</span>
          <span class="kafka-ops-chevron text-gray-400 text-sm transform transition-transform" style="transform: rotate(${expanded ? 180 : 0}deg)">▼</span>
        </button>
        <div class="kafka-ops-body border-t border-gray-100 ${expanded ? '' : 'hidden'}">
          <div class="p-4 space-y-4">
            ${(p.business_scenario || p.businessScenario) ? `
            <div class="p-3 bg-sky-50 border-l-4 border-sky-400 rounded text-sm text-gray-700">
              <span class="font-medium text-sky-800 block mb-1">真实业务场景</span>
              <p>${esc(p.business_scenario || p.businessScenario)}</p>
            </div>
            ` : ''}
            <div class="space-y-3 text-sm">
              <div class="flex gap-2">
                <span class="shrink-0 px-2 py-0.5 rounded bg-blue-100 text-blue-800 text-xs font-medium">1</span>
                <div><span class="font-medium text-gray-700">业务场景：</span><span class="text-gray-600">${esc(p.scenario)}</span></div>
              </div>
              <div class="flex gap-2">
                <span class="shrink-0 px-2 py-0.5 rounded bg-amber-100 text-amber-800 text-xs font-medium">2</span>
                <div><span class="font-medium text-gray-700">现象：</span><span class="text-gray-600">${esc(p.phenomenon)}</span></div>
              </div>
              <div class="flex gap-2">
                <span class="shrink-0 px-2 py-0.5 rounded bg-red-100 text-red-800 text-xs font-medium">3</span>
                <div><span class="font-medium text-gray-700">问题：</span><span class="text-gray-600">${esc(p.problem)}</span></div>
              </div>
              <div class="flex gap-2">
                <span class="shrink-0 px-2 py-0.5 rounded bg-green-100 text-green-800 text-xs font-medium">4</span>
                <div><span class="font-medium text-gray-700">解决方案：</span><span class="text-gray-600">${esc(p.solution)}</span></div>
              </div>
            </div>
            <div class="flex flex-wrap gap-2 pt-2 border-t items-center">
              ${(p.actions || []).map(a => `
                <button class="kafka-ops-run-btn px-3 py-1.5 bg-emerald-600 text-white rounded text-sm hover:bg-emerald-700 disabled:opacity-50" data-problem="${p.id}" data-action="${a.id}">Run: ${a.name}</button>
              `).join('')}
              <a href="#" class="kafka-case-link text-sky-600 hover:text-sky-800 text-sm" data-problem="${p.id}">查看完整案例</a>
              <button class="kafka-code-link px-3 py-1.5 bg-gray-100 text-gray-700 rounded text-sm hover:bg-gray-200" data-problem="${p.id}">查看/修改代码</button>
            </div>
          </div>
        </div>
      </div>
    `;
  }).join('');
  if (!list.length) {
    cardsEl.innerHTML = '<p class="text-gray-500 text-sm py-4">暂无问题列表，请点击刷新。</p>';
  }
}

async function loadKafkaOpsStatus() {
  const statusEl = $('kafka-ops-status');
  const cardsEl = $('kafka-ops-cards');
  if (!statusEl || !cardsEl) return;
  try {
    const res = await fetch(API_BASE + '/api/kafka-ops/problems');
    const data = await res.json();
    const problems = data.problems || [];
    KAFKA_OPS_LAST_PROBLEMS = problems;
    renderKafkaOpsCards(problems);
    if (data.kafka_available) {
      statusEl.innerHTML = '<span class="text-green-700">✓ Kafka 已配置。可在 Infra Config 中点击「测试 Kafka 连接」验证。</span>';
    } else {
      statusEl.innerHTML = '<span class="text-amber-700">⚠ 请先在 Infra Config 中配置 Kafka Brokers。</span>';
    }
  } catch (e) {
    statusEl.innerHTML = '<span class="text-amber-700">加载失败：' + (e.message || e) + '</span>';
    renderKafkaOpsCards([]);
  }
}

async function openKafkaCaseModal(problemId) {
  const modal = document.getElementById('kafka-case-modal');
  const titleEl = document.getElementById('kafka-case-modal-title');
  const bodyEl = document.getElementById('kafka-case-modal-body');
  const closeBtn = document.getElementById('kafka-case-modal-close');
  const backdrop = document.getElementById('kafka-case-modal-backdrop');
  if (!modal || !titleEl || !bodyEl) return;
  titleEl.textContent = '加载中...';
  bodyEl.innerHTML = '';
  modal.classList.remove('hidden');
  try {
    const res = await fetch(API_BASE + '/api/kafka-ops/case/' + encodeURIComponent(problemId));
    const data = await res.json();
    titleEl.textContent = '完整业务案例 - ' + problemId;
    const html = renderRedisCaseContent(data.content || '无内容');
    bodyEl.innerHTML = html;
    if (typeof mermaid !== 'undefined') {
      const mermaidNodes = bodyEl.querySelectorAll('.mermaid');
      if (mermaidNodes.length) {
        try {
          mermaid.initialize({ startOnLoad: false, theme: 'neutral' });
          await new Promise(r => requestAnimationFrame(r));
          await mermaid.run({ nodes: mermaidNodes, suppressErrors: true });
        } catch (err) {
          console.warn('Mermaid render:', err);
          mermaidNodes.forEach(n => { n.innerHTML = '<pre class="text-xs text-amber-600">' + n.textContent + '</pre>'; });
        }
      }
    }
  } catch (e) {
    titleEl.textContent = '加载失败';
    bodyEl.innerHTML = '<p class="text-red-600">Error: ' + (e.message || e) + '</p>';
  }
  function closeModal() {
    modal.classList.add('hidden');
    document.removeEventListener('keydown', onEsc);
  }
  function onEsc(e) {
    if (e.key === 'Escape') closeModal();
  }
  closeBtn.onclick = closeModal;
  backdrop.onclick = (e) => { if (e.target === backdrop) closeModal(); };
  document.addEventListener('keydown', onEsc);
}

async function runKafkaOps(problem, action, btn) {
  const out = $('kafka-ops-output');
  if (!out) return;
  if (btn) btn.disabled = true;
  out.classList.remove('hidden');
  out.textContent = 'Running...';
  try {
    const res = await fetch(API_BASE + '/api/kafka-ops/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ problem, action }),
    });
    const data = await res.json();
    out.textContent = (data.stdout || '') + (data.stderr ? '\n' + data.stderr : '');
    if (data.ok) out.classList.add('text-green-400'); else out.classList.add('text-red-400');
  } catch (e) {
    out.textContent = 'Error: ' + e.message;
    out.classList.add('text-red-400');
  }
  if (btn) btn.disabled = false;
}

const KAFKA_CODE_MODAL_STATE = { problemId: '', filePath: '' };

async function loadKafkaCodeFile(problemId, filePath) {
  const editor = $('kafka-code-editor');
  const status = $('kafka-code-status');
  if (!editor || !status) return;
  status.textContent = '加载文件中...';
  const res = await fetch(API_BASE + '/api/kafka-ops/code/' + encodeURIComponent(problemId) + '?path=' + encodeURIComponent(filePath));
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || '加载失败');
  editor.value = data.content || '';
  KAFKA_CODE_MODAL_STATE.filePath = data.path || filePath;
  status.textContent = '已加载：' + KAFKA_CODE_MODAL_STATE.filePath;
}

async function openKafkaCodeModal(problemId) {
  const modal = $('kafka-code-modal');
  const title = $('kafka-code-modal-title');
  const fileSel = $('kafka-code-file-select');
  const runSel = $('kafka-code-run-action');
  const status = $('kafka-code-status');
  const editor = $('kafka-code-editor');
  if (!modal || !title || !fileSel || !runSel || !status || !editor) return;

  KAFKA_CODE_MODAL_STATE.problemId = problemId;
  KAFKA_CODE_MODAL_STATE.filePath = '';
  const p = (KAFKA_OPS_LAST_PROBLEMS || []).find(x => x.id === problemId);
  title.textContent = '问题代码 - ' + (p ? p.name : problemId);

  try {
    const res = await fetch(API_BASE + '/api/kafka-ops/code/' + encodeURIComponent(problemId) + '/files');
    const data = await res.json();
    const files = data.files || [];
    fileSel.innerHTML = files.map(f => `<option value="${f}">${f}</option>`).join('');
    runSel.innerHTML = (p?.actions || []).map(a => `<option value="${a.id}">${a.name}</option>`).join('') || '<option value="">-</option>';
    if (files.length > 0) {
      await loadKafkaCodeFile(problemId, files[0]);
    } else {
      editor.value = '';
      status.textContent = '当前问题目录下没有可编辑文件。请确保 kafka-ops-learning 存在于 performance 同级目录。';
    }
  } catch (e) {
    status.textContent = '加载失败：' + (e.message || e);
    editor.value = '';
  }
  modal.classList.remove('hidden');

  fileSel.onchange = () => { if (fileSel.value) loadKafkaCodeFile(problemId, fileSel.value); };
  $('kafka-code-save-btn').onclick = async () => {
    if (!KAFKA_CODE_MODAL_STATE.filePath) return;
    const res = await fetch(API_BASE + '/api/kafka-ops/code/' + encodeURIComponent(problemId), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path: KAFKA_CODE_MODAL_STATE.filePath, content: editor.value }),
    });
    const d = await res.json();
    status.textContent = res.ok ? '已保存' : (d.detail || '保存失败');
  };
  $('kafka-code-run-btn').onclick = async () => {
    if (!KAFKA_CODE_MODAL_STATE.filePath) return;
    const saveRes = await fetch(API_BASE + '/api/kafka-ops/code/' + encodeURIComponent(problemId), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path: KAFKA_CODE_MODAL_STATE.filePath, content: editor.value }),
    });
    if (!saveRes.ok) { status.textContent = '保存失败'; return; }
    const action = runSel.value;
    if (!action) { status.textContent = '请选择运行动作'; return; }
    const runRes = await fetch(API_BASE + '/api/kafka-ops/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ problem: problemId, action }),
    });
    const runData = await runRes.json();
    const out = $('kafka-ops-output');
    if (out) {
      out.classList.remove('hidden');
      out.textContent = (runData.stdout || '') + (runData.stderr ? '\n' + runData.stderr : '');
    }
    status.textContent = '已保存并运行';
  };
  $('kafka-code-close').onclick = () => modal.classList.add('hidden');
  document.getElementById('kafka-code-modal-backdrop').onclick = (e) => { if (e.target.id === 'kafka-code-modal-backdrop') modal.classList.add('hidden'); };
}

async function loadRedisOpsStatus() {
  const statusEl = $('redis-ops-status');
  const cardsEl = $('redis-ops-cards');
  if (!statusEl || !cardsEl) return;
  try {
    const res = await fetch(API_BASE + '/api/redis-ops/problems');
    const data = await res.json();
    const problems = data.problems || [];
    REDIS_OPS_LAST_PROBLEMS = problems;
    renderRedisOpsCards(problems);
    if (data.redis_available) {
      statusEl.innerHTML = '<span class="text-green-700">✓ Redis 已就绪。使用 Infra 配置连接。</span>';
    } else {
      statusEl.innerHTML = '<span class="text-amber-700">⚠ 请先在 Infra Config 中配置 Redis。</span>';
    }
  } catch (e) {
    statusEl.innerHTML = '<span class="text-amber-700">加载失败：' + (e.message || e) + '</span>';
    renderRedisOpsCards([]);
  }
}

async function runRedisOps(problem, action, btn) {
  const out = $('redis-ops-output');
  if (!out) return;
  if (btn) btn.disabled = true;
  out.classList.remove('hidden');
  out.textContent = 'Running...';
  try {
    const res = await fetch(API_BASE + '/api/redis-ops/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ problem, action }),
    });
    const data = await res.json();
    let text = data.stdout || '';
    if (data.stderr) text += (text ? '\n\n' : '') + 'STDERR:\n' + data.stderr;
    if (!text && data.detail) text = 'ERROR:\n' + data.detail;
    out.textContent = text || '(no output)';
    out.classList.remove('text-red-400');
    if (!data.ok) out.classList.add('text-red-400');
    out.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  } catch (e) {
    out.textContent = 'Error: ' + e.message;
    out.classList.add('text-red-400');
  }
  if (btn) btn.disabled = false;
}

function renderRedisCaseContent(md) {
  if (!md) return '';
  const parts = [];
  let rest = md;
  const re = /```mermaid\r?\n([\s\S]*?)\r?\n```/gi;
  let lastIdx = 0;
  let m;
  while ((m = re.exec(md)) !== null) {
    parts.push({ type: 'md', text: md.slice(lastIdx, m.index) });
    parts.push({ type: 'mermaid', code: m[1].trim() });
    lastIdx = re.lastIndex;
  }
  parts.push({ type: 'md', text: md.slice(lastIdx) });
  let out = '';
  for (const p of parts) {
    if (p.type === 'mermaid') {
      out += '<div class="mermaid my-4">' + p.code + '</div>';
    } else if (p.type === 'md' && p.text) {
      out += typeof marked !== 'undefined' ? marked.parse(p.text) : p.text.replace(/</g, '&lt;');
    }
  }
  return out;
}

async function openRedisCaseModal(problemId) {
  const modal = document.getElementById('redis-case-modal');
  const titleEl = document.getElementById('redis-case-modal-title');
  const bodyEl = document.getElementById('redis-case-modal-body');
  const closeBtn = document.getElementById('redis-case-modal-close');
  const backdrop = document.getElementById('redis-case-modal-backdrop');
  if (!modal || !titleEl || !bodyEl) return;
  titleEl.textContent = '加载中...';
  bodyEl.innerHTML = '';
  modal.classList.remove('hidden');
  try {
    const res = await fetch(API_BASE + '/api/redis-ops/case/' + encodeURIComponent(problemId));
    const data = await res.json();
    titleEl.textContent = '完整业务案例 - ' + problemId;
    const html = renderRedisCaseContent(data.content || '无内容');
    bodyEl.innerHTML = html;
    if (typeof mermaid !== 'undefined') {
      const mermaidNodes = bodyEl.querySelectorAll('.mermaid');
      if (mermaidNodes.length) {
        try {
          mermaid.initialize({ startOnLoad: false, theme: 'neutral' });
          await new Promise(r => requestAnimationFrame(r));
          await mermaid.run({ nodes: mermaidNodes, suppressErrors: true });
        } catch (err) {
          console.warn('Mermaid render:', err);
          mermaidNodes.forEach(n => { n.innerHTML = '<pre class="text-xs text-amber-600">' + n.textContent + '</pre>'; });
        }
      }
    }
  } catch (e) {
    titleEl.textContent = '加载失败';
    bodyEl.innerHTML = '<p class="text-red-600">Error: ' + (e.message || e) + '</p>';
  }
  function closeModal() {
    modal.classList.add('hidden');
    document.removeEventListener('keydown', onEsc);
  }
  function onEsc(e) {
    if (e.key === 'Escape') closeModal();
  }
  closeBtn.onclick = closeModal;
  backdrop.onclick = (e) => { if (e.target === backdrop) closeModal(); };
  document.addEventListener('keydown', onEsc);
}

function getRedisProblemById(problemId) {
  return (REDIS_OPS_LAST_PROBLEMS || []).find(p => p.id === problemId);
}

const REDIS_CODE_MODAL_STATE = { problemId: '', filePath: '' };

async function loadRedisCodeFile(problemId, filePath) {
  const editor = $('redis-code-editor');
  const status = $('redis-code-status');
  if (!editor || !status) return;
  status.textContent = '加载文件中...';
  const res = await fetch(API_BASE + '/api/redis-ops/code/' + encodeURIComponent(problemId) + '?path=' + encodeURIComponent(filePath));
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || '加载失败');
  editor.value = data.content || '';
  REDIS_CODE_MODAL_STATE.filePath = data.path || filePath;
  status.textContent = '已加载：' + REDIS_CODE_MODAL_STATE.filePath;
}

async function openRedisCodeModal(problemId) {
  const modal = $('redis-code-modal');
  const title = $('redis-code-modal-title');
  const fileSel = $('redis-code-file-select');
  const runSel = $('redis-code-run-action');
  const status = $('redis-code-status');
  const editor = $('redis-code-editor');
  if (!modal || !title || !fileSel || !runSel || !status || !editor) return;

  REDIS_CODE_MODAL_STATE.problemId = problemId;
  REDIS_CODE_MODAL_STATE.filePath = '';
  const p = getRedisProblemById(problemId);
  title.textContent = `问题代码 - ${p ? p.name : problemId}`;
  editor.value = '';
  fileSel.innerHTML = '';
  runSel.innerHTML = ((p && p.actions) || []).map(a => `<option value="${a.id}">${a.name}</option>`).join('');

  modal.classList.remove('hidden');
  status.textContent = '正在获取文件列表...';
  try {
    const res = await fetch(API_BASE + '/api/redis-ops/code/' + encodeURIComponent(problemId) + '/files');
    const data = await res.json();
    if (!res.ok) {
      status.textContent = '获取文件失败：' + (data.detail || 'unknown');
      return;
    }
    const files = data.files || [];
    if (!files.length) {
      status.textContent = '当前问题目录下没有可编辑文件。请确保 redis-ops-learning 存在于 performance 同级目录。';
      return;
    }
    fileSel.innerHTML = files.map(f => `<option value="${f}">${f}</option>`).join('');
    await loadRedisCodeFile(problemId, files[0]);
  } catch (e) {
    status.textContent = '获取失败：' + (e.message || e);
  }
}

async function saveRedisCodeModal() {
  const problemId = REDIS_CODE_MODAL_STATE.problemId;
  const fileSel = $('redis-code-file-select');
  const editor = $('redis-code-editor');
  const status = $('redis-code-status');
  if (!problemId || !fileSel || !editor || !status) return;
  const path = fileSel.value;
  status.textContent = '保存中...';
  const res = await fetch(API_BASE + '/api/redis-ops/code/' + encodeURIComponent(problemId), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ path, content: editor.value }),
  });
  const data = await res.json();
  if (!res.ok) {
    status.textContent = '保存失败：' + (data.detail || 'unknown');
    return;
  }
  status.textContent = '保存成功：' + (data.path || path);
}

function initRedisCodeModal() {
  const modal = $('redis-code-modal');
  const backdrop = $('redis-code-modal-backdrop');
  const closeBtn = $('redis-code-close');
  const fileSel = $('redis-code-file-select');
  const saveBtn = $('redis-code-save-btn');
  const runBtn = $('redis-code-run-btn');
  const runSel = $('redis-code-run-action');
  const editor = $('redis-code-editor');
  if (!modal || !backdrop || !closeBtn || !fileSel || !saveBtn || !runBtn || !runSel || !editor) return;
  if (modal.dataset.bound === '1') return;
  modal.dataset.bound = '1';

  const closeModal = () => modal.classList.add('hidden');
  closeBtn.addEventListener('click', closeModal);
  backdrop.addEventListener('click', (e) => { if (e.target === backdrop) closeModal(); });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && !modal.classList.contains('hidden')) closeModal();
  });
  fileSel.addEventListener('change', async () => {
    if (!REDIS_CODE_MODAL_STATE.problemId || !fileSel.value) return;
    try {
      await loadRedisCodeFile(REDIS_CODE_MODAL_STATE.problemId, fileSel.value);
    } catch (e) {
      const status = $('redis-code-status');
      if (status) status.textContent = '加载失败：' + e.message;
    }
  });
  saveBtn.addEventListener('click', saveRedisCodeModal);
  runBtn.addEventListener('click', async () => {
    await saveRedisCodeModal();
    const action = runSel.value;
    if (!REDIS_CODE_MODAL_STATE.problemId || !action) return;
    await runRedisOps(REDIS_CODE_MODAL_STATE.problemId, action, runBtn);
  });
}

function initKafkaOpsOnLoad() {
  const refreshBtn = $('btn-kafka-ops-refresh');
  if (refreshBtn && refreshBtn.dataset.bound !== '1') {
    refreshBtn.dataset.bound = '1';
    refreshBtn.addEventListener('click', loadKafkaOpsStatus);
  }
  const copyBtn = $('btn-kafka-ops-copy');
  if (copyBtn && copyBtn.dataset.bound !== '1') {
    copyBtn.dataset.bound = '1';
    copyBtn.addEventListener('click', () => {
      const out = $('kafka-ops-output');
      if (out && out.textContent) navigator.clipboard.writeText(out.textContent);
    });
  }
  initKafkaAddModal();
}

function openKafkaAddModal() {
  const modal = $('kafka-add-modal');
  if (!modal) return;
  modal.classList.remove('hidden');
  const problemEl = $('kafka-add-problem');
  if (problemEl) problemEl.value = '';
  const statusEl = $('kafka-add-status');
  if (statusEl) statusEl.textContent = '';
}

let _kafkaAddGeneratePollTimer = null;

function closeKafkaAddModal() {
  if (_kafkaAddGeneratePollTimer) {
    clearInterval(_kafkaAddGeneratePollTimer);
    _kafkaAddGeneratePollTimer = null;
  }
  const modal = $('kafka-add-modal');
  if (modal) modal.classList.add('hidden');
}

function initKafkaAddModal() {
  const addBtn = $('btn-kafka-ops-add');
  const closeBtn = $('kafka-add-modal-close');
  const cancelBtn = $('kafka-add-cancel');
  const backdrop = document.getElementById('kafka-add-modal-backdrop');
  const form = $('kafka-add-form');
  if (!addBtn || !form || addBtn.dataset.bound === '1') return;
  addBtn.dataset.bound = '1';
  addBtn.addEventListener('click', openKafkaAddModal);
  if (closeBtn) closeBtn.addEventListener('click', closeKafkaAddModal);
  if (cancelBtn) cancelBtn.addEventListener('click', closeKafkaAddModal);
  if (backdrop) backdrop.addEventListener('click', (e) => { if (e.target === backdrop) closeKafkaAddModal(); });
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const problem = $('kafka-add-problem').value?.trim();
    const statusEl = $('kafka-add-status');
    const submitBtn = $('kafka-add-submit');
    if (!problem) {
      statusEl.textContent = '请填写问题名称';
      statusEl.className = 'text-sm text-red-600';
      return;
    }
    submitBtn.disabled = true;
    statusEl.textContent = '提交中...';
    statusEl.className = 'text-sm text-gray-600';
    try {
      const res = await fetch(API_BASE + '/api/kafka-ops/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ problem }),
      });
      const data = await res.json().catch(() => ({}));
      if (res.ok && data.ok) {
        const initialCount = (KAFKA_OPS_LAST_PROBLEMS || []).length;
        statusEl.textContent = '已提交。正在检测新案例（约 1–3 分钟）…';
        statusEl.className = 'text-sm text-green-600';
        const maxPolls = 12;
        let pollCount = 0;
        const doPoll = async () => {
          pollCount++;
          try {
            if (typeof loadKafkaOpsStatus === 'function') await loadKafkaOpsStatus();
            const current = KAFKA_OPS_LAST_PROBLEMS || [];
            if (current.length > initialCount) {
              if (_kafkaAddGeneratePollTimer) {
                clearInterval(_kafkaAddGeneratePollTimer);
                _kafkaAddGeneratePollTimer = null;
              }
              statusEl.textContent = '新案例已生成，请查看列表。';
              submitBtn.disabled = false;
              return;
            }
          } catch (err) {}
          if (pollCount >= maxPolls) {
            if (_kafkaAddGeneratePollTimer) {
              clearInterval(_kafkaAddGeneratePollTimer);
              _kafkaAddGeneratePollTimer = null;
            }
            statusEl.textContent = '超时。请稍后手动点击刷新列表查看。';
            submitBtn.disabled = false;
          }
        };
        doPoll();
        _kafkaAddGeneratePollTimer = setInterval(doPoll, 15000);
      } else {
        statusEl.textContent = data.detail || '提交失败';
        statusEl.className = 'text-sm text-red-600';
        submitBtn.disabled = false;
      }
    } catch (err) {
      statusEl.textContent = 'Error: ' + (err.message || err);
      statusEl.className = 'text-sm text-red-600';
      submitBtn.disabled = false;
    }
  });
}

function initRedisOpsOnLoad() {
  const refreshBtn = $('btn-redis-ops-refresh');
  const copyBtn = $('btn-redis-ops-copy');
  if (refreshBtn && refreshBtn.dataset.bound !== '1') {
    refreshBtn.dataset.bound = '1';
    refreshBtn.addEventListener('click', loadRedisOpsStatus);
  }
  if (copyBtn && copyBtn.dataset.bound !== '1') {
    copyBtn.dataset.bound = '1';
    copyBtn.addEventListener('click', () => {
      const out = $('redis-ops-output');
      if (out && out.textContent) {
        navigator.clipboard.writeText(out.textContent);
      }
    });
  }
  initRedisCodeModal();
  initRedisAddModal();
  renderRedisOpsCards([]);
}

function openRedisAddModal() {
  const modal = $('redis-add-modal');
  if (!modal) return;
  modal.classList.remove('hidden');
  const problemEl = $('redis-add-problem');
  if (problemEl) problemEl.value = '';
  const statusEl = $('redis-add-status');
  if (statusEl) statusEl.textContent = '';
}

let _redisAddGeneratePollTimer = null;

function closeRedisAddModal() {
  if (_redisAddGeneratePollTimer) {
    clearInterval(_redisAddGeneratePollTimer);
    _redisAddGeneratePollTimer = null;
  }
  const modal = $('redis-add-modal');
  if (modal) modal.classList.add('hidden');
}

function initRedisAddModal() {
  const addBtn = $('btn-redis-ops-add');
  const closeBtn = $('redis-add-modal-close');
  const cancelBtn = $('redis-add-cancel');
  const backdrop = document.getElementById('redis-add-modal-backdrop');
  const form = $('redis-add-form');
  if (!addBtn || !form || addBtn.dataset.bound === '1') return;
  addBtn.dataset.bound = '1';
  addBtn.addEventListener('click', openRedisAddModal);
  if (closeBtn) closeBtn.addEventListener('click', closeRedisAddModal);
  if (cancelBtn) cancelBtn.addEventListener('click', closeRedisAddModal);
  if (backdrop) backdrop.addEventListener('click', (e) => { if (e.target === backdrop) closeRedisAddModal(); });
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const problem = $('redis-add-problem').value?.trim();
    const statusEl = $('redis-add-status');
    const submitBtn = $('redis-add-submit');
    if (!problem) {
      statusEl.textContent = '请填写问题名称';
      statusEl.className = 'text-sm text-red-600';
      return;
    }
    submitBtn.disabled = true;
    statusEl.textContent = '提交中...';
    statusEl.className = 'text-sm text-gray-600';
    try {
      const res = await fetch(API_BASE + '/api/redis-ops/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ problem }),
      });
      const data = await res.json().catch(() => ({}));
      if (res.ok && data.ok) {
        const initialCount = (REDIS_OPS_LAST_PROBLEMS || []).length;
        statusEl.textContent = '已提交。正在检测新案例（约 1–3 分钟）…';
        statusEl.className = 'text-sm text-green-600';
        const maxPolls = 12;
        let pollCount = 0;
        const doPoll = async () => {
          pollCount++;
          try {
            if (typeof loadRedisOpsStatus === 'function') await loadRedisOpsStatus();
            const current = REDIS_OPS_LAST_PROBLEMS || [];
            if (current.length > initialCount) {
              if (_redisAddGeneratePollTimer) {
                clearInterval(_redisAddGeneratePollTimer);
                _redisAddGeneratePollTimer = null;
              }
              statusEl.textContent = '新案例已生成，请查看列表。';
              submitBtn.disabled = false;
              return;
            }
          } catch (err) {}
          if (pollCount >= maxPolls) {
            if (_redisAddGeneratePollTimer) {
              clearInterval(_redisAddGeneratePollTimer);
              _redisAddGeneratePollTimer = null;
            }
            statusEl.textContent = '超时。请稍后手动点击刷新列表查看。';
            submitBtn.disabled = false;
          }
        };
        doPoll();
        _redisAddGeneratePollTimer = setInterval(doPoll, 15000);
      } else {
        statusEl.textContent = data.detail || '提交失败';
        statusEl.className = 'text-sm text-red-600';
        submitBtn.disabled = false;
      }
    } catch (err) {
      statusEl.textContent = 'Error: ' + (err.message || err);
      statusEl.className = 'text-sm text-red-600';
      submitBtn.disabled = false;
    }
  });
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => {
    initMysqlOpsCardsOnLoad();
    initRedisOpsOnLoad();
    initKafkaOpsOnLoad();
  });
} else {
  initMysqlOpsCardsOnLoad();
  initRedisOpsOnLoad();
  initKafkaOpsOnLoad();
}
