"""`python -m filaments_mcp` over stdio: see the openspec mcp-tools spec."""

import os
import subprocess
import sys

import pytest
from conftest import TOKEN
from fastmcp import Client
from fastmcp.client.transports import StdioTransport


def server_env(**overrides: str) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith("FILAMENTS_")}
    env.update(overrides)
    return env


@pytest.mark.anyio
async def test_stdio_server_lists_six_tools():
    # A real subprocess: if anything but protocol messages reached stdout, the client
    # would fail to parse them and this call would error.
    transport = StdioTransport(
        command=sys.executable,
        args=["-m", "filaments_mcp"],
        env=server_env(FILAMENTS_API_TOKEN=TOKEN, FILAMENTS_API_URL="http://127.0.0.1:9/api"),
    )
    async with Client(transport) as client:
        tools = await client.list_tools()

    assert len(tools) == 6


def test_missing_token_exits_naming_the_setting():
    result = subprocess.run(
        [sys.executable, "-m", "filaments_mcp"],
        env=server_env(),
        capture_output=True,
        text=True,
        timeout=60,
        stdin=subprocess.DEVNULL,
    )

    assert result.returncode == 1
    assert "FILAMENTS_API_TOKEN" in result.stderr
    assert result.stdout == ""
