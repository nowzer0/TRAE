from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROLES = ("A", "B", "C")
JUDGE_ROLE = "judge"
ALL_ROLES = ROLES + (JUDGE_ROLE,)


@dataclass
class AgentConfig:
    provider: str = "gemini"
    model: str = "gemini-2.5-flash-lite"
    api_key_env: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def resolved_api_key(self) -> str | None:
        if self.api_key_env:
            return os.getenv(self.api_key_env)
        return os.getenv(default_api_key_env(self.provider))


@dataclass
class RuntimeConfig:
    agents: dict[str, AgentConfig]
    temperature: float = 0.2
    top_p: float = 1.0
    max_tokens: int = 3000
    timeout_ms: int | None = 60000
    dry_run: bool = False

    def agent(self, role: str | None) -> AgentConfig:
        role = role or ROLES[0]
        return self.agents.get(role) or self.agents[ROLES[0]]


@dataclass
class Thresholds:
    tau_rel: float = 0.90
    tau_lab: float = 0.90
    min_votes: int = 3


# Default high-confidence routing settings used by the release pipeline.
DEFAULT_THRESHOLDS = Thresholds(tau_rel=0.90, tau_lab=0.90, min_votes=3)


def default_api_key_env(provider: str) -> str:
    provider = provider.lower()
    return {
        "openai": "OPENAI_API_KEY",
        "gemini": "GEMINI_API_KEY",
        "claude": "ANTHROPIC_API_KEY",
        "deepseek": "DEEPSEEK_API_KEY",
        "grok": "XAI_API_KEY",
    }.get(provider, "")


def build_single_model_agents(provider: str, model: str) -> dict[str, AgentConfig]:
    return {
        role: AgentConfig(
            provider=provider,
            model=model,
            api_key_env=default_api_key_env(provider),
        )
        for role in ALL_ROLES
    }


def load_agent_config(path: str | Path) -> dict[str, AgentConfig]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if "agents" in raw:
        raw = raw["agents"]

    agents: dict[str, AgentConfig] = {}
    for role in ALL_ROLES:
        data = dict(raw.get(role, {}))
        provider = data.pop("provider", "gemini")
        model = data.pop("model", "gemini-2.5-flash-lite")
        api_key_env = data.pop("api_key_env", default_api_key_env(provider))
        if "api_key" in data:
            raise ValueError(
                "Do not put API keys in config files; use api_key_env and an environment variable."
            )
        agents[role] = AgentConfig(
            provider=provider,
            model=model,
            api_key_env=api_key_env,
            extra=data,
        )
    return agents


def build_runtime_config(
    *,
    provider: str = "gemini",
    model: str = "gemini-2.5-flash-lite",
    agent_config: str | None = None,
    temperature: float = 0.2,
    top_p: float = 1.0,
    max_tokens: int = 3000,
    timeout_ms: int | None = 60000,
    dry_run: bool = False,
) -> RuntimeConfig:
    if agent_config:
        agents = load_agent_config(agent_config)
    else:
        agents = build_single_model_agents(provider, model)

    return RuntimeConfig(
        agents=agents,
        temperature=temperature,
        top_p=top_p,
        max_tokens=max_tokens,
        timeout_ms=timeout_ms,
        dry_run=dry_run,
    )
