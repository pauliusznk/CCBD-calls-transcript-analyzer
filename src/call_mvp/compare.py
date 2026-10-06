"""Palyginimas: tas pats ASR -> LLM darbas paprastai (po vieną skambutį) ir su Spark (keli vienu metu).

ASR ir LLM vykdomi per OpenAI suderinamą API, todėl Spark local[N] pagreitina darbą siųsdamas
N skambučių užklausas vienu metu. Rezultatai netalpinami (cache): kiekvienas būdas iš naujo
siunčia garsą ir tekstą. API atsakymai gali šiek tiek skirtis, todėl ASR tekstai lyginami panašumo procentu.
"""

from __future__ import annotations

import csv
import difflib
import json
import os
import platform
import sys
import time
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path

from call_mvp import pipeline
from call_mvp.config import Settings, load_settings

CPU_COUNT = os.cpu_count() or 1
RESULT_COLUMNS = ["call_id", "audio_filename", "duration_s", "asr_seconds", "llm_seconds", "asr_word_count", "topic",
                  "resolution", "customer_dissatisfied", "quote_found", "resolution_quote", "summary_lt", "error"]
TIMING_COLUMNS = ["method", "calls", "audio_min", "workers", "spark_start_s", "total_s",
                  "total_min", "asr_sum_s", "llm_sum_s", "speedup_vs_python", "errors"]


def spark_workers(master: str) -> int:
    inner = master.removeprefix("local[").removesuffix("]")
    if master == "local":
        return 1
    if inner == "*":
        return CPU_COUNT
    if master.startswith("local[") and inner.isdigit():
        return int(inner)
    raise ValueError(f"Palaikomas tik vietinis Spark režimas local[N]: {master!r}")


def run_python(calls: list[dict], settings: Settings) -> tuple[list[dict], dict]:
    start = time.perf_counter()
    rows = []
    for i, call in enumerate(calls, start=1):
        row = pipeline.process_call(call, settings)
        rows.append(row)
        print(f"  python {i}/{len(calls)} {call['audio_filename']}: ASR {row['asr_seconds']} s, "
              f"LLM {row['llm_seconds']} s{' KLAIDA ' + row['error'] if row['error'] else ''}", flush=True)
    total = time.perf_counter() - start
    return rows, {"method": "python", "workers": 1, "spark_start_s": None, "total_s": total}


def run_spark(calls: list[dict], settings: Settings, master: str) -> tuple[list[dict], dict]:
    from pyspark.sql import SparkSession

    workers = spark_workers(master)
    os.environ.setdefault("PYSPARK_PYTHON", sys.executable)
    start = time.perf_counter()
    spark = SparkSession.builder.master(master).appName("call_mvp").config("spark.ui.enabled", "false").getOrCreate()
    spark.sparkContext.setLogLevel("ERROR")
    spark_start = time.perf_counter() - start
    try:
        # Viena Spark užduotis = vienas skambutis; laisvas darbininkas pasiima kitą skambutį.
        # Nustatymai (modeliai ir promptas) nusiunčiami darbininkams kartu su užduotimi.
        rows = (spark.sparkContext.parallelize(calls, len(calls))
                .map(lambda call: pipeline.process_call(call, settings))
                .collect())
    finally:
        spark.stop()
    total = time.perf_counter() - start
    return rows, {"method": f"spark_local_{workers}", "workers": workers, "spark_start_s": spark_start,
                  "total_s": total}


def write_results(rows: list[dict], out_dir: Path, name: str) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = sorted(rows, key=lambda r: r["call_id"])
    with (out_dir / f"{name}.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=RESULT_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    with (out_dir / f"{name}.jsonl").open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def text_similarity(a: str | None, b: str | None) -> float | None:
    """Žodžių sekų panašumas 0–1 (1 = identiški tekstai)."""
    if a is None or b is None:
        return None
    return difflib.SequenceMatcher(None, a.split(), b.split(), autojunk=False).ratio()


def agreement(base: list[dict], other: list[dict]) -> dict:
    """Kiek skambučių abu būdai davė tą patį ASR tekstą ir tas pačias LLM išvadas."""
    other_by_id = {r["call_id"]: r for r in other}
    pairs = [(a, other_by_id[a["call_id"]]) for a in base if a["call_id"] in other_by_id]

    def same(field):
        return sum(1 for a, b in pairs if a.get(field) is not None and a.get(field) == b.get(field))

    similarities = [s for a, b in pairs if (s := text_similarity(a.get("transcript"), b.get("transcript"))) is not None]
    return {"calls": len(pairs), "asr_text_same": same("transcript"),
            "asr_text_similarity_pct": round(100 * sum(similarities) / len(similarities), 2) if similarities else None,
            "topic_same": same("topic"), "resolution_same": same("resolution"),
            "dissatisfied_same": same("customer_dissatisfied")}


def timing_row(timing: dict, rows: list[dict], python_total: float | None) -> dict:
    return {
        "method": timing["method"], "calls": len(rows),
        "audio_min": round(sum(r["duration_s"] for r in rows) / 60, 2),
        "workers": timing["workers"],
        "spark_start_s": round(timing["spark_start_s"], 2) if timing["spark_start_s"] is not None else None,
        "total_s": round(timing["total_s"], 2), "total_min": round(timing["total_s"] / 60, 2),
        "asr_sum_s": round(sum(r["asr_seconds"] or 0 for r in rows), 2),
        "llm_sum_s": round(sum(r["llm_seconds"] or 0 for r in rows), 2),
        "speedup_vs_python": round(python_total / timing["total_s"], 2) if python_total else None,
        "errors": sum(1 for r in rows if r["error"]),
    }


def per_call_table(results: dict[str, list[dict]]) -> list[dict]:
    """Viena eilutė skambučiui: kiekvieno būdo laikai ir išvados šalia."""
    names = list(results)
    by_method = {name: {r["call_id"]: r for r in rows} for name, rows in results.items()}
    table = []
    for call_id in sorted(by_method[names[0]]):
        first = by_method[names[0]][call_id]
        row = {"call_id": call_id, "audio_filename": first["audio_filename"], "duration_s": first["duration_s"]}
        for name in names:
            r = by_method[name].get(call_id, {})
            for field in ("asr_seconds", "llm_seconds", "topic", "resolution", "customer_dissatisfied"):
                row[f"{name}_{field}"] = r.get(field)
        if len(names) > 1:
            similarity = text_similarity(first.get("transcript"), by_method[names[1]].get(call_id, {}).get("transcript"))
            row["asr_text_similarity_pct"] = round(100 * similarity, 2) if similarity is not None else None
        table.append(row)
    return table


def _label(method: str) -> str:
    return "Paprastas Python" if method == "python" else f"Spark local[{method.removeprefix('spark_local_')}]"


def plot_times(timings: list[dict], path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    colors = {"python": "#2a78d6"}
    labels = [_label(t["method"]) for t in timings]
    minutes = [t["total_min"] for t in timings]
    fig, ax = plt.subplots(figsize=(7.5, 1.2 + 0.7 * len(timings)), dpi=150)
    fig.patch.set_facecolor("#fcfcfb")
    ax.set_facecolor("#fcfcfb")
    bars = ax.barh(labels, minutes, height=0.5,
                   color=[colors.get(t["method"], "#eb6834") for t in timings])
    for bar, value in zip(bars, minutes):
        ax.text(bar.get_width(), bar.get_y() + bar.get_height() / 2, f"  {value:.1f} min".replace(".", ","),
                va="center", color="#0b0b0b", fontsize=10)
    ax.invert_yaxis()
    ax.set_xlim(0, max(minutes) * 1.2)
    ax.set_xlabel("Minutės (mažiau – geriau)", color="#52514e")
    calls, audio = timings[0]["calls"], timings[0]["audio_min"]
    ax.set_title(f"{calls} skambučių ({audio:.0f} min garso): ASR + OpenAI analizė", loc="left", color="#0b0b0b")
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color("#c3c2b7")
    ax.tick_params(colors="#52514e")
    ax.grid(axis="x", color="#e1e0d9", linewidth=0.8)
    ax.set_axisbelow(True)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, facecolor="#fcfcfb")
    plt.close(fig)


def _version(package: str) -> str:
    try:
        return metadata.version(package)
    except metadata.PackageNotFoundError:
        return "nenustatyta"


def run_compare(inputs: Path, data_root: Path, output: Path, reports: Path, modes: list[str],
                master: str, limit: int | None = None, config_dir: Path = Path("config")) -> dict:
    settings = load_settings(config_dir)
    calls = pipeline.load_calls(inputs / "manifest.csv", data_root, limit)
    print(f"Skambučiai: {len(calls)}, garso: {sum(c['duration_s'] for c in calls) / 60:.1f} min", flush=True)
    print(f"ASR: {settings.asr_model}, LLM: {settings.llm_model}, promptas: {settings.prompt_sha256}", flush=True)

    results: dict[str, list[dict]] = {}
    timings: list[dict] = []
    for mode in modes:
        print(f"[{mode}] pradžia", flush=True)
        rows, timing = run_python(calls, settings) if mode == "python" else run_spark(calls, settings, master)
        results[timing["method"]] = rows
        write_results(rows, output, timing["method"])
        python_total = next((t["total_s"] for t in timings if t["method"] == "python"), None)
        timings.append(timing_row(timing, rows, python_total))
        print(f"[{mode}] baigta per {timing['total_s'] / 60:.1f} min", flush=True)

    reports.mkdir(parents=True, exist_ok=True)
    with (reports / "laikai.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=TIMING_COLUMNS)
        writer.writeheader()
        writer.writerows(timings)
    table = per_call_table(results)
    with (reports / "skambuciai.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(table[0]))
        writer.writeheader()
        writer.writerows(table)
    plot_times(timings, reports / "laikai.png")

    names = list(results)
    report = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "timings": timings,
        "agreement": agreement(results[names[0]], results[names[1]]) if len(names) > 1 else None,
        "environment": {
            "os": platform.platform(), "python": platform.python_version(), "cpu_cores": CPU_COUNT,
            "api_base_url": os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            "asr_model": f"{settings.asr_model} (API, {settings.asr_chunk_seconds} s WAV dalys)",
            "llm_model": settings.llm_model,
            "llm_temperature": settings.llm_temperature,
            "prompt_file": str(config_dir / "prompts.toml"),
            "prompt_sha256": settings.prompt_sha256,
            "packages": {p: _version(p) for p in ("pyspark", "openai", "openai-agents")},
            "spark_master": master if "spark" in modes else None,
        },
    }
    (reports / "palyginimas.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report
