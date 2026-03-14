"""
DEX Ops Dashboard API - Config, Deploy, Monitor, Perf Test.
"""
import asyncio
import json
import os
import shlex
import subprocess
from pathlib import Path
from typing import Any, List, Optional

from fastapi import Body, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .config_store import get_infra_config, save_infra_config, get_perftest_config, save_perftest_config
from .config_generator import generate_perf_yaml
from .locust_generator import generate_locustfile
from .validate import ensure_mysql_database, run_mysql_init_sql
from .validate import validate_all

app = FastAPI(title="DEX Ops Dashboard", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

PERF_DIR = Path(__file__).parent.parent
PERFTEST_DIR = PERF_DIR / "perftest"


# --- Pydantic models ---
class RedisConfig(BaseModel):
    host: str = "127.0.0.1"
    port: int = 6379
    password: str = ""


class MySQLConfig(BaseModel):
    host: str = "127.0.0.1"
    port: int = 3306
    user: str = "root"
    password: str = ""
    database: str = "dexs"


class KafkaConfig(BaseModel):
    brokers: str = "127.0.0.1:9092"  # comma-separated


class AppServerConfig(BaseModel):
    host: str = ""
    ssh_port: int = 22
    ssh_user: str = "root"
    deploy_path: str = "/opt/dex"
    mysql_ops_path: str = "/opt/dex/mysql-ops-learning"


class GithubConfig(BaseModel):
    repo_url: str = ""
    branch: str = "main"
    subpath: str = ""  # e.g. "dex_full" if project root is inside repo


class InfraConfig(BaseModel):
    redis: RedisConfig = RedisConfig()
    mysql: MySQLConfig = MySQLConfig()
    kafka: KafkaConfig = KafkaConfig()
    app_server: AppServerConfig = AppServerConfig()
    github: GithubConfig = GithubConfig()
    gateway_url: str = "http://127.0.0.1:8080"
    mysql_init_sql: str = ""  # 建表 SQL，Validate/Deploy 时自动执行


class EndpointItem(BaseModel):
    path: str = "/api/health"
    method: str = "GET"
    weight: int = 1
    name: Optional[str] = None


class PerftestConfig(BaseModel):
    endpoints: List[Any] = []  # [{"path":"/api/health","method":"GET","weight":1}, ...]
    users: int = 50
    ramp_up_seconds: int = 10
    duration_seconds: int = 30


# --- API routes ---
@app.get("/api/config")
def get_config():
    """Get current infra config."""
    config = get_infra_config()
    if config is None:
        return {"exists": False, "config": None}
    # Parse brokers for form
    if "kafka" in config and "brokers" in config["kafka"]:
        b = config["kafka"]["brokers"]
        if isinstance(b, list):
            config["kafka"]["brokers"] = ",".join(b)
    return {"exists": True, "config": config}


@app.post("/api/config")
def save_config(infra: InfraConfig):
    """Save infra config."""
    raw = infra.model_dump()
    # Convert brokers string to list
    if isinstance(raw.get("kafka", {}).get("brokers"), str):
        raw["kafka"] = raw.get("kafka", {})
        raw["kafka"]["brokers"] = [b.strip() for b in raw["kafka"]["brokers"].split(",") if b.strip()]
    if save_infra_config(raw):
        return {"ok": True}
    raise HTTPException(status_code=500, detail="Failed to save config")


@app.post("/api/config/validate")
def validate_config():
    """Validate connectivity to Redis, MySQL, Kafka."""
    config = get_infra_config()
    if not config:
        raise HTTPException(status_code=400, detail="No config saved. Save config first.")
    return validate_all(config)


@app.get("/api/config/generate")
def generate_configs():
    """Generate *-perf.yaml contents from saved config."""
    config = get_infra_config()
    if not config:
        raise HTTPException(status_code=400, detail="No config saved. Save config first.")
    return generate_perf_yaml(config)


class DeployRequest(BaseModel):
    """Optional SSH password for first-time auto ssh-copy-id. Not persisted."""
    ssh_password: Optional[str] = None


def _run_deploy(ssh_password: Optional[str] = None) -> dict:
    """Run deploy script; shared by POST /api/deploy and webhook."""
    config = get_infra_config()
    if not config:
        raise HTTPException(status_code=400, detail="No config saved. Save config first.")
    # 部署前自动建库并执行初始化 SQL（如 MySQL 已配置）
    m = config.get("mysql", {})
    if m.get("host"):
        db = m.get("database", "dexs")
        ok, msg = ensure_mysql_database(
            m.get("host", "127.0.0.1"),
            int(m.get("port", 3306)),
            m.get("user", "root"),
            m.get("password", ""),
            db,
        )
        if not ok:
            return {"ok": False, "returncode": 1, "stdout": "", "stderr": f"MySQL 自动建库失败: {msg}"}
        init_sql = config.get("mysql_init_sql", "")
        if init_sql:
            ok2, msg2 = run_mysql_init_sql(
                m.get("host", "127.0.0.1"),
                int(m.get("port", 3306)),
                m.get("user", "root"),
                m.get("password", ""),
                db,
                init_sql,
            )
            if not ok2:
                return {"ok": False, "returncode": 1, "stdout": "", "stderr": f"MySQL 初始化 SQL 失败: {msg2}"}
    deploy_script = PERF_DIR / "scripts" / "deploy.sh"
    if not deploy_script.exists():
        raise HTTPException(status_code=501, detail="Deploy script not found.")
    env = {**os.environ, "PERF_CONFIG": str(PERF_DIR / "config" / "infra.json")}
    if ssh_password:
        env["PERF_SSH_PASSWORD"] = ssh_password
    proc = subprocess.run(
        ["bash", str(deploy_script)],
        cwd=str(PERF_DIR),
        capture_output=True,
        text=True,
        env=env,
        stdin=subprocess.DEVNULL,  # 避免 ssh 等在终端上阻塞等待输入
    )
    return {
        "ok": proc.returncode == 0,
        "returncode": proc.returncode,
        "stdout": proc.stdout or "",
        "stderr": proc.stderr or "",
    }


@app.post("/api/deploy")
async def trigger_deploy(req: DeployRequest = Body(default=DeployRequest())):
    """
    Trigger deploy script. Runs scripts/deploy.sh with current config.
    Optional: pass ssh_password for first-time auto setup of SSH key (not saved).
    """
    return _run_deploy(ssh_password=req.ssh_password)


@app.api_route("/api/deploy/webhook", methods=["GET", "POST"])
async def deploy_webhook(
    token: Optional[str] = Query(None),
    x_deploy_token: Optional[str] = Header(None, alias="X-Deploy-Token"),
):
    """
    Webhook for CI/CD: trigger deploy from GitHub Action, Jenkins, etc.
    Supports GET and POST (Jenkins often uses GET). If PERF_DEPLOY_TOKEN env is set,
    requests must pass it via ?token= or X-Deploy-Token header.
    """
    required = os.environ.get("PERF_DEPLOY_TOKEN")
    if required:
        passed = token or x_deploy_token
        if passed != required:
            raise HTTPException(status_code=401, detail="Invalid or missing deploy token")
    result = _run_deploy(ssh_password=None)
    if not result["ok"]:
        raise HTTPException(status_code=500, detail=result.get("stderr", "Deploy failed"))
    return {"ok": True, "stdout": result["stdout"]}


def _check_project_health(gateway_url: str, timeout: float = 3.0) -> dict:
    """HTTP health check for deployed project. Returns status, latency_ms, message."""
    if not gateway_url or not gateway_url.startswith("http"):
        return {"status": "unknown", "message": "未配置 Gateway 地址"}
    import httpx
    # Try /health, /api/health, or root
    for path in ["/health", "/api/health", ""]:
        url = gateway_url.rstrip("/") + (path or "")
        try:
            with httpx.Client(timeout=timeout) as client:
                resp = client.get(url)
                if resp.status_code == 200:
                    return {"status": "up", "latency_ms": int(resp.elapsed.total_seconds() * 1000), "message": "运行中"}
        except Exception as e:
            continue
    return {"status": "down", "message": "HTTP 请求失败，项目可能未启动"}


@app.get("/api/metrics")
def get_metrics():
    """
    Fetch CPU, memory, project status from servers via SSH.
    Project server: full metrics + HTTP health check.
    """
    config = get_infra_config()
    if not config:
        return {"machines": []}

    import subprocess
    machines = []

    # Project server - we have SSH user, fetch full metrics + health
    app = config.get("app_server", {})
    app_host = app.get("host", "").strip()
    gateway_url = (config.get("gateway_url") or "").strip()
    # Use app_host if gateway_url points to localhost
    if gateway_url and "127.0.0.1" in gateway_url and app_host:
        gateway_url = gateway_url.replace("127.0.0.1", app_host)

    if app_host:
        script = PERF_DIR / "scripts" / "fetch_metrics.sh"
        if script.exists():
            try:
                r = subprocess.run(
                    ["bash", str(script), app.get("ssh_user", "root"), app_host, str(app.get("ssh_port", 22))],
                    capture_output=True, text=True, timeout=10, cwd=str(PERF_DIR),
                    stdin=subprocess.DEVNULL,
                )
                if r.returncode == 0 and r.stdout:
                    m = json.loads(r.stdout.strip())
                    procs = m.get("project_procs", "0")
                    ports = m.get("ports_listen", "") or "-"
                    health = _check_project_health(gateway_url)
                    machines.append({
                        "name": "项目服务器",
                        "host": app_host,
                        "cpu": m.get("cpu_pct"),
                        "memory": f"{m.get('mem_used_mb')}/{m.get('mem_total_mb')} MB",
                        "disk_read": m.get("disk_read"),
                        "disk_write": m.get("disk_write"),
                        "project_procs": str(procs),
                        "ports_listen": str(ports),
                        "project_status": health.get("status", "unknown"),
                        "project_message": health.get("message", ""),
                        "project_latency_ms": health.get("latency_ms"),
                    })
                else:
                    health = _check_project_health(gateway_url)
                    machines.append({
                        "name": "项目服务器",
                        "host": app_host,
                        "error": r.stderr or "SSH failed",
                        "project_status": health.get("status", "unknown"),
                        "project_message": health.get("message", ""),
                    })
            except Exception as e:
                health = _check_project_health(gateway_url)
                machines.append({
                    "name": "项目服务器",
                    "host": app_host,
                    "error": str(e),
                    "project_status": health.get("status", "unknown"),
                    "project_message": health.get("message", ""),
                })
        else:
            machines.append({"name": "项目服务器", "host": app_host, "note": "需配置 SSH 免密登录"})

    # MySQL, Redis, Kafka - show host (SSH metrics optional)
    for name, key in [("MySQL", "mysql"), ("Redis", "redis")]:
        c = config.get(key, {})
        host = c.get("host", c.get("Path", "")).strip()
        if host:
            machines.append({"name": name, "host": host, "port": c.get("port"), "note": "配置 SSH 后可查看监控"})
    k = config.get("kafka", {})
    brokers = k.get("brokers", [])
    if isinstance(brokers, str):
        brokers = [b.strip() for b in brokers.split(",") if b.strip()]
    for b in brokers[:1]:
        machines.append({"name": "Kafka", "host": b.split(":")[0] if ":" in b else b, "note": "配置 SSH 后可查看监控"})

    return {"machines": machines}


@app.get("/api/perftest/config")
def get_perftest():
    """Get perftest config (endpoints, users, ramp_up, duration)."""
    cfg = get_perftest_config()
    if cfg is None:
        return {"exists": False, "config": {"endpoints": [{"path": "/api/health", "method": "GET", "weight": 1}], "users": 50, "ramp_up_seconds": 10, "duration_seconds": 30}}
    return {"exists": True, "config": cfg}


@app.post("/api/perftest/config")
def save_perftest(cfg: PerftestConfig):
    """Save perftest config."""
    raw = cfg.model_dump()
    if save_perftest_config(raw):
        return {"ok": True}
    raise HTTPException(status_code=500, detail="Failed to save perftest config")


@app.post("/api/perftest/run")
async def run_perftest():
    """
    Run Locust performance test.
    Uses: gateway_url from infra, endpoints/users/ramp_up/duration from perftest config.
    """
    config = get_infra_config()
    if not config:
        raise HTTPException(status_code=400, detail="No config saved. Save config first.")

    gateway_url = config.get("gateway_url", "http://127.0.0.1:8080")
    pt_cfg = get_perftest_config() or {}
    users = int(pt_cfg.get("users", 50))
    ramp_up = max(1, int(pt_cfg.get("ramp_up_seconds", 10)))
    duration = max(5, int(pt_cfg.get("duration_seconds", 30)))
    spawn_rate = max(1, users // ramp_up)  # 每秒启动的线程数
    endpoints = pt_cfg.get("endpoints", [])

    # 根据配置生成 locustfile
    locust_content = generate_locustfile(endpoints)
    generated_file = PERF_DIR / "config" / "locustfile_generated.py"
    generated_file.parent.mkdir(parents=True, exist_ok=True)
    generated_file.write_text(locust_content, encoding="utf-8")

    try:
        html_report = PERF_DIR / "config" / "perftest_report.html"
        proc = await asyncio.create_subprocess_exec(
            "locust",
            "-f", str(generated_file),
            "--host", gateway_url.rstrip("/"),
            "--headless",
            "-u", str(users),
            "-r", str(spawn_rate),
            "-t", str(duration),
            "--html", str(html_report),
            "--csv", str(PERF_DIR / "config" / "perftest"),
            cwd=str(PERFTEST_DIR),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        out = stdout.decode() if stdout else ""

        # Parse CSV stats if available
        csv_file = PERF_DIR / "config" / "perftest_stats.csv"
        result_data = None
        if csv_file.exists():
            lines = csv_file.read_text().strip().split("\n")
            if len(lines) >= 2:
                headers = lines[0].split(",")
                rows = [dict(zip(headers, r.split(","))) for r in lines[1:] if r]
                result_data = {"stats": rows, "summary": out}

        return {
            "ok": proc.returncode == 0,
            "result": result_data,
            "stdout": out,
            "stderr": stderr.decode() if stderr else "",
            "html_report": "/api/perftest/report" if html_report.exists() else None,
        }
    except FileNotFoundError:
        raise HTTPException(
            status_code=500,
            detail="Locust not installed. Run: pip install locust",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/perftest/report")
def get_perftest_report():
    """Serve the last HTML report if exists."""
    from fastapi.responses import FileResponse
    report = PERF_DIR / "config" / "perftest_report.html"
    if report.exists():
        return FileResponse(report, media_type="text/html")
    raise HTTPException(status_code=404, detail="No report yet")


@app.get("/api/perftest/result")
def get_perftest_result():
    """Get last performance test result."""
    result_file = PERF_DIR / "config" / "perftest_result.json"
    if not result_file.exists():
        return {"exists": False}
    with open(result_file) as f:
        return {"exists": True, "result": json.load(f)}


# --- MySQL Ops (mysql-ops-learning integration) ---
MYSQL_OPS_DIR = PERF_DIR.parent / "mysql-ops-learning"
MYSQL_CASES_DIR = PERF_DIR / "mysql-cases"


def _build_mysql_dsn(config: dict) -> str:
    """Build MYSQL_DSN from Infra config."""
    m = config.get("mysql", {})
    host = m.get("host", "127.0.0.1")
    port = int(m.get("port", 3306))
    user = m.get("user", "root")
    password = m.get("password", "")
    database = m.get("database", "jmeter_test")
    return f"{user}:{password}@tcp({host}:{port})/{database}?charset=utf8mb4&parseTime=True"


MYSQL_OPS_PROBLEMS = [
    {
        "id": "01-max-connections",
        "name": "最大连接数耗尽",
        "scenario": "应用未正确复用连接，不断创建新连接而不释放。连接池配置不当或存在连接泄漏。",
        "phenomenon": "新连接报错 Too many connections；应用无法访问数据库；Threads_connected 接近 max_connections。",
        "problem": "MySQL 连接数达到上限，无法接受新连接。通常由连接泄漏、连接池过小或并发突增导致。",
        "solution": "1. 调整 max_connections（若确实需要更多连接）；2. 应用层使用连接池，避免每请求一连接；3. 排查并修复未关闭连接；4. 调整 wait_timeout 缩短空闲连接占用。",
        "actions": [{"id": "reproduce", "name": "模拟耗尽"}, {"id": "monitor", "name": "查看状态"}],
    },
    {
        "id": "02-slow-log",
        "name": "慢查询监控",
        "scenario": "线上偶发接口变慢，但不知道是哪些 SQL 导致。需要开启慢查询日志定位问题语句。",
        "phenomenon": "接口响应时间不稳定；数据库负载波动；用户反馈卡顿。",
        "problem": "部分 SQL 执行时间过长，但未开启慢日志或未设置合适阈值，无法定位具体慢查询。",
        "solution": "1. 开启 slow_query_log；2. 设置 long_query_time（如 2 秒）；3. 使用 pt-query-digest 或 MySQL 工具分析慢日志；4. 针对慢查询加索引或改写。",
        "actions": [{"id": "reproduce", "name": "模拟慢查询"}, {"id": "enable", "name": "开启慢日志"}],
    },
    {
        "id": "03-large-transaction",
        "name": "大事务",
        "scenario": "批量更新/插入在单事务内执行过多行，事务持有锁时间过长。",
        "phenomenon": "其他会话长时间等待；复制延迟；undo log 膨胀；锁等待超时。",
        "problem": "单事务修改大量行，长时间持有行锁/表锁，阻塞其他事务，并可能造成主从延迟和回滚段膨胀。",
        "solution": "1. 拆分为小批次，每批 500–1000 行提交一次；2. 缩短事务内操作，尽快提交；3. 通过 INNODB_TRX 监控长事务，及早发现。",
        "actions": [{"id": "reproduce", "name": "模拟大事务"}, {"id": "detect", "name": "检测长事务"}],
    },
    {
        "id": "04-large-table",
        "name": "大表问题",
        "scenario": "单表数据量持续增长，全表扫描、DDL 变更耗时过长或长时间锁表。",
        "phenomenon": "查询变慢；ALTER TABLE 执行数小时；锁表导致业务不可用。",
        "problem": "表过大导致全表扫描、DDL 需要重建表，锁表时间长，影响线上业务。",
        "solution": "1. 分区：按范围/哈希拆分大表；2. 在线 DDL：MySQL 8.0 ALGORITHM=INPLACE 或 pt-osc、gh-ost；3. 数据归档；4. 合理建索引避免全表扫描。",
        "actions": [{"id": "reproduce", "name": "模拟大表"}, {"id": "analyze", "name": "分析表大小"}],
    },
    {
        "id": "05-deadlock",
        "name": "死锁",
        "scenario": "多事务并发更新，加锁顺序不一致，互相等待对方持有的锁。",
        "phenomenon": "事务报错 Deadlock found；部分事务被自动回滚；偶发失败需重试。",
        "problem": "事务 A 锁表1→等表2，事务 B 锁表2→等表1，形成环路。MySQL 会回滚其中一个。",
        "solution": "1. 统一加锁顺序（如按 ID 升序）；2. 死锁后自动重试；3. 缩短事务；4. 通过索引保证访问路径一致。",
        "actions": [{"id": "reproduce", "name": "模拟死锁"}, {"id": "analyze", "name": "查看死锁信息"}],
    },
    {
        "id": "06-lock-wait-timeout",
        "name": "锁等待超时",
        "scenario": "事务 A 持锁未提交，事务 B 等待同一行锁，超过 innodb_lock_wait_timeout 后报错。",
        "phenomenon": "报错 Lock wait timeout exceeded；更新/删除操作失败；需手动重试。",
        "problem": "持锁事务长时间不提交，阻塞其他事务。默认等待 50 秒后超时。",
        "solution": "1. 缩短持锁时间，尽快提交；2. 调整 innodb_lock_wait_timeout；3. 通过 INNODB_LOCK_WAITS 定位阻塞；4. 必要时 KILL 阻塞会话。",
        "actions": [{"id": "reproduce", "name": "模拟等待"}],
    },
    {
        "id": "07-index-misuse",
        "name": "索引使用不当",
        "scenario": "查询条件列无索引或索引未被使用，导致全表扫描。",
        "phenomenon": "单条 SQL 执行很慢；EXPLAIN 显示 type=ALL、rows 很大。",
        "problem": "未建索引或索引不符合查询条件，MySQL 只能全表扫描，数据量大时性能极差。",
        "solution": "1. 对 WHERE/ORDER BY 列建索引；2. 避免 SELECT *；3. 使用覆盖索引；4. 通过 EXPLAIN 检查执行计划。",
        "actions": [{"id": "reproduce", "name": "模拟全表扫描"}, {"id": "explain", "name": "查看执行计划"}],
    },
]


def _load_case_business_scenario(problem_id: str) -> str:
    """Load 业务需求场景 from mysql-cases/*.md if exists."""
    case_file = MYSQL_CASES_DIR / f"{problem_id}.md"
    if not case_file.exists():
        return ""
    text = case_file.read_text(encoding="utf-8")
    if "## 业务需求场景" not in text:
        return ""
    start = text.index("## 业务需求场景") + len("## 业务需求场景")
    end = text.find("\n## ", start)
    if end == -1:
        end = len(text)
    block = text[start:end].strip()
    # Clean markdown bold, join into single paragraph
    block = block.replace("**", "").strip()
    return " ".join(block.split())  # collapse whitespace


@app.get("/api/mysql-ops/case/{problem_id}")
def get_mysql_ops_case(problem_id: str):
    """Return full case markdown for a problem. Used by '查看完整案例' link."""
    case_file = MYSQL_CASES_DIR / f"{problem_id}.md"
    if not case_file.exists():
        raise HTTPException(status_code=404, detail="Case not found")
    return {"content": case_file.read_text(encoding="utf-8")}


@app.get("/api/mysql-ops/problems")
def list_mysql_ops_problems():
    """List available problems with scenario, phenomenon, problem, solution. Enriches with business scenario from mysql-cases/."""
    config = get_infra_config() or {}
    app_server = config.get("app_server", {})
    mysql_ops_available = bool(app_server.get("host", "").strip())
    problems = []
    for p in MYSQL_OPS_PROBLEMS:
        obj = dict(p)
        scenario_from_file = _load_case_business_scenario(p["id"])
        if scenario_from_file:
            obj["business_scenario"] = scenario_from_file  # 真实业务场景段落
        problems.append(obj)
    return {
        "problems": problems,
        "mysql_ops_available": mysql_ops_available,
    }


class MysqlOpsRunRequest(BaseModel):
    problem: str
    action: str


def _ssh_args_from_config(config: dict) -> List[str]:
    app_server = config.get("app_server", {})
    host = app_server.get("host", "").strip()
    if not host:
        raise HTTPException(status_code=400, detail="App server host is required. Please save Infra config first.")
    port = int(app_server.get("ssh_port", 22))
    user = app_server.get("ssh_user", "root").strip() or "root"
    args = [
        "ssh",
        "-o", "StrictHostKeyChecking=no",
        "-o", "ConnectTimeout=10",
    ]
    if port != 22:
        args.extend(["-p", str(port)])
    args.append(f"{user}@{host}")
    return args


async def _resolve_remote_mysql_ops_dir(config: dict) -> str:
    app_server = config.get("app_server", {})
    deploy_path = app_server.get("deploy_path", "/opt/dex").strip() or "/opt/dex"
    preferred = app_server.get("mysql_ops_path", "").strip()
    candidates = []
    if preferred:
        candidates.append(preferred)
    candidates.extend([
        f"{deploy_path}/mysql-ops-learning",
        f"{deploy_path}/code/mysql-ops-learning",
        "~/mysql-ops-learning",
    ])
    # de-duplicate while preserving order
    seen = set()
    unique_candidates = []
    for c in candidates:
        if c not in seen:
            seen.add(c)
            unique_candidates.append(c)

    search_list = " ".join(shlex.quote(p) for p in unique_candidates)
    probe_script = (
        "for p in " + search_list + "; do "
        '[ -d "$p" ] && printf "%s" "$p" && exit 0; '
        "done; exit 1"
    )
    remote_probe_cmd = f"bash -lc {shlex.quote(probe_script)}"
    proc = await asyncio.create_subprocess_exec(
        *_ssh_args_from_config(config),
        remote_probe_cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=20)
    except asyncio.TimeoutError:
        proc.kill()
        raise HTTPException(status_code=500, detail="SSH probe timeout while searching mysql-ops-learning on app server.")

    if proc.returncode == 0 and stdout:
        return stdout.decode("utf-8", errors="replace").strip()

    detail = (
        "mysql-ops-learning not found on app server. "
        f"Tried: {', '.join(unique_candidates)}. "
        "Please upload code to one of these paths or set app_server.mysql_ops_path in Infra Config."
    )
    if stderr:
        detail += f" SSH error: {stderr.decode('utf-8', errors='replace').strip()}"
    raise HTTPException(status_code=500, detail=detail)


@app.post("/api/mysql-ops/run")
async def run_mysql_ops(req: MysqlOpsRunRequest):
    """
    Run mysql-ops-learning on remote app server via SSH.
    Uses MySQL config from Infra and executes real scenario code on target server.
    """
    config = get_infra_config()
    if not config:
        raise HTTPException(status_code=400, detail="No config saved. Save Infra config with MySQL first.")

    dsn = _build_mysql_dsn(config)
    remote_dir = await _resolve_remote_mysql_ops_dir(config)
    app_server = config.get("app_server", {})
    deploy_path = app_server.get("deploy_path", "/opt/dex").strip() or "/opt/dex"
    remote_cmd = (
        "set -e; "
        "source /etc/profile >/dev/null 2>&1 || true; "
        "export PATH=\"$PATH:/usr/local/go/bin:/usr/local/bin\"; "
        f"export MYSQL_DSN={shlex.quote(dsn)}; "
        f"cd {shlex.quote(remote_dir)}; "
        "if command -v go >/dev/null 2>&1; then "
        f"  go run ./cmd run {shlex.quote(req.problem)} {shlex.quote(req.action)}; "
        "elif [ -x ./build/main ]; then "
        f"  ./build/main run {shlex.quote(req.problem)} {shlex.quote(req.action)}; "
        f"elif [ -x {shlex.quote(deploy_path)}/build/main ]; then "
        f"  {shlex.quote(deploy_path)}/build/main run {shlex.quote(req.problem)} {shlex.quote(req.action)}; "
        "else "
        "  echo 'go not found and no executable build/main found on app server.' 1>&2; "
        "  echo 'Please install Go or run Deploy to upload /opt/dex/build/main.' 1>&2; "
        "  exit 127; "
        "fi"
    )

    try:
        remote_exec_cmd = f"bash -lc {shlex.quote(remote_cmd)}"
        proc = await asyncio.create_subprocess_exec(
            *_ssh_args_from_config(config),
            remote_exec_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=180)
        return {
            "ok": proc.returncode == 0,
            "stdout": stdout.decode("utf-8", errors="replace"),
            "stderr": stderr.decode("utf-8", errors="replace"),
        }
    except asyncio.TimeoutError:
        return {"ok": False, "stdout": "", "stderr": "Timeout (180s). Remote scenario may still be running on app server."}
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="SSH command not found on dashboard host.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Serve frontend last so /api routes take precedence
_frontend = Path(__file__).parent.parent / "frontend"
if _frontend.exists():
    app.mount("/", StaticFiles(directory=str(_frontend), html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
