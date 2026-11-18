"""Load scanner YAML from the repository config directory."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "config" / "scanner.yaml"


def load_config(path: Path | None = None) -> dict:
    src = Path(path) if path else DEFAULT_CONFIG
    with src.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Config must be a mapping: {src}")
    if "risk" not in data or "sessions" not in data:
        raise ValueError("Config is missing risk or sessions")
    # Hard-coded: nothing in the file is allowed to turn live trading on.
    if data.get("live_trading") or data.get("risk", {}).get("live_trading"):
        raise ValueError("live_trading is not a supported setting")
    return data


@lru_cache(maxsize=1)
def default_config() -> dict:
    return load_config(DEFAULT_CONFIG)
