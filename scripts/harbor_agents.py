"""Harbor agent adapters that reuse the trial image's pre-installed CLIs.

The DrugDiscoveryBench image ships pinned, working agent CLIs (claude-code, codex,
gemini-cli, installed via npm). Harbor's stock installed-agent adapters
unconditionally reinstall the CLI at every trial's agent-setup step, and those
upstream installers fail inside the trial container: claude-code's native
(Bun) ``claude.ai/install.sh`` build and codex/gemini's ``nvm install`` paths
are both SIGKILLed (exit 137) — independent of memory, network, or the egress
proxy. The reinstall also undermines the whole point of pinning the image,
since it pulls "latest" instead of the version baked into the image.

These subclasses skip the reinstall when a working CLI is already present —
the same ``already_installed`` pattern Harbor's own ``openhands_sdk`` adapter
uses — so trials run against the image's pinned CLIs. If no CLI is present
(or an explicit ``version`` kwarg is set), they fall back to Harbor's normal
install.

Wired via ``harbor run --agent-import-path harbor_agents:PreinstalledClaudeCode``
(see ``scripts/run_eval.sh``, which puts this file's directory on PYTHONPATH).
Works with the stock pip/uv-installed Harbor — no fork, no upstream change.
"""

from __future__ import annotations

from harbor.agents.installed.claude_code import ClaudeCode
from harbor.agents.installed.codex import Codex
from harbor.agents.installed.gemini_cli import GeminiCli


async def _reuse_preinstalled(agent, environment) -> bool:
    """Skip install if a working CLI is already on PATH.

    Returns True (and records the detected version) when the agent's version
    command succeeds, signalling the caller to skip Harbor's install step.
    Honors an explicitly pinned ``version`` by declining to skip.
    """
    if agent._version is not None:
        return False
    version_cmd = agent.get_version_command()
    if not version_cmd:
        return False
    probe = await environment.exec(command=version_cmd)
    if probe.return_code == 0 and (probe.stdout or "").strip():
        agent._version = agent.parse_version(probe.stdout)
        return True
    return False


class PreinstalledClaudeCode(ClaudeCode):
    async def install(self, environment) -> None:
        if await _reuse_preinstalled(self, environment):
            return
        await super().install(environment)


class PreinstalledCodex(Codex):
    async def install(self, environment) -> None:
        if await _reuse_preinstalled(self, environment):
            return
        await super().install(environment)


class PreinstalledGeminiCli(GeminiCli):
    async def install(self, environment) -> None:
        if await _reuse_preinstalled(self, environment):
            return
        await super().install(environment)
