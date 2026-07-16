"""Requires a real Piston container with the python package installed:
    make up-sandbox
    make sandbox-install-python
Opt-in via `pytest -m sandbox` — excluded from the default `make test` run
because it depends on infrastructure beyond the test database/redis."""

import pytest

from logica.modules.sandbox.piston_client import run_code

pytestmark = pytest.mark.sandbox


async def test_correct_code_runs_successfully() -> None:
    result = await run_code("python", "3.10.0", "print(2 + 2)")
    assert result.exit_code == 0
    assert result.stdout.strip() == "4"
    assert result.timed_out is False


async def test_runtime_error_is_reported_without_crashing_the_client() -> None:
    result = await run_code("python", "3.10.0", "raise ValueError('boom')")
    assert result.exit_code != 0
    assert "ValueError" in result.stderr


async def test_infinite_loop_times_out() -> None:
    result = await run_code("python", "3.10.0", "while True:\n    pass", run_timeout_ms=1500)
    assert result.timed_out is True


async def test_network_access_is_blocked_or_fails() -> None:
    source = (
        "import socket\n"
        "s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)\n"
        "s.settimeout(2)\n"
        "s.connect(('example.com', 80))\n"
        "print('connected')\n"
    )
    result = await run_code("python", "3.10.0", source, run_timeout_ms=4000)
    # Piston's sandbox denies network access; either the connect() call
    # raises (non-zero exit, no "connected" in stdout) or the process is
    # killed for exceeding its timeout — both count as "blocked".
    assert "connected" not in result.stdout
