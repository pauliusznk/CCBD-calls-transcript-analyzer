"""LLM analizė: vienas OpenAI Agents SDK agentas (Agent + Runner) su Pydantic atsakymo schema.

Modelis – config/models.toml, instrukcijos ir temos – config/prompts.toml,
adresas ir raktas – .env (OPENAI_BASE_URL, OPENAI_API_KEY).
"""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Literal

from agents import Agent, ModelSettings, Runner, set_tracing_disabled
from pydantic import BaseModel, Field, create_model

from call_mvp.config import Settings


@lru_cache
def analysis_model(topics: tuple[str, ...]) -> type[BaseModel]:
    """Atsakymo schema; temų sąrašas imamas iš prompts.toml."""
    return create_model(
        "CallAnalysis",
        summary_lt=(str, Field(description="2–3 sakinių pokalbio santrauka lietuviškai")),
        topic=(Literal[topics], Field(description="Main reason for the call")),
        resolution=(Literal["resolved", "unresolved", "unknown"], ...),
        resolution_quote=(str | None, Field(
            description="Exact, unchanged English quote from the transcript supporting resolution; null if unknown")),
        customer_dissatisfied=(Literal["yes", "no", "unknown"], ...),
    )


def _normalize(text: str) -> str:
    """Mažosios raidės, be skyrybos ir papildomų tarpų: ASR tekste skyrybos gali nebūti."""
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", text.lower())).strip()


def quote_found(quote: str | None, transcript: str) -> bool | None:
    """Ar modelio citata tikrai yra transkripte (skyryba ir didžiosios raidės nesvarbu). None, jei citatos nėra."""
    if not quote:
        return None
    return _normalize(quote) in _normalize(transcript)


def analyze(transcript: str, settings: Settings) -> dict:
    set_tracing_disabled(True)
    agent = Agent(
        name="call_analyst",
        instructions=settings.instructions,
        model=settings.llm_model,
        model_settings=ModelSettings(temperature=settings.llm_temperature),
        output_type=analysis_model(settings.topics),
    )
    analysis = Runner.run_sync(agent, transcript).final_output.model_dump()
    analysis["quote_found"] = quote_found(analysis["resolution_quote"], transcript)
    return analysis
