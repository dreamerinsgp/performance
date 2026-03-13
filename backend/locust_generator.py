"""Generate Locust test file from perftest config."""
from typing import List


def generate_locustfile(endpoints: List[dict]) -> str:
    """
    Generate locustfile.py content from endpoint config.
    endpoints: [{"path": "/api/health", "method": "GET", "weight": 1}, ...]
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
            task_lines.append(f'''
    @task({weight})
    def {task_name}(self):
        """{method} {path}"""
        self.client.post("{path}", name="{name}")
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
