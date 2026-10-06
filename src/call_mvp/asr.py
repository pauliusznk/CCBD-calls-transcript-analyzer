"""Kalbos atpažinimas (ASR) per OpenAI suderinamą API: garso įrašas -> tekstas.

Modelis ir dalies ilgis – config/models.toml, adresas ir raktas – .env (OPENAI_BASE_URL,
OPENAI_API_KEY). Serveris neatpažįsta ilgų įrašų, todėl įrašas siunčiamas WAV dalimis,
o tekstai sujungiami.
"""

from __future__ import annotations

import io
import wave
from pathlib import Path

from openai import OpenAI


def wav_chunks(path: str | Path, seconds: int = 300) -> list[bytes]:
    """Supjausto WAV į ne ilgesnes nei `seconds` dalis, kiekviena – atskiras WAV failas."""
    chunks = []
    with wave.open(str(path), "rb") as src:
        params = src.getparams()
        step = src.getframerate() * seconds
        while frames := src.readframes(step):
            buffer = io.BytesIO()
            with wave.open(buffer, "wb") as out:
                out.setparams(params)
                out.writeframes(frames)
            chunks.append(buffer.getvalue())
    return chunks


def transcribe(path: str | Path, model: str, chunk_seconds: int) -> str:
    client = OpenAI(timeout=300)
    parts = []
    for i, chunk in enumerate(wav_chunks(path, chunk_seconds)):
        text = client.audio.transcriptions.create(model=model, file=(f"part{i}.wav", chunk), response_format="text")
        parts.append(str(text).strip())
    return " ".join(part for part in parts if part)
