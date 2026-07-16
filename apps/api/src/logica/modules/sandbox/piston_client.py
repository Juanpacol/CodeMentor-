"""Thin client for a self-hosted Piston instance (§4.2): code from a student
never runs in the API process — always in this isolated, resource-limited
container, reached only over HTTP."""

from dataclasses import dataclass

import httpx

from logica.config import get_settings

_MAX_OUTPUT_CHARS = 4000
_TRUNCATION_SUFFIX = "\n... (salida truncada)"


class SandboxUnavailableError(Exception):
    pass


@dataclass(frozen=True)
class SandboxResult:
    stdout: str
    stderr: str
    exit_code: int | None
    timed_out: bool


def _truncate(text: str) -> str:
    if len(text) <= _MAX_OUTPUT_CHARS:
        return text
    return text[:_MAX_OUTPUT_CHARS] + _TRUNCATION_SUFFIX


async def run_code(
    language: str,
    version: str,
    source: str,
    stdin: str = "",
    run_timeout_ms: int = 5000,
) -> SandboxResult:
    settings = get_settings()
    payload = {
        "language": language,
        "version": version,
        "files": [{"name": "main", "content": source}],
        "stdin": stdin,
        "run_timeout": run_timeout_ms,
        "compile_timeout": 10_000,
        "compile_memory_limit": -1,
        "run_memory_limit": -1,
    }

    try:
        async with httpx.AsyncClient(timeout=(run_timeout_ms / 1000) + 15) as client:
            response = await client.post(f"{settings.sandbox_url}/api/v2/execute", json=payload)
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPError as exc:
        raise SandboxUnavailableError(f"Sandbox no disponible: {exc}") from exc

    compile_result = data.get("compile")
    if compile_result is not None and compile_result.get("code") not in (0, None):
        return SandboxResult(
            stdout=_truncate(compile_result.get("stdout", "")),
            stderr=_truncate(compile_result.get("stderr", "")),
            exit_code=compile_result.get("code"),
            timed_out=False,
        )

    run_result = data.get("run", {})
    # Piston kills the process on timeout: no exit code, but a signal is set.
    timed_out = run_result.get("code") is None and run_result.get("signal") is not None

    return SandboxResult(
        stdout=_truncate(run_result.get("stdout", "")),
        stderr=_truncate(run_result.get("stderr", "")),
        exit_code=run_result.get("code"),
        timed_out=timed_out,
    )
