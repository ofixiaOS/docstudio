from __future__ import annotations

import asyncio
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import requests
from mcp import Client, StdioServerParameters


BACKEND_DIR = Path(__file__).resolve().parent.parent


def unused_local_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def test_mcp_stdio_process_reaches_the_local_gamma_api(test_data_dir: Path) -> None:
    port = unused_local_port()
    api_url = f"http://127.0.0.1:{port}"
    environment = {
        **os.environ,
        "GAMMA_API_URL": api_url,
        "GEMINI_API_KEY": "",
        "GAMMA_DATA_DIR": str(test_data_dir),
    }
    backend = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", str(port)],
        cwd=BACKEND_DIR,
        env=environment,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        for _ in range(50):
            try:
                if requests.get(f"{api_url}/api/health", timeout=0.2).ok:
                    break
            except requests.RequestException:
                time.sleep(0.1)
        else:
            stderr = backend.stderr.read() if backend.stderr else ""
            raise AssertionError(f"El backend de integración no inició: {stderr}")

        created = requests.post(
            f"{api_url}/api/projects/quick-create",
            json={"title": "Proyecto MCP STDIO"},
            timeout=5,
        )
        created.raise_for_status()
        project_id = created.json()["project_id"]

        async def exercise_stdio() -> None:
            parameters = StdioServerParameters(
                command=sys.executable,
                args=[str(BACKEND_DIR / "scripts" / "gamma_mcp.py")],
                env=environment,
                cwd=BACKEND_DIR,
            )
            async with Client(parameters, read_timeout_seconds=10) as client:
                tools = await client.list_tools()
                assert "get_project_context" in {tool.name for tool in tools.tools}
                result = await client.call_tool("get_project_context", {"project_id": project_id})
                assert result.structured_content["project"]["id"] == project_id
                assert result.structured_content["constraints"]["completion_is_audit_controlled"] is True

        asyncio.run(exercise_stdio())
    finally:
        backend.terminate()
        try:
            backend.wait(timeout=5)
        except subprocess.TimeoutExpired:
            backend.kill()
            backend.wait(timeout=5)
