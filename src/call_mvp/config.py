"""Nustatymai iš config/models.toml (modeliai) ir config/prompts.toml (LLM promptas ir temos).

Nustatymai nuskaitomi vieną kartą ir perduodami kiekvienam skambučiui, todėl paprastas būdas
ir Spark darbininkai naudoja lygiai tuos pačius modelius ir promptą.
"""

from __future__ import annotations

import hashlib
import tomllib
from dataclasses import dataclass
from pathlib import Path

DEFAULT_CONFIG_DIR = Path("config")


@dataclass(frozen=True)
class Settings:
    asr_model: str
    asr_chunk_seconds: int
    llm_model: str
    llm_temperature: float | None
    instructions: str
    topics: tuple[str, ...]

    @property
    def prompt_sha256(self) -> str:
        return hashlib.sha256(self.instructions.encode("utf-8")).hexdigest()[:12]


def _read(path: Path) -> dict:
    if not path.is_file():
        raise FileNotFoundError(f"Nerastas nustatymų failas {path}. Paleisk iš projekto šaknies arba nurodyk --config.")
    with path.open("rb") as fh:
        return tomllib.load(fh)


def load_settings(config_dir: Path = DEFAULT_CONFIG_DIR) -> Settings:
    models = _read(config_dir / "models.toml")
    prompts = _read(config_dir / "prompts.toml")
    try:
        analysis = prompts["call_analysis"]
        settings = Settings(
            asr_model=models["asr"]["model"],
            asr_chunk_seconds=int(models["asr"].get("chunk_seconds", 300)),
            llm_model=models["llm"]["model"],
            llm_temperature=models["llm"].get("temperature"),
            instructions=analysis["instructions"].strip(),
            topics=tuple(analysis["topics"]),
        )
    except KeyError as exc:
        raise ValueError(f"Nustatymų faile {config_dir} trūksta lauko {exc}") from exc
    if not settings.instructions or not settings.topics:
        raise ValueError("prompts.toml: instructions ir topics negali būti tušti")
    return settings
