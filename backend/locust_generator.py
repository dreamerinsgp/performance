"""Generate Locust test file from perftest config."""
import json
from typing import List


def _body_to_py(body_str: str) -> str:
    """Convert JSON body string to Python dict literal for generated code."""
    try:
        return repr(json.loads(body_str))
    except (json.JSONDecodeError, TypeError):
        return "{}"


def _default_post_body(path: str) -> str:
    """Default JSON body for POST requests."""
    if "/items" in path and "items/" not in path:
        return '{"name": "perf-test", "description": "load test"}'
    return "{}"


def generate_locustfile(endpoints: List[dict]) -> str:
    """
    Generate locustfile.py content from endpoint config.
    endpoints: [{"path": "/api/health", "method": "GET", "weight": 1}, ...]
    POST/PUT can have optional "body" field (JSON string).
    """
    if not endpoints:
        return _fallback_locustfile()

    task_lines = []
    for i, ep in enumerate(endpoints):
        path = (ep.get("path") or "/").replace('"', '\\"')
        method = (ep.get("method") or "GET").upper()
        weight = max(1, int(ep.get("weight", 1)))
        name = (ep.get("name") or path).replace('"', '\\"')
        task_name = f"task_{i}"

        if method == "POST":
            body_str = ep.get("body") or _default_post_body(path)
            body_py = _body_to_py(body_str)
            task_lines.append(f'''
    @task({weight})
    def {task_name}(self):
        """{method} {path}"""
        self.client.post("{path}", json={body_py}, name="{name}")
''')
        elif method == "PUT":
            body_str = ep.get("body") or "{}"
            body_py = _body_to_py(body_str)
            task_lines.append(f'''
    @task({weight})
    def {task_name}(self):
        """{method} {path}"""
        self.client.put("{path}", json={body_py}, name="{name}")
''')
        elif method == "DELETE":
            task_lines.append(f'''
    @task({weight})
    def {task_name}(self):
        """{method} {path}"""
        self.client.delete("{path}", name="{name}")
''')
        else:
            task_lines.append(f'''
    @task({weight})
    def {task_name}(self):
        """{method} {path}"""
        self.client.get("{path}", name="{name}")
''')

    tasks = "\n".join(task_lines)
    return f'''"""
Auto-generated Locust file from perftest config.
"""
from locust import HttpUser, task, between


class PerfTestUser(HttpUser):
    wait_time = between(0.5, 2)
{tasks}
'''


def _fallback_locustfile() -> str:
    """Default locustfile when no endpoints configured."""
    return '''"""
Default Locust file - add endpoints in Perf Test config.
"""
from locust import HttpUser, task, between


class PerfTestUser(HttpUser):
    wait_time = between(0.5, 2)

    @task(1)
    def health(self):
        self.client.get("/api/health", name="/api/health")
'''
