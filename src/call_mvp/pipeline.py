"""Skambučių sąrašas ir vieno skambučio apdorojimas: ASR -> LLM."""

from __future__ import annotations

import csv
import time
from pathlib import Path

from call_mvp import asr
from call_mvp.config import Settings


def load_calls(manifest: Path, data_root: Path, limit: int | None = None) -> list[dict]:
    """Skambučiai iš manifest.csv. Su --limit imami trumpiausi; apdorojami nuo ilgiausio."""
    with manifest.open(encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    calls = [{
        "call_id": row["call_id"],
        "audio_filename": Path(row["relative_path"]).name,
        "audio_path": str((data_root / row["relative_path"]).resolve()),
        "duration_s": float(row["duration_s"]),
    } for row in rows]
    missing = [c["audio_path"] for c in calls if not Path(c["audio_path"]).is_file()]
    if missing:
        raise FileNotFoundError(f"Nerasta {len(missing)} WAV, pvz. {missing[0]}. Patikrink --data-root.")
    calls.sort(key=lambda c: c["duration_s"])
    if limit:
        calls = calls[:limit]
    # Ilgiausi pirmi: lygiagrečiai dirbant, ilgas įrašas nepalieka vieno darbininko pabaigoje.
    return sorted(calls, key=lambda c: c["duration_s"], reverse=True)


def process_call(call: dict, settings: Settings) -> dict:
    """Vienas skambutis: ASR tekstas ir OpenAI analizė. Klaida užrašoma, kiti skambučiai tęsiami."""
    from call_mvp import llm

    row = {k: call[k] for k in ("call_id", "audio_filename", "duration_s")}
    row.update(asr_seconds=None, llm_seconds=None, asr_word_count=None, transcript=None, error=None)
    try:
        start = time.perf_counter()
        transcript = asr.transcribe(call["audio_path"], settings.asr_model, settings.asr_chunk_seconds)
        row.update(asr_seconds=round(time.perf_counter() - start, 2), asr_word_count=len(transcript.split()),
                   transcript=transcript)
        start = time.perf_counter()
        row.update(llm.analyze(transcript, settings))
        row["llm_seconds"] = round(time.perf_counter() - start, 2)
    except Exception as exc:  # noqa: BLE001 - vieno skambučio klaida neturi sustabdyti viso palyginimo
        row["error"] = f"{type(exc).__name__}: {exc}"[:500]
    return row
