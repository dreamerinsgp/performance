"""
DEX Ops Dashboard API - Config, Deploy, Monitor, Perf Test.
"""
import asyncio
import json
import os
import shlex
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pymysql
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
    username: str = ""  # Redis 6+ ACL，阿里云普通账号需填写，默认账号留空


class MySQLConfig(BaseModel):
    host: str = "127.0.0.1"
    port: int = 3306
    user: str = "root"
    password: str = ""
    database: str = "dexs"


class KafkaConfig(BaseModel):
    brokers: str = "127.0.0.1:9092"  # comma-separated
    username: str = ""  # SASL username (e.g. Aliyun 公网 9093)
    password: str = ""  # SASL password


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
    token: str = ""  # GitHub PAT for private repos (HTTPS clone)


class OpenClawConfig(BaseModel):
    gateway_url: str = "http://127.0.0.1:18789"
    hooks_token: str = ""


class InfraConfig(BaseModel):
    redis: RedisConfig = RedisConfig()
    mysql: MySQLConfig = MySQLConfig()
    kafka: KafkaConfig = KafkaConfig()
    app_server: AppServerConfig = AppServerConfig()
    github: GithubConfig = GithubConfig()
    gateway_url: str = "http://127.0.0.1:8080"
    mysql_init_sql: str = ""  # 建表 SQL，Validate/Deploy 时自动执行
    openclaw: Optional[OpenClawConfig] = None  # OpenClaw for MySQL Ops case generation


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


class ValidateKafkaRequest(BaseModel):
    brokers: str = "127.0.0.1:9092"


@app.post("/api/config/validate/kafka")
def validate_kafka(req: ValidateKafkaRequest):
    """Quick test Kafka connectivity (TCP) without saving config."""
    try:
        from .validate import check_kafka

        brokers = [b.strip() for b in req.brokers.split(",") if b.strip()]
        if not brokers:
            return {"ok": False, "message": "No brokers configured"}
        ok, msg = check_kafka(brokers)
        return {"ok": ok, "message": msg}
    except Exception as e:
        return {"ok": False, "message": str(e)}


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


def _discover_endpoints_from_gateway_yaml(gateway_path: Path) -> Optional[Dict[str, Any]]:
    """Parse gateway.yaml and return { projects: [{ id, name, endpoints }], source: 'gateway' }."""
    try:
        import yaml
        data = yaml.safe_load(gateway_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not data:
        return None
    upstreams = data.get("Upstreams") or []
    # Group by path prefix: /v1/market -> market
    by_prefix: Dict[str, List[Dict[str, str]]] = {}
    name_map = {
        "market": "Market（行情）",
        "trade": "Trade（交易）",
        "account": "Account（账户）",
        "consumer": "Consumer（消费）",
        "dcmsg": "Discord 消息",
        "twmsg": "Twitter 消息",
        "rebate": "Rebate（返佣）",
        "admin": "Admin 管理",
        "campaign": "Campaign（活动）",
        "push": "Push（推送）",
    }
    for up in upstreams:
        if not isinstance(up, dict):
            continue
        grpc = up.get("Grpc")
        mappings = (grpc.get("Mappings") or []) if isinstance(grpc, dict) else []
        if not mappings:
            mappings = up.get("Mappings") or []  # go-zero: Mappings 与 Grpc 同级
        for m in mappings:
            if not isinstance(m, dict):
                continue
            path = (m.get("Path") or "").strip()
            method = (m.get("Method") or "get").upper()
            if not path or path == "/":
                continue
            # /v1/market/xxx -> market, /v1/admin/xxx -> admin
            parts = path.strip("/").split("/")
            prefix = parts[1] if len(parts) >= 2 else "other"
            if prefix not in by_prefix:
                by_prefix[prefix] = []
            by_prefix[prefix].append({"path": path, "method": method})
    projects = []
    for pid, eps in sorted(by_prefix.items()):
        projects.append({
            "id": pid,
            "name": name_map.get(pid, pid),
            "endpoints": eps,
        })
    return {"source": "gateway", "projects": projects}


def _get_deployed_project_root() -> Optional[Tuple[Path, Path]]:
    """Get (project_root, clone_dir) of the deployed project (from Infra config + workspace)."""
    config = get_infra_config()
    if not config:
        return None
    github = config.get("github") or {}
    repo_url = (github.get("repo_url") or "").strip()
    subpath = (github.get("subpath") or "").strip()
    if not repo_url:
        return None
    repo_name = Path(repo_url.rstrip("/")).name
    if repo_name.endswith(".git"):
        repo_name = repo_name[:-4]
    ws = PERF_DIR / "workspace"
    clone_dir = ws / repo_name
    if not clone_dir.exists() or not clone_dir.is_dir():
        return None
    project_root = clone_dir / subpath if subpath else clone_dir
    if not project_root.exists():
        return None
    return (project_root, clone_dir)


def _ensure_git_branch(clone_dir: Path, branch: str) -> bool:
    """Checkout the configured branch in workspace clone. 确保读取 infra 配置的分支."""
    if not branch or not (clone_dir / ".git").exists():
        return True
    try:
        subprocess.run(
            ["git", "fetch", "origin", branch],
            cwd=str(clone_dir),
            capture_output=True,
            text=True,
            timeout=30,
        )
        r = subprocess.run(
            ["git", "checkout", "-B", branch, f"origin/{branch}"],
            cwd=str(clone_dir),
            capture_output=True,
            text=True,
            timeout=10,
        )
        if r.returncode != 0:
            subprocess.run(
                ["git", "checkout", branch],
                cwd=str(clone_dir),
                capture_output=True,
                text=True,
                timeout=10,
            )
        return True
    except Exception:
        return False


def _discover_perftest_endpoints() -> Dict[str, Any]:
    """Discover testable projects and HTTP endpoints from the deployed project's gateway.yaml only."""
    pair = _get_deployed_project_root()
    if not pair:
        return {
            "source": "deployed",
            "projects": [],
            "message": "请先完成部署。发现接口仅从已部署项目的 Gateway 配置读取。",
        }
    project_root, clone_dir = pair
    # 按 Infra 配置的分支 checkout，确保读取的是正确分支的 gateway.yaml
    config = get_infra_config() or {}
    branch = (config.get("github") or {}).get("branch") or "main"
    _ensure_git_branch(clone_dir, branch)
    # 与 deploy.sh 一致的路径：DEX / go-zero / 嵌套 dex_full
    candidates = [
        project_root / "apps" / "gateway" / "etc" / "gateway.yaml",
        project_root / "gateway" / "etc" / "gateway.yaml",
        project_root / "dex_full" / "apps" / "gateway" / "etc" / "gateway.yaml",
    ]
    for p in candidates:
        if p.exists():
            result = _discover_endpoints_from_gateway_yaml(p)
            if result:
                result["source"] = "deployed"
                result["message"] = "来自已部署项目的 Gateway 配置"
                return result
    return {
        "source": "deployed",
        "projects": [],
        "message": "已部署项目中未找到 gateway.yaml（apps/gateway/etc/ 或 gateway/etc/）。",
    }


PROJECT_SCENARIOS_FILE = PERF_DIR / "config" / "project_scenarios.json"


# 真实业务场景：路径模式 -> (场景名, 用途描述, 风险)
_MYSQL_SCENARIO_RULES = [
    ("model/solmodel/blockmodel", "区块数据处理", "Consumer 消费链上区块后落库，用于断点续传与状态追踪", "高并发写入阻塞"),
    ("model/solmodel/pairmodel", "交易对信息存储", "存储 DEX 交易对（Pair）元数据，供行情与交易服务查询", "大表需索引"),
    ("model/solmodel/tokenmodel", "代币元数据存储", "存储代币 CA、名称、精度等，供行情与下单使用", ""),
    ("model/solmodel/trademodel", "链上交易记录", "存储链上成交记录，供 K 线、成交列表等查询", "高写入 QPS"),
    ("model/trademodel/tradeordermodel", "限价单订单", "用户挂单数据，买卖队列、价格、数量", "锁竞争、大表"),
    ("model/trademodel/tradeorderlogmodel", "订单操作日志", "订单创建、成交、取消等操作流水", ""),
]

_REDIS_SCENARIO_RULES = [
    ("trade/internal/ticker", "链上交易检查锁", "CheckOnChainTxRedisKey 分布式锁，防止同一笔链上交易重复提交", "锁超时影响撮合"),
    ("trade/internal/proclimitorder/tokenpricelimit", "限价单价格队列与锁", "Redis List 存买单/卖单队列，锁保护价格触发时的并发处理", "热 key、队列堆积"),
    ("pkg/xredis", "分布式锁工具", "xredis.Lock/MustLock 封装，供 ticker、tokenpricelimit 等使用", ""),
]

_KAFKA_SCENARIO_RULES = [
    ("consumer/internal/logic/mq/producer", "Producer 发送链上交易", "Consumer 服务将链上成交事件发送到 Kafka，供 market 消费", "发送失败影响 K 线"),
    ("market/internal/mqs/consumers/trade_consumer", "Consumer 消费交易事件", "解析 TradeWithPair 消息，更新 K 线、推送 WebSocket", "lag 导致 K 线延迟"),
]


def _match_scenario_rules(rules: List[Tuple[str, str, str, str]], files: List[str]) -> List[Dict[str, Any]]:
    """按规则将文件分组，生成「真实业务场景 + 对应代码位置」。"""
    result: List[Dict[str, Any]] = []
    used = set()
    for prefix, scenario, usage, risk in rules:
        matched = [f for f in files if prefix in f.replace("\\", "/")]
        if not matched:
            continue
        for f in matched:
            used.add(f)
        result.append({
            "scenario": scenario,
            "usage": usage,
            "files": sorted(matched)[:10],
            "risk": risk or ("高并发/锁竞争需关注" if "lock" in prefix.lower() or "order" in prefix.lower() else ""),
        })
    remainder = [f for f in files if f not in used]
    if remainder and result:
        result.append({
            "scenario": "服务层依赖",
            "usage": "ServiceContext、配置、连接初始化",
            "files": sorted(remainder)[:8],
            "risk": "",
        })
    elif remainder:
        result.append({
            "scenario": "业务持久化",
            "usage": "模型与持久化层",
            "files": sorted(remainder)[:10],
            "risk": "",
        })
    return result


def _scan_project_for_middleware(project_root: Path) -> Dict[str, Any]:
    """Scan Go project for MySQL, Redis, Kafka usage. Returns structured findings with scenario text."""
    mysql_files: List[str] = []
    redis_files: List[str] = []
    kafka_files: List[str] = []
    mysql_patterns = [
        "gorm.io/gorm", "gorm.io/driver/mysql", "database/sql",
        "sql.Open", "mysql.", "go-sql-driver/mysql",
    ]
    redis_patterns = [
        "redis/go-redis", "go-redis/redis", "gomodule/redigo",
        "zeromicro/go-zero/core/stores/redis", "redis.NewClient", "redis.Options",
        "xredis.Lock", "xredis.MustLock",
    ]
    kafka_patterns = [
        "sarama", "kafka-go", "segmentio/kafka-go",
        "confluent-kafka-go", "IBM/sarama",
        "kafka.NewReader", "sarama.NewConsumer",
    ]
    try:
        for f in project_root.rglob("*.go"):
            if "vendor" in str(f) or ".git" in str(f):
                continue
            try:
                text = f.read_text(encoding="utf-8", errors="ignore")
                rel = str(f.relative_to(project_root))
                for p in mysql_patterns:
                    if p in text:
                        mysql_files.append(rel)
                        break
                for p in redis_patterns:
                    if p in text:
                        redis_files.append(rel)
                        break
                for p in kafka_patterns:
                    if p in text:
                        kafka_files.append(rel)
                        break
            except Exception:
                continue
        mysql_files = sorted(set(mysql_files))[:20]
        redis_files = sorted(set(redis_files))[:20]
        kafka_files = sorted(set(kafka_files))[:20]
    except Exception:
        pass
    result: Dict[str, Any] = {"mysql": [], "redis": [], "kafka": []}
    if mysql_files:
        result["mysql"] = _match_scenario_rules(_MYSQL_SCENARIO_RULES, mysql_files)
    if redis_files:
        result["redis"] = _match_scenario_rules(_REDIS_SCENARIO_RULES, redis_files)
    if kafka_files:
        result["kafka"] = _match_scenario_rules(_KAFKA_SCENARIO_RULES, kafka_files)
    return result


def _analyze_project_scenarios(use_agent: bool = False, project_path_override: Optional[str] = None) -> Dict[str, Any]:
    """
    Analyze deployed project for MySQL/Redis/Kafka scenarios.
    use_agent=True: invoke OpenClaw to generate richer business scenarios.
    project_path_override: for testing, use this path instead of workspace.
    """
    project_root = None
    repo_name = "project"
    branch = "main"
    if project_path_override:
        p = Path(project_path_override)
        if p.exists() and p.is_dir():
            project_root = p
            repo_name = p.name
    if not project_root:
        pair = _get_deployed_project_root()
        if not pair:
            return {"ok": False, "message": "请先完成部署。", "scenarios": None}
        project_root, _ = pair
        config = get_infra_config() or {}
        github = config.get("github") or {}
        repo_name = Path((github.get("repo_url") or "").rstrip("/")).name
        if repo_name.endswith(".git"):
            repo_name = repo_name[:-4]
        branch = github.get("branch") or "main"
    config = get_infra_config() or {}
    from datetime import datetime, timezone
    analyzed_at = datetime.now(timezone.utc).isoformat()
    scanned = _scan_project_for_middleware(project_root)
    if use_agent:
        openclaw = config.get("openclaw") or {}
        base_url = (openclaw.get("gateway_url") or "http://127.0.0.1:18789").rstrip("/")
        token = (openclaw.get("hooks_token") or "").strip()
        if token:
            import httpx
            abs_path = str(project_root.resolve())
            out_path = str(PROJECT_SCENARIOS_FILE.resolve())
            message = (
                "请使用 project-scenarios-analyzer 技能，分析项目并生成业务场景。\n\n"
                f"**参数：**\n"
                f"- PROJECT_PATH: {abs_path}\n"
                f"- OUTPUT_PATH: {out_path}\n"
                f"- PROJECT_NAME: {repo_name}\n"
                f"- BRANCH: {branch}\n\n"
                "**要求：** 严格按 Skill 中的路径规则分组，输出格式必须包含 scenario、usage、files、risk。"
                " 将 JSON 写入 OUTPUT_PATH。"
            )
            try:
                with httpx.Client(timeout=60.0) as client:
                    r = client.post(
                        f"{base_url}/hooks/agent",
                        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                        json={
                            "message": message,
                            "name": "project-scenarios-analyzer",
                            "sessionKey": f"hook:project-scenarios:{hash(abs_path) % 100000:05d}",
                            "deliver": False,
                            "timeoutSeconds": 300,
                        },
                    )
                if r.status_code in (200, 202):
                    return {"ok": True, "message": "Agent 已启动，请稍后刷新查看。", "scenarios": None}
            except Exception:
                pass
    data = {
        "project_name": repo_name,
        "branch": branch,
        "analyzed_at": analyzed_at,
        "mysql": scanned.get("mysql", []),
        "redis": scanned.get("redis", []),
        "kafka": scanned.get("kafka", []),
    }
    PROJECT_SCENARIOS_FILE.parent.mkdir(parents=True, exist_ok=True)
    PROJECT_SCENARIOS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True, "message": "分析完成。", "scenarios": data}


@app.get("/api/project-scenarios")
def get_project_scenarios():
    """Get project-specific MySQL/Redis/Kafka scenarios (from last analyze)."""
    if not PROJECT_SCENARIOS_FILE.exists():
        return {"exists": False, "scenarios": None}
    try:
        data = json.loads(PROJECT_SCENARIOS_FILE.read_text(encoding="utf-8"))
        return {"exists": True, "scenarios": data}
    except Exception:
        return {"exists": False, "scenarios": None}


@app.post("/api/project-scenarios/analyze")
def analyze_project_scenarios(
    use_agent: bool = Query(False, description="Use OpenClaw agent for richer scenarios"),
    project_path: Optional[str] = Query(None, description="Override: use this path for testing (e.g. /path/to/local/project)"),
):
    """
    Analyze deployed project for MySQL/Redis/Kafka application scenarios.
    use_agent=true: invoke OpenClaw to generate customized business scenarios.
    project_path: optional override for testing with local path.
    """
    return _analyze_project_scenarios(use_agent=use_agent, project_path_override=project_path)


@app.get("/api/perftest/discover")
def discover_perftest_endpoints():
    """List all testable projects and HTTP endpoints (from gateway.yaml or preset)."""
    return _discover_perftest_endpoints()


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
MYSQL_OPS_JSON = PERF_DIR / "config" / "mysql_ops_problems.json"
REDIS_OPS_JSON = PERF_DIR / "config" / "redis_ops_problems.json"
REDIS_CASES_DIR = PERF_DIR / "redis-cases"
REDIS_OPS_LOCAL = PERF_DIR.parent / "redis-ops-learning"  # sibling to performance
KAFKA_OPS_JSON = PERF_DIR / "config" / "kafka_ops_problems.json"
KAFKA_CASES_DIR = PERF_DIR / "kafka-cases"
KAFKA_OPS_LOCAL = PERF_DIR.parent / "kafka-ops-learning"

MYSQL_OPS_PROBLEM_DIRS = {
    "01-max-connections": "problems/conn",
    "02-slow-log": "problems/slowlog",
    "03-large-transaction": "problems/largetx",
    "04-large-table": "problems/largetable",
    "05-deadlock": "problems/deadlock",
    "06-lock-wait-timeout": "problems/lockwait",
    "07-index-misuse": "problems/indexmisuse",
    "08-replication-lag": "problems/replicationlag",
    "09-cpu-io-high": "problems/highcpu",
}


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
        "actions": [{"id": "reproduce", "name": "模拟慢查询"}, {"id": "enable", "name": "开启慢日志"}, {"id": "view", "name": "查看慢日志"}],
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
    {
        "id": "08-replication-lag",
        "name": "主从复制延迟",
        "scenario": "主从架构下，主库写入激增（如大促），从库单线程 apply binlog 缓慢，Seconds_Behind_Master 持续增大。",
        "phenomenon": "从库延迟 30+ 分钟；报表数据滞后；relay log 堆积。",
        "problem": "从库默认单线程复制，大事务或高写入导致 binlog 应用跟不上主库。",
        "solution": "1. 开启 slave_parallel_workers 并行复制；2. 设置 slave_parallel_type=LOGICAL_CLOCK；3. 拆分大事务；4. 监控 Seconds_Behind_Master。",
        "actions": [{"id": "reproduce", "name": "模拟大事务"}, {"id": "monitor", "name": "监控延迟"}, {"id": "detect", "name": "检测配置"}],
    },
    {
        "id": "09-cpu-io-high",
        "name": "CPU/IO 飙高",
        "scenario": "报表系统每日凌晨执行聚合查询，由于缺少复合索引导致全表扫描，CPU 和 I/O 负载激增。",
        "phenomenon": "MySQL 服务器 CPU 使用率达 80%+；I/O 等待高；查询耗时从 1 秒飙升到 30+ 秒。",
        "problem": "SQL 查询缺少合适的索引，执行全表扫描并触发 Filesort 排序，CPU 用于大量行数据的排序和聚合计算。",
        "solution": "1. 添加复合索引: ALTER TABLE orders ADD INDEX idx_status_time (status, create_time); 2. 使用覆盖索引避免回表；3. 避免在索引列上使用函数。",
        "actions": [{"id": "reproduce", "name": "模拟全表扫描"}, {"id": "explain", "name": "分析执行计划"}, {"id": "optimize", "name": "添加索引优化"}],
    },
]


def _load_mysql_ops_from_json() -> Tuple[List[dict], Dict[str, str]]:
    """Load problems and problem_dirs from JSON. Returns (problems, problem_dirs). Uses in-code defaults if JSON missing/invalid."""
    if not MYSQL_OPS_JSON.exists():
        return MYSQL_OPS_PROBLEMS, MYSQL_OPS_PROBLEM_DIRS
    try:
        with open(MYSQL_OPS_JSON, "r", encoding="utf-8") as f:
            data = json.load(f)
        problems = data.get("problems", MYSQL_OPS_PROBLEMS)
        dirs = data.get("problem_dirs", MYSQL_OPS_PROBLEM_DIRS)
        return (problems, dirs)
    except (json.JSONDecodeError, IOError):
        return MYSQL_OPS_PROBLEMS, MYSQL_OPS_PROBLEM_DIRS


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
    """List available problems with scenario, phenomenon, problem, solution. Loads from JSON (dynamic, no restart needed)."""
    config = get_infra_config() or {}
    app_server = config.get("app_server", {})
    mysql_ops_available = bool(app_server.get("host", "").strip())
    problems_list, _ = _load_mysql_ops_from_json()
    problems = []
    for p in problems_list:
        obj = dict(p)
        scenario_from_file = _load_case_business_scenario(p["id"])
        if scenario_from_file:
            obj["business_scenario"] = scenario_from_file  # 真实业务场景段落
        problems.append(obj)
    return {
        "problems": problems,
        "mysql_ops_available": mysql_ops_available,
    }


class MysqlOpsGenerateRequest(BaseModel):
    """Request for AI-generated MySQL ops case. Only problem is required; AI generates the rest."""
    problem: str  # 问题名称，如「CPU/IO 飙高」「binlog 过大」


@app.post("/api/mysql-ops/generate")
def generate_mysql_ops_case(req: MysqlOpsGenerateRequest):
    """Trigger OpenClaw agent to generate a new MySQL ops case from the given description."""
    config = get_infra_config() or {}
    openclaw = config.get("openclaw") or {}
    base_url = (openclaw.get("gateway_url") or "http://127.0.0.1:18789").rstrip("/")
    token = (openclaw.get("hooks_token") or "").strip()
    if not token:
        raise HTTPException(
            status_code=400,
            detail="OpenClaw hooks token not configured. Add openclaw.gateway_url and openclaw.hooks_token in Infra Config.",
        )
    message = (
        "请使用 mysql-ops-case-gen 技能，根据以下【问题】生成新的 MySQL 运维案例。\n\n"
        f"问题：{req.problem}\n\n"
        "要求：请你先根据该问题，自动生成【业务场景】【现象】【技术点】，再按 Skill 步骤生成完整案例。\n"
        "步骤：1) 构思业务场景、现象、技术点 2) 创建 problems/<pkg>/ 3) 更新 cmd/main.go "
        "4) 创建 performance/mysql-cases/<id>.md 5) 更新 performance/config/mysql_ops_problems.json "
        "（read 该 JSON，在 problem_dirs 和 problems 中追加新条目后 write）6) 执行 go build 验证。"
    )
    import httpx
    try:
        with httpx.Client(timeout=30.0) as client:
            r = client.post(
                f"{base_url}/hooks/agent",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json={
                    "message": message,
                    "name": "mysql-ops-case-gen",
                    "sessionKey": f"hook:mysql-ops:{hash(req.problem) % 100000:05d}",
                    "deliver": False,
                    "timeoutSeconds": 180,
                },
            )
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to reach OpenClaw gateway: {e}",
        )
    if r.status_code == 401:
        raise HTTPException(status_code=400, detail="OpenClaw hooks token invalid or expired.")
    if r.status_code not in (200, 202):
        raise HTTPException(
            status_code=502,
            detail=f"OpenClaw returned {r.status_code}: {r.text[:200]}",
        )
    body = r.json() if r.content else {}
    return {"ok": True, "runId": body.get("runId"), "message": "Agent 已启动，稍后刷新页面查看新案例。"}


class MysqlOpsRunRequest(BaseModel):
    problem: str
    action: str


class MysqlOpsCodeSaveRequest(BaseModel):
    path: str
    content: str


class MysqlOpsConnectionLimitRequest(BaseModel):
    max_connections: int
    max_user_connections: Optional[int] = None


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


def _get_problem_dir(problem_id: str) -> str:
    _, problem_dirs = _load_mysql_ops_from_json()
    rel = problem_dirs.get(problem_id)
    if not rel:
        raise HTTPException(status_code=400, detail=f"Unknown problem id: {problem_id}")
    return rel


async def _run_remote_bash(config: dict, script: str, timeout: int = 60) -> tuple[int, str, str]:
    """Execute bash script on app server over SSH."""
    remote_cmd = f"bash -lc {shlex.quote(script)}"
    proc = await asyncio.create_subprocess_exec(
        *_ssh_args_from_config(config),
        remote_cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        raise HTTPException(status_code=500, detail=f"Remote command timeout ({timeout}s)")
    return (
        proc.returncode,
        stdout.decode("utf-8", errors="replace"),
        stderr.decode("utf-8", errors="replace"),
    )


def _mysql_connect_from_config(config: dict):
    """Create direct MySQL connection using Infra config."""
    m = config.get("mysql", {})
    return pymysql.connect(
        host=m.get("host", "127.0.0.1"),
        port=int(m.get("port", 3306)),
        user=m.get("user", "root"),
        password=m.get("password", ""),
        database=m.get("database", "jmeter_test"),
        connect_timeout=8,
        autocommit=True,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )


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


@app.get("/api/mysql-ops/connection-limits")
def get_mysql_connection_limits():
    """View current MySQL connection limits and usage."""
    config = get_infra_config()
    if not config:
        raise HTTPException(status_code=400, detail="No config saved. Save Infra config first.")
    try:
        conn = _mysql_connect_from_config(config)
        with conn.cursor() as cur:
            cur.execute("SHOW VARIABLES LIKE 'max_connections'")
            row1 = cur.fetchone() or {}
            cur.execute("SHOW VARIABLES LIKE 'max_user_connections'")
            row2 = cur.fetchone() or {}
            cur.execute("SHOW STATUS LIKE 'Threads_connected'")
            row3 = cur.fetchone() or {}
            cur.execute("SHOW STATUS LIKE 'Threads_running'")
            row4 = cur.fetchone() or {}
        conn.close()
        return {
            "max_connections": int(row1.get("Value", 0) or 0),
            "max_user_connections": int(row2.get("Value", 0) or 0),
            "threads_connected": int(row3.get("Value", 0) or 0),
            "threads_running": int(row4.get("Value", 0) or 0),
        }
    except pymysql.MySQLError as e:
        raise HTTPException(status_code=500, detail=f"MySQL error: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/mysql-ops/connection-limits")
def set_mysql_connection_limits(req: MysqlOpsConnectionLimitRequest):
    """Update MySQL max connections. Optionally update max_user_connections."""
    config = get_infra_config()
    if not config:
        raise HTTPException(status_code=400, detail="No config saved. Save Infra config first.")
    if req.max_connections < 1:
        raise HTTPException(status_code=400, detail="max_connections must be >= 1")
    if req.max_user_connections is not None and req.max_user_connections < 0:
        raise HTTPException(status_code=400, detail="max_user_connections must be >= 0 (0 means unlimited by user)")
    try:
        conn = _mysql_connect_from_config(config)
        with conn.cursor() as cur:
            cur.execute(f"SET GLOBAL max_connections = {int(req.max_connections)}")
            if req.max_user_connections is not None:
                cur.execute(f"SET GLOBAL max_user_connections = {int(req.max_user_connections)}")
        conn.close()
        return get_mysql_connection_limits()
    except pymysql.MySQLError as e:
        raise HTTPException(status_code=500, detail=f"MySQL error: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/mysql-ops/code/{problem_id}/files")
async def list_mysql_ops_code_files(problem_id: str):
    """List editable files for this problem on app server."""
    config = get_infra_config()
    if not config:
        raise HTTPException(status_code=400, detail="No config saved. Save Infra config first.")
    remote_dir = await _resolve_remote_mysql_ops_dir(config)
    problem_rel = _get_problem_dir(problem_id)
    script = f"""
set -e
cd {shlex.quote(remote_dir)}
python3 - <<'PY'
import os, json
repo = os.getcwd()
problem_rel = {json.dumps(problem_rel)}
root = os.path.normpath(os.path.join(repo, problem_rel))
if not root.startswith(repo + os.sep) or not os.path.isdir(root):
    print(json.dumps({{"files": [], "error": f"Problem directory not found: {{problem_rel}}"}}))
    raise SystemExit(0)
allow_ext = {{".go", ".md", ".sql", ".txt", ".yaml", ".yml"}}
files = []
for d, _, names in os.walk(root):
    for n in names:
        ext = os.path.splitext(n)[1].lower()
        if ext in allow_ext:
            rel = os.path.relpath(os.path.join(d, n), repo).replace("\\\\", "/")
            files.append(rel)
files.sort()
print(json.dumps({{"files": files[:200]}}))
PY
"""
    code, stdout, stderr = await _run_remote_bash(config, script, timeout=40)
    if code != 0:
        raise HTTPException(status_code=500, detail=f"List files failed: {stderr.strip() or stdout.strip()}")
    try:
        data = json.loads(stdout.strip() or "{}")
    except Exception:
        raise HTTPException(status_code=500, detail=f"Unexpected list files output: {stdout[:300]}")
    if data.get("error"):
        raise HTTPException(status_code=404, detail=data["error"])
    return data


@app.get("/api/mysql-ops/code/{problem_id}")
async def get_mysql_ops_code(problem_id: str, path: str = Query(...)):
    """Read file content from problem directory on app server."""
    config = get_infra_config()
    if not config:
        raise HTTPException(status_code=400, detail="No config saved. Save Infra config first.")
    remote_dir = await _resolve_remote_mysql_ops_dir(config)
    problem_rel = _get_problem_dir(problem_id)
    script = f"""
set -e
cd {shlex.quote(remote_dir)}
python3 - <<'PY'
import os, json, pathlib
repo = os.getcwd()
problem_rel = {json.dumps(problem_rel)}
req_path = {json.dumps(path)}
problem_root = os.path.normpath(os.path.join(repo, problem_rel))
target = os.path.normpath(os.path.join(repo, req_path))
if not target.startswith(problem_root + os.sep):
    print(json.dumps({{"error": "Path is outside problem directory"}}))
    raise SystemExit(0)
if not os.path.isfile(target):
    print(json.dumps({{"error": f"File not found: {{req_path}}"}}))
    raise SystemExit(0)
text = pathlib.Path(target).read_text(encoding="utf-8")
print(json.dumps({{"path": req_path, "content": text}}))
PY
"""
    code, stdout, stderr = await _run_remote_bash(config, script, timeout=40)
    if code != 0:
        raise HTTPException(status_code=500, detail=f"Read file failed: {stderr.strip() or stdout.strip()}")
    data = json.loads(stdout.strip() or "{}")
    if data.get("error"):
        raise HTTPException(status_code=400, detail=data["error"])
    return data


@app.post("/api/mysql-ops/code/{problem_id}")
async def save_mysql_ops_code(problem_id: str, req: MysqlOpsCodeSaveRequest):
    """Save file content back to app server under current problem directory."""
    config = get_infra_config()
    if not config:
        raise HTTPException(status_code=400, detail="No config saved. Save Infra config first.")
    remote_dir = await _resolve_remote_mysql_ops_dir(config)
    problem_rel = _get_problem_dir(problem_id)
    script = f"""
set -e
cd {shlex.quote(remote_dir)}
python3 - <<'PY'
import os, json, pathlib
repo = os.getcwd()
problem_rel = {json.dumps(problem_rel)}
req_path = {json.dumps(req.path)}
content = {json.dumps(req.content)}
problem_root = os.path.normpath(os.path.join(repo, problem_rel))
target = os.path.normpath(os.path.join(repo, req_path))
if not target.startswith(problem_root + os.sep):
    print(json.dumps({{"error": "Path is outside problem directory"}}))
    raise SystemExit(0)
os.makedirs(os.path.dirname(target), exist_ok=True)
pathlib.Path(target).write_text(content, encoding="utf-8")
print(json.dumps({{"ok": True, "path": req_path}}))
PY
"""
    code, stdout, stderr = await _run_remote_bash(config, script, timeout=60)
    if code != 0:
        raise HTTPException(status_code=500, detail=f"Save file failed: {stderr.strip() or stdout.strip()}")
    data = json.loads(stdout.strip() or "{}")
    if data.get("error"):
        raise HTTPException(status_code=400, detail=data["error"])
    return data


# --- Redis Ops ---
REDIS_PROBLEM_DIRS_FALLBACK = {
    "01-memory": "problems/memory",
    "02-clients": "problems/clients",
    "03-slowlog": "problems/slowlog",
    "04-replication": "problems/replication",
    "05-stats": "problems/stats",
}


def _load_redis_problem_dirs() -> dict:
    """Load problem_dirs from JSON. Falls back to hardcoded map."""
    if not REDIS_OPS_JSON.exists():
        return dict(REDIS_PROBLEM_DIRS_FALLBACK)
    try:
        with open(REDIS_OPS_JSON, "r", encoding="utf-8") as f:
            data = json.load(f)
        dirs = data.get("problem_dirs", {})
        return {**REDIS_PROBLEM_DIRS_FALLBACK, **dirs} if dirs else REDIS_PROBLEM_DIRS_FALLBACK
    except (json.JSONDecodeError, IOError):
        return dict(REDIS_PROBLEM_DIRS_FALLBACK)


def _get_redis_problem_dir(problem_id: str) -> str:
    dirs = _load_redis_problem_dirs()
    rel = dirs.get(problem_id)
    if not rel:
        raise HTTPException(status_code=400, detail=f"Unknown Redis problem id: {problem_id}")
    return rel


def _load_redis_ops_from_json() -> List[dict]:
    """Load Redis ops problems from JSON."""
    if not REDIS_OPS_JSON.exists():
        return []
    try:
        with open(REDIS_OPS_JSON, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("problems", [])
    except (json.JSONDecodeError, IOError):
        return []


def _redis_client_from_config(config: dict):
    """Create Redis client from Infra config."""
    import redis
    r = config.get("redis", {})
    host = r.get("host", "127.0.0.1")
    port = int(r.get("port", 6379))
    password = r.get("password", "") or None
    username = r.get("username", "") or None
    kwargs = {"host": host, "port": port, "socket_connect_timeout": 10}
    if password:
        kwargs["password"] = password
    if username:
        kwargs["username"] = username
    return redis.Redis(**kwargs)


def _run_redis_ops_command(problem: str, action: str, client) -> Tuple[bool, str]:
    """Execute Redis command for given problem+action. Returns (ok, output)."""
    output_lines = []
    try:
        if problem == "01-memory":
            if action == "info":
                info = client.info("memory")
                for k, v in sorted(info.items()):
                    output_lines.append(f"{k}: {v}")
            elif action == "bigkeys":
                cursor = 0
                sampled = 0
                max_samples = 50
                while True:
                    cursor, keys = client.scan(cursor, count=100)
                    for k in keys[:10]:
                        try:
                            mem = client.memory_usage(k)
                            if mem and mem > 1024:
                                output_lines.append(f"{k.decode() if isinstance(k, bytes) else k}: {mem} bytes")
                        except Exception:
                            pass
                        sampled += 1
                        if sampled >= max_samples:
                            break
                    if cursor == 0 or sampled >= max_samples:
                        break
                if not output_lines:
                    output_lines.append("(未发现明显大 key，或 MEMORY USAGE 不可用。可尝试 redis-cli --bigkeys)")
        elif problem == "02-clients":
            if action == "info":
                info = client.info("clients")
                for k, v in sorted(info.items()):
                    output_lines.append(f"{k}: {v}")
        elif problem == "03-slowlog":
            if action == "info":
                try:
                    cfg = client.config_get("slowlog*")
                    for k, v in sorted(cfg.items()):
                        output_lines.append(f"{k}: {v}")
                except Exception as ex:
                    output_lines.append(f"(CONFIG 可能被禁用: {ex})")
            elif action == "slowlog":
                logs = client.slowlog_get(10)
                for i, e in enumerate(logs):
                    cmd = " ".join((x.decode() if isinstance(x, bytes) else str(x) for x in (e.get("command") or [])))
                    output_lines.append(f"{i+1}. {e.get('duration', 0)}us - {cmd[:80]}...")
                if not logs:
                    output_lines.append("(无慢命令记录)")
        elif problem == "04-replication":
            if action == "info":
                info = client.info("replication")
                for k, v in sorted(info.items()):
                    output_lines.append(f"{k}: {v}")
        elif problem == "05-stats":
            if action == "info":
                for section in ["server", "clients", "memory", "stats"]:
                    try:
                        info = client.info(section)
                        output_lines.append(f"# {section}")
                        for k, v in sorted(info.items()):
                            output_lines.append(f"{k}: {v}")
                        output_lines.append("")
                    except Exception:
                        pass
            elif action == "stats":
                info = client.info("stats")
                for k, v in sorted(info.items()):
                    output_lines.append(f"{k}: {v}")
        else:
            return False, f"Unknown problem or action: {problem} / {action}"
        return True, "\n".join(output_lines)
    except Exception as e:
        return False, str(e)


def _load_redis_case_business_scenario(problem_id: str) -> str:
    """Load 业务需求场景 from redis-cases/*.md if exists. Same logic as MySQL."""
    case_file = REDIS_CASES_DIR / f"{problem_id}.md"
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
    block = block.replace("**", "").strip()
    return " ".join(block.split())


@app.get("/api/redis-ops/problems")
def list_redis_ops_problems():
    """List Redis ops problems. Loads from JSON, enriches with business_scenario from case files."""
    problems_raw = _load_redis_ops_from_json()
    config = get_infra_config() or {}
    r = config.get("redis", {})
    redis_available = bool(r.get("host", "").strip())
    problems = []
    for p in problems_raw:
        obj = dict(p)
        scenario_from_file = _load_redis_case_business_scenario(p["id"])
        if scenario_from_file:
            obj["business_scenario"] = scenario_from_file
        problems.append(obj)
    return {"problems": problems, "redis_available": redis_available}


class RedisOpsGenerateRequest(BaseModel):
    """Request for AI-generated Redis ops case."""
    problem: str  # 问题名称，如「内存碎片」「热 key」「哨兵切换」


@app.post("/api/redis-ops/generate")
def generate_redis_ops_case(req: RedisOpsGenerateRequest):
    """Trigger OpenClaw agent to generate a new Redis ops case from the given description."""
    config = get_infra_config() or {}
    openclaw = config.get("openclaw") or {}
    base_url = (openclaw.get("gateway_url") or "http://127.0.0.1:18789").rstrip("/")
    token = (openclaw.get("hooks_token") or "").strip()
    if not token:
        raise HTTPException(
            status_code=400,
            detail="OpenClaw hooks token not configured. Add openclaw.gateway_url and openclaw.hooks_token in Infra Config.",
        )
    message = (
        "请使用 redis-ops-case-gen 技能，根据以下【问题】生成新的 Redis 运维案例。\n\n"
        f"问题：{req.problem}\n\n"
        "要求：请你先根据该问题，自动生成【业务场景】【现象】【技术点】，再按 Skill 步骤生成完整案例。\n"
        "步骤：1) 构思业务场景、现象、技术点 2) 创建 problems/<pkg>/ 3) 更新 cmd/main.go "
        "4) 创建 performance/redis-cases/<id>.md 5) 更新 performance/config/redis_ops_problems.json "
        "（在 problem_dirs 和 problems 中追加新条目）6) 执行 go build 验证。"
    )
    import httpx
    try:
        with httpx.Client(timeout=30.0) as client:
            r = client.post(
                f"{base_url}/hooks/agent",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json={
                    "message": message,
                    "name": "redis-ops-case-gen",
                    "sessionKey": f"hook:redis-ops:{hash(req.problem) % 100000:05d}",
                    "deliver": False,
                    "timeoutSeconds": 180,
                },
            )
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to reach OpenClaw gateway: {e}",
        )
    if r.status_code == 401:
        raise HTTPException(status_code=400, detail="OpenClaw hooks token invalid or expired.")
    if r.status_code not in (200, 202):
        raise HTTPException(
            status_code=502,
            detail=f"OpenClaw returned {r.status_code}: {r.text[:200]}",
        )
    body = r.json() if r.content else {}
    return {"ok": True, "runId": body.get("runId"), "message": "Agent 已启动，稍后刷新页面查看新案例。"}


class RedisOpsRunRequest(BaseModel):
    problem: str
    action: str


def _run_redis_ops_via_go(problem: str, action: str, config: dict) -> Tuple[bool, str, str]:
    """Run via redis-ops-learning Go binary when available. Returns (ok, stdout, stderr)."""
    if not REDIS_OPS_LOCAL.exists() or not REDIS_OPS_LOCAL.is_dir():
        return False, "", ""
    r = config.get("redis", {})
    host = r.get("host", "127.0.0.1")
    port = int(r.get("port", 6379))
    addr = f"{host}:{port}"
    env = {**os.environ, "REDIS_ADDR": addr}
    if r.get("password"):
        env["REDIS_PASSWORD"] = str(r.get("password", ""))
    if r.get("username"):
        env["REDIS_USERNAME"] = str(r.get("username", ""))
    try:
        proc = subprocess.run(
            ["go", "run", "./cmd", "run", problem, action],
            cwd=str(REDIS_OPS_LOCAL),
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
        )
        out = proc.stdout or ""
        err = proc.stderr or ""
        return proc.returncode == 0, out, err
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False, "", ""


@app.post("/api/redis-ops/run")
def run_redis_ops(req: RedisOpsRunRequest):
    """Run Redis ops action (execute Redis commands via Infra config)."""
    config = get_infra_config()
    if not config:
        raise HTTPException(status_code=400, detail="No config saved. Save Infra config with Redis first.")
    try:
        # Prefer Go binary when redis-ops-learning exists (supports 06+ and all problems)
        go_ok, go_out, go_err = _run_redis_ops_via_go(req.problem, req.action, config)
        if go_ok:
            return {"ok": True, "stdout": go_out, "stderr": go_err or ""}
        if go_out or go_err:
            # Go ran but failed - return its output
            return {"ok": False, "stdout": go_out, "stderr": go_err or ""}
        # Go not installed or not runnable - fall back to Python for built-in problems (01-05)
        client = _redis_client_from_config(config)
        ok, output = _run_redis_ops_command(req.problem, req.action, client)
        client.close()
        return {"ok": ok, "stdout": output, "stderr": ""}
    except Exception as e:
        return {"ok": False, "stdout": "", "stderr": str(e)}


@app.get("/api/redis-ops/case/{problem_id}")
def get_redis_ops_case(problem_id: str):
    """Return markdown content for Redis ops case. Read from local redis-cases/."""
    _get_redis_problem_dir(problem_id)  # validate
    case_path = REDIS_CASES_DIR / f"{problem_id}.md"
    if not case_path.exists():
        raise HTTPException(status_code=404, detail=f"Case not found: {problem_id}")
    try:
        return {"content": case_path.read_text(encoding="utf-8")}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _resolve_redis_ops_local_dir() -> Path:
    """Return redis-ops-learning root if it exists."""
    if not REDIS_OPS_LOCAL.exists() or not REDIS_OPS_LOCAL.is_dir():
        raise HTTPException(
            status_code=400,
            detail=f"redis-ops-learning not found at {REDIS_OPS_LOCAL}. Place it as sibling to performance/.",
        )
    return REDIS_OPS_LOCAL


@app.get("/api/redis-ops/code/{problem_id}/files")
def list_redis_ops_code_files(problem_id: str):
    """List editable files for this Redis problem. Uses local redis-ops-learning."""
    root_dir = _resolve_redis_ops_local_dir()
    problem_rel = _get_redis_problem_dir(problem_id)
    root = (root_dir / problem_rel).resolve()
    repo = root_dir.resolve()
    if not root.is_dir() or not str(root).startswith(str(repo) + os.sep):
        raise HTTPException(status_code=404, detail=f"Problem directory not found: {problem_rel}")
    allow_ext = {".go", ".md", ".txt", ".yaml", ".yml"}
    files = []
    for d, _, names in os.walk(root):
        for n in names:
            ext = os.path.splitext(n)[1].lower()
            if ext in allow_ext:
                full = Path(d) / n
                rel = str(full.relative_to(repo)).replace("\\", "/")
                files.append(rel)
    files.sort()
    return {"files": files[:200]}


@app.get("/api/redis-ops/code/{problem_id}")
def get_redis_ops_code(problem_id: str, path: str = Query(...)):
    """Read file content from redis-ops-learning problem directory."""
    root_dir = _resolve_redis_ops_local_dir()
    problem_rel = _get_redis_problem_dir(problem_id)
    problem_root = (root_dir / problem_rel).resolve()
    target = (root_dir / path).resolve()
    try:
        target.relative_to(problem_root)
    except ValueError:
        raise HTTPException(status_code=400, detail="Path is outside problem directory")
    if not target.is_file():
        raise HTTPException(status_code=404, detail=f"File not found: {path}")
    try:
        return {"path": path, "content": target.read_text(encoding="utf-8")}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class RedisOpsCodeSaveRequest(BaseModel):
    path: str
    content: str


@app.post("/api/redis-ops/code/{problem_id}")
def save_redis_ops_code(problem_id: str, req: RedisOpsCodeSaveRequest):
    """Save file content back to redis-ops-learning."""
    root_dir = _resolve_redis_ops_local_dir()
    problem_rel = _get_redis_problem_dir(problem_id)
    problem_root = (root_dir / problem_rel).resolve()
    target = (root_dir / req.path).resolve()
    try:
        target.relative_to(problem_root)
    except ValueError:
        raise HTTPException(status_code=400, detail="Path is outside problem directory")
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(req.content, encoding="utf-8")
        return {"ok": True, "path": req.path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- Kafka Ops ---


def _get_kafka_problem_dir(problem_id: str) -> str:
    """Return problem dir from kafka_ops_problems.json problem_dirs."""
    if not KAFKA_OPS_JSON.exists():
        raise HTTPException(status_code=404, detail=f"Problem not found: {problem_id}")
    with open(KAFKA_OPS_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)
    dirs = data.get("problem_dirs", {})
    if problem_id not in dirs:
        raise HTTPException(status_code=404, detail=f"Problem not found: {problem_id}")
    return dirs[problem_id]


def _run_kafka_ops_via_go(problem: str, action: str, config: dict) -> Tuple[bool, str, str]:
    """Run via kafka-ops-learning Go binary. Returns (ok, stdout, stderr)."""
    if not KAFKA_OPS_LOCAL.exists() or not KAFKA_OPS_LOCAL.is_dir():
        return False, "", ""
    k = config.get("kafka", {})
    brokers = k.get("brokers", "127.0.0.1:9092")
    if isinstance(brokers, list):
        brokers = ",".join(brokers)
    env = {**os.environ, "KAFKA_BROKERS": brokers or "127.0.0.1:9092"}
    if k.get("username"):
        env["KAFKA_USERNAME"] = str(k.get("username", ""))
    if k.get("password"):
        env["KAFKA_PASSWORD"] = str(k.get("password", ""))
    try:
        proc = subprocess.run(
            ["go", "run", "./cmd", "run", problem, action],
            cwd=str(KAFKA_OPS_LOCAL),
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
        )
        return proc.returncode == 0, proc.stdout or "", proc.stderr or ""
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False, "", ""


def _load_kafka_ops_from_json() -> list:
    """Load Kafka ops problems from JSON."""
    if not KAFKA_OPS_JSON.exists():
        return []
    try:
        with open(KAFKA_OPS_JSON, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("problems", [])
    except (json.JSONDecodeError, IOError):
        return []


def _load_kafka_case_business_scenario(problem_id: str) -> str:
    """Load 业务需求场景 from kafka-cases/*.md if exists."""
    case_file = KAFKA_CASES_DIR / f"{problem_id}.md"
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
    block = block.replace("**", "").strip()
    return " ".join(block.split())


@app.get("/api/kafka-ops/problems")
def list_kafka_ops_problems():
    """List Kafka ops problems. Loads from JSON, enriches with business_scenario from case files."""
    problems_raw = _load_kafka_ops_from_json()
    config = get_infra_config() or {}
    k = config.get("kafka", {})
    brokers = k.get("brokers", "")
    if isinstance(brokers, list):
        brokers = ",".join(brokers) if brokers else ""
    kafka_available = bool((brokers or "").strip())
    problems = []
    for p in problems_raw:
        obj = dict(p)
        scenario_from_file = _load_kafka_case_business_scenario(p["id"])
        if scenario_from_file:
            obj["business_scenario"] = scenario_from_file
        problems.append(obj)
    return {"problems": problems, "kafka_available": kafka_available}


@app.get("/api/kafka-ops/case/{problem_id}")
def get_kafka_ops_case(problem_id: str):
    """Return markdown content for Kafka ops case. Read from local kafka-cases/."""
    _get_kafka_problem_dir(problem_id)  # validate
    case_path = KAFKA_CASES_DIR / f"{problem_id}.md"
    if not case_path.exists():
        raise HTTPException(status_code=404, detail=f"Case not found: {problem_id}")
    try:
        return {"content": case_path.read_text(encoding="utf-8")}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class KafkaOpsGenerateRequest(BaseModel):
    """Request for AI-generated Kafka ops case."""
    problem: str  # 问题名称，如「消息重复消费」「分区不均衡」


@app.post("/api/kafka-ops/generate")
def generate_kafka_ops_case(req: KafkaOpsGenerateRequest):
    """Trigger OpenClaw agent to generate a new Kafka ops case from the given description."""
    config = get_infra_config() or {}
    openclaw = config.get("openclaw") or {}
    base_url = (openclaw.get("gateway_url") or "http://127.0.0.1:18789").rstrip("/")
    token = (openclaw.get("hooks_token") or "").strip()
    if not token:
        raise HTTPException(
            status_code=400,
            detail="OpenClaw hooks token not configured. Add openclaw.gateway_url and openclaw.hooks_token in Infra Config.",
        )
    message = (
        "请使用 kafka-ops-case-gen 技能，根据以下【问题】生成新的 Kafka 运维案例。\n\n"
        f"问题：{req.problem}\n\n"
        "要求：请你先根据该问题，自动生成【业务场景】【现象】【技术点】，再按 Skill 步骤生成完整案例。\n"
        "步骤：1) 构思业务场景、现象、技术点 2) 创建 problems/<pkg>/ 3) 更新 cmd/main.go "
        "4) 创建 performance/kafka-cases/<id>.md 5) 更新 performance/config/kafka_ops_problems.json "
        "（在 problem_dirs 和 problems 中追加新条目）6) 执行 go build 验证。"
    )
    import httpx
    try:
        with httpx.Client(timeout=30.0) as client:
            r = client.post(
                f"{base_url}/hooks/agent",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json={
                    "message": message,
                    "name": "kafka-ops-case-gen",
                    "sessionKey": f"hook:kafka-ops:{hash(req.problem) % 100000:05d}",
                    "deliver": False,
                    "timeoutSeconds": 180,
                },
            )
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to reach OpenClaw gateway: {e}",
        )
    if r.status_code == 401:
        raise HTTPException(status_code=400, detail="OpenClaw hooks token invalid or expired.")
    if r.status_code not in (200, 202):
        raise HTTPException(
            status_code=502,
            detail=f"OpenClaw returned {r.status_code}: {r.text[:200]}",
        )
    body = r.json() if r.content else {}
    return {"ok": True, "runId": body.get("runId"), "message": "Agent 已启动，稍后刷新页面查看新案例。"}


class KafkaOpsRunRequest(BaseModel):
    problem: str
    action: str


@app.post("/api/kafka-ops/run")
def run_kafka_ops(req: KafkaOpsRunRequest):
    """Run Kafka ops action via kafka-ops-learning."""
    config = get_infra_config()
    if not config:
        raise HTTPException(status_code=400, detail="No config saved. Save Infra config with Kafka first.")
    go_ok, go_out, go_err = _run_kafka_ops_via_go(req.problem, req.action, config)
    if not (KAFKA_OPS_LOCAL.exists() and KAFKA_OPS_LOCAL.is_dir()):
        return {
            "ok": False,
            "stdout": "",
            "stderr": "kafka-ops-learning 未找到。请将项目放在 performance 同级目录。",
        }
    out = (go_out or "") + ("\n" + go_err if go_err else "")
    return {"ok": go_ok, "stdout": go_out, "stderr": go_err or ""}


def _resolve_kafka_ops_local_dir() -> Path:
    """Return kafka-ops-learning root if it exists."""
    if not KAFKA_OPS_LOCAL.exists() or not KAFKA_OPS_LOCAL.is_dir():
        raise HTTPException(
            status_code=400,
            detail=f"kafka-ops-learning not found at {KAFKA_OPS_LOCAL}. Place it as sibling to performance/.",
        )
    return KAFKA_OPS_LOCAL


@app.get("/api/kafka-ops/code/{problem_id}/files")
def list_kafka_ops_code_files(problem_id: str):
    """List editable files for this Kafka problem."""
    root_dir = _resolve_kafka_ops_local_dir()
    problem_rel = _get_kafka_problem_dir(problem_id)
    root = (root_dir / problem_rel).resolve()
    repo = root_dir.resolve()
    if not root.is_dir() or not str(root).startswith(str(repo) + os.sep):
        raise HTTPException(status_code=404, detail=f"Problem directory not found: {problem_rel}")
    allow_ext = {".go", ".md", ".txt", ".yaml", ".yml"}
    files = []
    for d, _, names in os.walk(root):
        for n in names:
            ext = os.path.splitext(n)[1].lower()
            if ext in allow_ext:
                full = Path(d) / n
                rel = str(full.relative_to(repo)).replace("\\", "/")
                files.append(rel)
    files.sort()
    return {"files": files[:200]}


@app.get("/api/kafka-ops/code/{problem_id}")
def get_kafka_ops_code(problem_id: str, path: str = Query(...)):
    """Read file content from kafka-ops-learning problem directory."""
    root_dir = _resolve_kafka_ops_local_dir()
    problem_rel = _get_kafka_problem_dir(problem_id)
    problem_root = (root_dir / problem_rel).resolve()
    target = (root_dir / path).resolve()
    try:
        target.relative_to(problem_root)
    except ValueError:
        raise HTTPException(status_code=400, detail="Path is outside problem directory")
    if not target.is_file():
        raise HTTPException(status_code=404, detail=f"File not found: {path}")
    try:
        return {"path": path, "content": target.read_text(encoding="utf-8")}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class KafkaOpsCodeSaveRequest(BaseModel):
    path: str
    content: str


@app.post("/api/kafka-ops/code/{problem_id}")
def save_kafka_ops_code(problem_id: str, req: KafkaOpsCodeSaveRequest):
    """Save file content back to kafka-ops-learning."""
    root_dir = _resolve_kafka_ops_local_dir()
    problem_rel = _get_kafka_problem_dir(problem_id)
    problem_root = (root_dir / problem_rel).resolve()
    target = (root_dir / req.path).resolve()
    try:
        target.relative_to(problem_root)
    except ValueError:
        raise HTTPException(status_code=400, detail="Path is outside problem directory")
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(req.content, encoding="utf-8")
        return {"ok": True, "path": req.path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Serve frontend last so /api routes take precedence
_frontend = Path(__file__).parent.parent / "frontend"
if _frontend.exists():
    app.mount("/", StaticFiles(directory=str(_frontend), html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
