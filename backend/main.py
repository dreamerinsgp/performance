"""
DEX Ops Dashboard API - Config, Deploy, Monitor, Perf Test.
"""
import asyncio
import json
import os
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


# Serve frontend last so /api routes take precedence
_frontend = Path(__file__).parent.parent / "frontend"
if _frontend.exists():
    app.mount("/", StaticFiles(directory=str(_frontend), html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
