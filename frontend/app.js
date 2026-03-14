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
      $('app-server-mysql-ops-path').value = c.app_server.mysql_ops_path || '/opt/dex/mysql-ops-learning';
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
    app_server: {
      host: $('app-server-host').value,
      ssh_port: parseInt($('app-server-ssh-port').value) || 22,
      ssh_user: $('app-server-ssh-user').value || 'root',
      deploy_path: $('app-server-deploy-path').value || '/opt/dex',
      mysql_ops_path: $('app-server-mysql-ops-path').value || '/opt/dex/mysql-ops-learning',
    },
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

// MySQL Ops - 业务场景 / 现象 / 问题 / 解决方案（前端静态数据作为回退，确保 Run 按钮始终可见）
const MYSQL_OPS_PROBLEMS_FALLBACK = [
  { id: "01-max-connections", name: "最大连接数耗尽", business_scenario: "电商平台大促秒杀：双11 活动开始瞬间每秒 5000+ 请求，应用每次新建 MySQL 连接且未归还，max_connections=500 约 10 秒后新请求全部报 Too many connections，用户界面显示「系统繁忙，请稍后再试」，活动被迫暂停。", scenario: "应用未正确复用连接，不断创建新连接而不释放。", phenomenon: "新连接报错 Too many connections；Threads_connected 接近 max_connections。", problem: "MySQL 连接数达到上限。", solution: "调整 max_connections；使用连接池；修复连接泄漏。", actions: [{ id: "reproduce", name: "模拟耗尽" }, { id: "monitor", name: "查看状态" }] },
  { id: "02-slow-log", name: "慢查询监控", business_scenario: "O2O 平台用户搜索订单：输入订单号或手机号查询，要等十几秒才能出结果，有时直接超时。DBA 发现数据库 CPU 偶发飙高，但未开慢查询日志，无法定位是哪条 SQL 导致。", scenario: "线上偶发接口变慢，需定位慢 SQL。", phenomenon: "接口响应时间不稳定；数据库负载波动。", problem: "部分 SQL 执行时间过长，未开启慢日志无法定位。", solution: "开启 slow_query_log；设置 long_query_time；用 pt-query-digest 分析。", actions: [{ id: "reproduce", name: "模拟慢查询" }, { id: "enable", name: "开启慢日志" }] },
  { id: "03-large-transaction", name: "大事务", business_scenario: "积分商城周年庆：运营给 10 万用户每人加 100 积分，单事务内 UPDATE 10 万行，执行约 5 分钟才提交。这 5 分钟内所有涉及 user_points 的操作（登录校验、下单扣积分、查询余额）全被阻塞，前台业务几乎停滞。", scenario: "批量更新在单事务内执行过多行。", phenomenon: "其他会话长时间等待；复制延迟；锁等待超时。", problem: "单事务修改大量行，长时间持锁阻塞其他事务。", solution: "拆分为小批次；缩短事务；通过 INNODB_TRX 监控。", actions: [{ id: "reproduce", name: "模拟大事务" }, { id: "detect", name: "检测长事务" }] },
  { id: "04-large-table", name: "大表问题", business_scenario: "订单表 5000 万行需新增 coupon_id 字段。DBA 执行 ALTER TABLE 使用默认 COPY 算法，重建整表约 2 小时，期间表被锁定，用户无法下单、无法查订单，大促前夜执行导致活动推迟。", scenario: "单表数据量持续增长，DDL 耗时过长。", phenomenon: "查询变慢；ALTER TABLE 执行数小时；锁表。", problem: "表过大导致全表扫描、DDL 锁表时间长。", solution: "分区；在线 DDL（pt-osc、gh-ost）；数据归档；合理建索引。", actions: [{ id: "reproduce", name: "模拟大表" }, { id: "analyze", name: "分析表大小" }] },
  { id: "05-deadlock", name: "死锁", business_scenario: "用户 A 给 B 转 100 元、B 同时给 A 转 50 元。两事务均为先锁转出方再锁转入方，形成 A 等 B、B 等 A 的环路，MySQL 检测到死锁回滚其一，用户看到「交易失败，请重试」。", scenario: "多事务并发更新，加锁顺序不一致。", phenomenon: "事务报错 Deadlock found；部分事务被自动回滚。", problem: "事务互相等待对方持有的锁，形成环路。", solution: "统一加锁顺序；死锁后自动重试；缩短事务。", actions: [{ id: "reproduce", name: "模拟死锁" }, { id: "analyze", name: "查看死锁信息" }] },
  { id: "06-lock-wait-timeout", name: "锁等待超时", business_scenario: "SaaS 平台运营导出全部用户报表：事务内 SELECT * FROM users 全表扫描且长时间不提交。前台用户尝试更新头像、昵称需要排他锁，等待超过 50 秒后返回 Lock wait timeout exceeded，用户看到「修改失败，请重试」。", scenario: "事务 A 持锁未提交，事务 B 等待同一行锁。", phenomenon: "报错 Lock wait timeout exceeded；更新/删除失败。", problem: "持锁事务长时间不提交，阻塞其他事务。", solution: "缩短持锁时间；调整 innodb_lock_wait_timeout；定位并 KILL 阻塞会话。", actions: [{ id: "reproduce", name: "模拟等待" }] },
  { id: "07-index-misuse", name: "索引使用不当", business_scenario: "外卖订单表 1000 万行，用户按手机号查订单。WHERE phone=? 无索引，MySQL 全表扫描，单次查询 20~30 秒，接口超时，用户看到「加载失败」，数据库 CPU 长期偏高。", scenario: "查询条件列无索引或索引未被使用。", phenomenon: "单条 SQL 执行很慢；EXPLAIN 显示 type=ALL。", problem: "未建索引或索引不符合查询，导致全表扫描。", solution: "对 WHERE/ORDER BY 列建索引；避免 SELECT *；通过 EXPLAIN 检查。", actions: [{ id: "reproduce", name: "模拟全表扫描" }, { id: "explain", name: "查看执行计划" }] },
];

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
            </div>
          </div>
        </div>
      </div>
    `;
  }).join('');
  // 点击由 document 事件委托统一处理，此处无需再绑定
}

async function openMysqlCaseModal(problemId) {
  const modal = document.getElementById('mysql-case-modal');
  const titleEl = document.getElementById('mysql-case-modal-title');
  const bodyEl = document.getElementById('mysql-case-modal-body');
  const closeBtn = document.getElementById('mysql-case-modal-close');
  const backdrop = document.getElementById('mysql-case-modal-backdrop');
  if (!modal || !titleEl || !bodyEl) return;
  titleEl.textContent = '加载中...';
  bodyEl.textContent = '';
  modal.classList.remove('hidden');
  try {
    const res = await fetch(API_BASE + '/api/mysql-ops/case/' + encodeURIComponent(problemId));
    const data = await res.json();
    titleEl.textContent = '完整业务案例 - ' + problemId;
    bodyEl.textContent = data.content || '无内容';
  } catch (e) {
    titleEl.textContent = '加载失败';
    bodyEl.textContent = 'Error: ' + e.message;
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
  renderMysqlOpsCards(problems);
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

function initMysqlOpsOutputCopy() {
  const btn = $('btn-mysql-ops-copy');
  if (!btn || btn.dataset.bound === '1') return;
  btn.dataset.bound = '1';
  btn.addEventListener('click', copyMysqlOpsOutput);
}

// 页面加载时立即渲染问题列表，确保列表始终可见（不依赖 tab 切换或 API）
function initMysqlOpsCardsOnLoad() {
  const cardsEl = document.getElementById('mysql-ops-cards');
  const statusEl = document.getElementById('mysql-ops-status');
  if (cardsEl) renderMysqlOpsCards(MYSQL_OPS_PROBLEMS_FALLBACK);
  initMysqlOpsOutputCopy();
  if (statusEl && !statusEl.textContent) statusEl.innerHTML = '<span class="text-gray-600">点击问题标题展开查看业务场景与详情。切换到此 Tab 后将尝试加载服务端数据。</span>';
}
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initMysqlOpsCardsOnLoad);
} else {
  initMysqlOpsCardsOnLoad();
}
