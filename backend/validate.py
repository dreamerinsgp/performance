"""Validate Redis, MySQL, Kafka connectivity."""
import socket
import subprocess
import sys
from typing import Tuple

import redis
import pymysql


def check_tcp(host: str, port: int, timeout: float = 3.0) -> Tuple[bool, str]:
    """Check if TCP port is reachable."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        if result == 0:
            return True, "OK"
        return False, f"Connection refused or timeout (port {port})"
    except socket.gaierror as e:
        return False, f"DNS/host resolution failed: {e}"
    except Exception as e:
        return False, str(e)


def check_redis(
    host: str, port: int, password: str = "", username: str = ""
) -> Tuple[bool, str]:
    """Check Redis connection and PING. username for Redis 6+ ACL (e.g. Aliyun 普通账号)."""
    try:
        kwargs = {"host": host, "port": port, "socket_connect_timeout": 5}
        if password:
            kwargs["password"] = password
        if username:
            kwargs["username"] = username
        r = redis.Redis(**kwargs)
        r.ping()
        return True, "PONG"
    except redis.ConnectionError as e:
        return False, str(e)
    except Exception as e:
        return False, str(e)


def ensure_mysql_database(host: str, port: int, user: str, password: str, database: str) -> Tuple[bool, str]:
    """Create database if not exists. Requires user to have CREATE privilege."""
    import re
    if not database or not re.match(r"^[a-zA-Z0-9_]+$", database):
        return False, "Database name is empty or invalid (only alphanumeric and underscore)"
    try:
        conn = pymysql.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            connect_timeout=5,
        )
        with conn.cursor() as cur:
            cur.execute(
                f"CREATE DATABASE IF NOT EXISTS `{database}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
        conn.close()
        return True, "OK"
    except pymysql.Error as e:
        return False, str(e)


def run_mysql_init_sql(
    host: str, port: int, user: str, password: str, database: str, init_sql: str
) -> Tuple[bool, str]:
    """Execute user-provided init SQL (CREATE TABLE etc.) in the database."""
    if not init_sql or not init_sql.strip():
        return True, "OK"
    # 可忽略的错误码：表/库已存在视为成功
    IGNORABLE_ERRORS = (1050,)  # Table 'xxx' already exists
    try:
        conn = pymysql.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
            connect_timeout=5,
        )
        with conn.cursor() as cur:
            for stmt in _split_sql_statements(init_sql):
                if stmt.strip():
                    try:
                        cur.execute(stmt)
                    except pymysql.Error as e:
                        if e.args[0] in IGNORABLE_ERRORS:
                            continue  # 表已存在，忽略
                        raise
        conn.commit()
        conn.close()
        return True, "OK"
    except pymysql.Error as e:
        return False, str(e)


def _split_sql_statements(sql: str) -> list:
    """Split SQL by semicolon, preserving strings and comments."""
    stmts = []
    current = []
    in_string = None
    i = 0
    sql = sql + "\n"
    while i < len(sql):
        c = sql[i]
        if in_string:
            if c == "\\" and i + 1 < len(sql):
                current.append(c + sql[i + 1])
                i += 2
                continue
            if c == in_string:
                in_string = None
            current.append(c)
            i += 1
            continue
        if c in ("'", '"', "`"):
            in_string = c
            current.append(c)
            i += 1
            continue
        if c == ";":
            stmts.append("".join(current))
            current = []
            i += 1
            continue
        current.append(c)
        i += 1
    if current:
        stmts.append("".join(current))
    return stmts


def check_mysql(
    host: str,
    port: int,
    user: str,
    password: str,
    database: str,
    init_sql: str = "",
) -> Tuple[bool, str]:
    """Check MySQL connection. Auto-creates database and runs init SQL if provided."""
    ok, msg = ensure_mysql_database(host, port, user, password, database)
    if not ok:
        return False, f"Create DB failed: {msg}"
    try:
        conn = pymysql.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
            connect_timeout=5,
        )
        conn.close()
        ok2, msg2 = run_mysql_init_sql(host, port, user, password, database, init_sql)
        if not ok2:
            return False, f"Init SQL failed: {msg2}"
        return True, "Connected"
    except pymysql.Error as e:
        return False, str(e)
    except Exception as e:
        return False, str(e)


def check_kafka(brokers: list) -> Tuple[bool, str]:
    """Check Kafka brokers - use TCP check as fallback (no kafka-python dep)."""
    if not brokers:
        return False, "No brokers configured"
    # Parse host:port from brokers
    for b in brokers:
        if ":" in b:
            parts = b.split(":")
            host, port = parts[0], int(parts[1])
        else:
            host, port = b, 9092
        ok, msg = check_tcp(host, port)
        if ok:
            return True, f"Broker {host}:{port} reachable"
    return False, "No Kafka broker reachable"


def validate_all(config: dict) -> dict:
    """Validate all services and return status dict."""
    results = {}

    # Redis
    r = config.get("redis", {})
    ok, msg = check_redis(
        r.get("host", "127.0.0.1"),
        r.get("port", 6379),
        r.get("password", ""),
        r.get("username", ""),
    )
    results["redis"] = {"ok": ok, "message": msg}

    # MySQL
    m = config.get("mysql", {})
    init_sql = config.get("mysql_init_sql", "") or m.get("init_sql", "")
    ok, msg = check_mysql(
        m.get("host", "127.0.0.1"),
        m.get("port", 3306),
        m.get("user", "root"),
        m.get("password", ""),
        m.get("database", "dexs"),
        init_sql,
    )
    results["mysql"] = {"ok": ok, "message": msg}

    # Kafka
    k = config.get("kafka", {})
    brokers = k.get("brokers", ["127.0.0.1:9092"])
    if isinstance(brokers, str):
        brokers = [b.strip() for b in brokers.split(",")]
    ok, msg = check_kafka(brokers)
    results["kafka"] = {"ok": ok, "message": msg}

    # Gateway (HTTP)
    gw = config.get("gateway_url", "")
    if gw:
        ok, msg = check_tcp(
            gw.replace("http://", "").replace("https://", "").split("/")[0].split(":")[0],
            int(gw.split(":")[-1].rstrip("/")) if ":" in gw.split("//")[-1] else 80,
        )
        results["gateway"] = {"ok": ok, "message": msg}
    else:
        results["gateway"] = {"ok": None, "message": "Not configured"}

    return results
