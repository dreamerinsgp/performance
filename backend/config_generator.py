"""Generate *-perf.yaml config files from infra config."""


def generate_perf_yaml(config: dict) -> dict:
    """
    Generate perf config content for each service.
    Returns dict of filename -> content.
    """
    r = config.get("redis", {})
    m = config.get("mysql", {})
    k = config.get("kafka", {})
    redis_host = r.get("host", "127.0.0.1")
    redis_port = r.get("port", 6379)
    redis_addr = f"{redis_host}:{redis_port}" if ":" not in str(redis_host) else redis_host
    mysql_host = m.get("host", "127.0.0.1")
    mysql_port = m.get("port", 3306)
    kafka_brokers = k.get("brokers", ["127.0.0.1:9092"])
    if isinstance(kafka_brokers, str):
        kafka_brokers = [b.strip() for b in kafka_brokers.split(",")]

    files = {}

    # Consumer
    files["consumer-perf.yaml"] = f"""# Auto-generated perf config for consumer
Mysql:
  User: {m.get('user', 'root')}
  Password: "{m.get('password', '')}"
  Host: {mysql_host}
  Port: {mysql_port}
  DBname: {m.get('database', 'dexs')}

Redis:
  Host: {redis_addr}
  Pass: {r.get('password', '')}
  Type: node
  Key: bizRedis
  PingTimeout: 10s

KqSolTrades:
  Brokers:
""" + "\n".join(f"    - {b}" for b in kafka_brokers) + "\n"

    # Market
    files["market-perf.yaml"] = f"""# Auto-generated perf config for market
Mysql:
  Master:
    Path: {mysql_host}
    Port: {mysql_port}
    Dbname: {m.get('database', 'dexs')}
    Username: {m.get('user', 'root')}
    Password: "{m.get('password', '')}"
    MaxIdleConns: 20
    MaxOpenConns: 50

redis:
  Host: {redis_addr}
  Type: node
  Pass: {r.get('password', '')}
  Tls: false
  Key: "10"
  PingTimeout: 10s
"""

    # Dataflow
    files["dataflow-perf.yaml"] = f"""# Auto-generated perf config for dataflow
Mysql:
  Master:
    Path: {mysql_host}
    Port: {mysql_port}
    Dbname: {m.get('database', 'dexs')}
    Username: {m.get('user', 'root')}
    Password: "{m.get('password', '')}"
    MaxIdleConns: 20
    MaxOpenConns: 50

redis:
  Host: {redis_addr}
  Type: node
  Pass: {r.get('password', '')}
  Tls: false
  Key: "10"
  PingTimeout: 10s

KqSol:
  Brokers:
""" + "\n".join(f"    - {b}" for b in kafka_brokers) + "\n"

    # Trade
    files["trade-perf.yaml"] = f"""# Auto-generated perf config for trade
Mysql:
  User: {m.get('user', 'root')}
  Password: "{m.get('password', '')}"
  Host: {mysql_host}
  Port: {mysql_port}
  DBname: {m.get('database', 'dexs')}

Redis:
  Host: {redis_addr}
  Pass: {r.get('password', '')}
  Type: node
  Key: bizRedis
  PingTimeout: 10s
"""

    return files
