"""Read resolved Compose configuration without printing secrets; run local browser checks."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def settings() -> tuple[str, str, str]:
    result = subprocess.run(
        ["docker", "compose", "config", "--format", "json"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    services = json.loads(result.stdout)["services"]
    api = f"http://localhost:{services['backend']['ports'][0]['published']}"
    frontend = f"http://localhost:{services['frontend']['ports'][0]['published']}"
    password = services["backend"]["environment"]["DEMO_PASSWORD"]
    return api, frontend, password


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("info", "health", "e2e"))
    args = parser.parse_args()

    api, frontend, password = settings()
    if args.command == "info":
        print(f"Website: {frontend}\nAPI: {api}")
        return

    for url in (f"{api}/health", frontend):
        with urllib.request.urlopen(url, timeout=10) as response:
            if response.status != 200:
                raise SystemExit(f"Not ready: {url} ({response.status})")

    if args.command == "health":
        print("API and website are ready.")
        return

    env = dict(os.environ, API_URL=api, BASE_URL=frontend)
    for role, email in (
        ("ADMIN", "admin@example.com"),
        ("CUSTOMER", "customer@example.com"),
        ("GUEST", "guest@example.com"),
        ("WAITER", "waiter.rustaveli@example.com"),
    ):
        env[role + "_EMAIL"] = email
        env[role + "_PASSWORD"] = password

    result = subprocess.run([sys.executable, "-m", "pytest", "e2e", "-v"], cwd=ROOT, env=env)
    raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
