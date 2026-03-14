# DEX Ops Dashboard

一站式 GUI：配置 MySQL/Redis/Kafka 与项目服务器 → 部署项目到服务器 → 监控各机器 → 性能压测。

## Quick Start

**Option A: ./run.sh** (tries venv, falls back to Docker)
```bash
cd /home/ubuntu/dex_full/performance
./run.sh
```

**Option B: Manual venv** (if `python3-venv` is installed)
```bash
cd /home/ubuntu/dex_full/performance
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

**Option C: Docker** (no venv needed)
```bash
docker compose up -d
```

If `python3-venv` is missing, run: `sudo apt install python3.12-venv`

Open http://localhost:8000 in your browser.

## Features

1. **Infra Config** - Enter Redis, MySQL, Kafka IP:port and GitHub repo URL. Save and validate connectivity.
2. **Deploy** - One-click deploy that generates `*-perf.yaml` and runs the deploy script.
3. **Monitor** - View CPU/内存、项目进程数、监听端口、HTTP 健康检查（需配置 gateway_url）。
4. **Perf Test** - Run Locust load test on core APIs (get_candlestick, index_trending, etc.).

## Project Structure

```
performance/
├── backend/           # FastAPI API
│   ├── main.py
│   ├── config_store.py
│   ├── config_generator.py
│   └── validate.py
├── frontend/          # Static HTML + JS
│   ├── index.html
│   └── app.js
├── config/            # Saved infra.json (gitignored)
│   └── infra.json.example
├── scripts/
│   ├── deploy.sh      # Deploy DEX with perf config
│   └── validate_infra.sh
├── ci/
│   └── deploy-webhook.yaml.example  # GitHub Action 示例，tag 触发部署
├── perftest/
│   └── locustfile.py  # Locust scenarios
├── requirements.txt
└── docker-compose.yml
```

## 流程概览

1. **配置**：填写 MySQL、Redis、Kafka、项目服务器的 IP 与端口，以及 GitHub 仓库
2. **部署**：从 GitHub 克隆 → 编译 → 生成配置（项目连接 MySQL/Redis/Kafka）→ rsync 到项目服务器
3. **监控**：通过 SSH 获取项目服务器的 CPU、内存
4. **压测**：对 Gateway 接口做负载测试
5. **MySQL Ops**：运行 mysql-ops-learning 工具，模拟连接数、慢查询、大事务等问题（需同级目录有 mysql-ops-learning 项目及 Go 环境）
6. **MySQL 案例**：`mysql-cases/` 目录存放各问题的真实业务场景设计，便于理解技术概念对业务的影响

## 配置说明

- **MySQL/Redis/Kafka**：各中间件所在机器的 IP 和端口。MySQL 会在 Validate 或 Deploy 时**自动建库**；**初始化 SQL** 可填写建表等 DDL，会按顺序执行
- **项目服务器**：部署目标的 IP、SSH 端口、用户、部署路径。**免密登录**：首次部署时在 Deploy 页填写目标服务器的 SSH 密码，会自动执行 ssh-copy-id 完成配置；或手动运行 `ssh-copy-id user@host`。自动配置需安装 `sudo apt install sshpass`
- **GitHub 仓库**：项目代码地址、分支、子路径（若项目在子目录）。**Private 仓库**：需填写 GitHub Token (PAT)，创建路径：Settings → Developer settings → Personal access tokens，勾选 repo 权限
- **Gateway 地址**：性能压测目标，通常为 `http://项目服务器IP:8081`

## 部署步骤

Deploy 会执行：

1. 克隆/拉取 GitHub 仓库
2. 按配置生成 Redis/MySQL/Kafka 的 yaml，写入 `apps/*/etc/`
3. `make build` 编译
4. rsync `build/` 到项目服务器
5. 在项目服务器上生成 `start.sh` 启动脚本
6. 自动执行 `start.sh` 启动/重启服务

## CI/CD 集成

借鉴现有 `dex-gateway-test` / Jenkins Webhook 模式：**Tag 触发 → 调用 Webhook → 自动部署**。

### Webhook 端点

```
POST /api/deploy/webhook?token=xxx
# 或 Header: X-Deploy-Token: xxx
```

若设置环境变量 `PERF_DEPLOY_TOKEN`，请求必须携带对应 token 才会执行部署。

### GitHub Action 示例

1. 将 `performance/ci/deploy-webhook.yaml.example` 复制到项目 `.github/workflows/deploy-perf.yaml`
2. 在仓库 Settings → Secrets 添加 `DASHBOARD_URL`（如 `https://your-dashboard:8000`）、`DEPLOY_TOKEN`（与 Dashboard 的 `PERF_DEPLOY_TOKEN` 一致）
3. 推送 tag 触发部署，例如：`git tag dex-deploy/v1.0.0 && git push origin dex-deploy/v1.0.0`

### 与现有 CI 对比

| 现有 (dex-gateway-test)     | Dashboard 模式                    |
|-----------------------------|------------------------------------|
| Tag → Build Docker → Push Hub → Jenkins Webhook | Tag → Dashboard Webhook → deploy.sh |
| 每服务独立镜像、K8s 部署     | 单体二进制 rsync + start.sh       |

## Performance Test

类 JMeter，可配置：

- **待测接口**：每行 `路径` 或 `路径,方法,权重`，支持 GET/POST/PUT/DELETE。例：`/api/items,POST,1` 或 `/api/items,GET,2`
- **线程数**：虚拟用户数
- **启动时间**：多少秒内启动全部线程
- **执行时长**：压测持续时间

目标地址取自 Infra 的 `gateway_url`。Requires `pip install locust`。

## Monitoring (Full Metrics)

For CPU, memory, disk read/write per machine:

1. Install [Node Exporter](https://github.com/prometheus/node_exporter) on each server
2. Set up Prometheus to scrape them
3. Add Prometheus URL to the dashboard (future enhancement) or use Grafana

The current Monitor tab shows the machine list from config; integrate Prometheus for detailed metrics.
