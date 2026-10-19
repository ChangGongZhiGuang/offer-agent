"""配置加载: 环境变量 + roles.yaml 默认值 -> Settings。"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import yaml
from dotenv import load_dotenv

_DEFAULT_ROLES_PATH = Path(__file__).with_name("roles.yaml")


@dataclass(frozen=True)
class Settings:
    # 模型端点
    base_url: str
    api_key: str
    model_name: str
    embed_model_name: str
    # 有界性参数
    token_budget: int
    max_turns: int
    max_replans: int
    max_tool_calls_per_turn: int
    single_output_cap: int
    snip_after_turns: int
    # 全局规则
    global_rules: list[dict]


def _int_env_or(default: int, key: str) -> int:
    raw = os.getenv(key)
    if raw is None or raw.strip() == "":
        return default
    return int(raw)


def load_settings(roles_path: Path | None = None) -> Settings:
    load_dotenv()  # 读取 .env (若存在)
    roles_path = roles_path or _DEFAULT_ROLES_PATH
    data = yaml.safe_load(roles_path.read_text(encoding="utf-8"))
    bounds = data["bounds"]

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY is required (set it in .env or environment)")

    return Settings(
        base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        api_key=api_key,
        model_name=os.getenv("MODEL_NAME", "gpt-4o-mini"),
        embed_model_name=os.getenv("EMBED_MODEL_NAME", "text-embedding-3-small"),
        token_budget=_int_env_or(bounds["token_budget"], "TOKEN_BUDGET"),
        max_turns=_int_env_or(bounds["max_turns"], "MAX_TURNS"),
        max_replans=bounds["max_replans"],
        max_tool_calls_per_turn=bounds["max_tool_calls_per_turn"],
        single_output_cap=bounds["single_output_cap"],
        snip_after_turns=bounds["snip_after_turns"],
        global_rules=data.get("global_rules") or [],
    )
