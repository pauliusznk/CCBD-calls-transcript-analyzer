"""Komanda: python -m call_mvp.cli compare

Visus skambučius apdoroja ASR -> OpenAI paprastai ir su Spark, tada palygina laiką ir rezultatus.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import find_dotenv, load_dotenv


def cmd_compare(args) -> int:
    if not os.environ.get("OPENAI_API_KEY"):
        print("Trūksta OPENAI_API_KEY: įrašyk jį į .env projekto šaknyje (žr. .env.example).", file=sys.stderr)
        return 2
    from call_mvp.compare import run_compare

    report = run_compare(args.inputs, args.data_root, args.output, args.reports, args.modes, args.master, args.limit,
                         args.config)
    print(f"\n{'būdas':<18}{'skambučiai':>11}{'min':>8}{'pagreitis':>11}{'klaidos':>9}")
    for t in report["timings"]:
        speedup = f"{t['speedup_vs_python']:.2f}x" if t["speedup_vs_python"] else "-"
        print(f"{t['method']:<18}{t['calls']:>11}{t['total_min']:>8.1f}{speedup:>11}{t['errors']:>9}")
    if report["agreement"]:
        a = report["agreement"]
        print(f"\nSutapo iš {a['calls']}: ASR tekstas {a['asr_text_same']}, tema {a['topic_same']}, "
              f"išspręsta {a['resolution_same']}, nepasitenkinimas {a['dissatisfied_same']}")
    print(f"Rezultatai: {args.output}, ataskaita: {args.reports}")
    return 1 if any(t["errors"] for t in report["timings"]) else 0


def main(argv: list[str] | None = None) -> int:
    load_dotenv(find_dotenv(usecwd=True), override=False)  # .env neperrašo jau nustatytų aplinkos kintamųjų
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(errors="replace")  # lietuviškos raidės nenutraukia darbo senesnėje konsolėje
    parser = argparse.ArgumentParser(prog="python -m call_mvp.cli",
                                     description="2 dalis: ASR + OpenAI analizė paprastai ir su Spark.")
    sub = parser.add_subparsers(dest="command", required=True)
    compare = sub.add_parser("compare", help="apdoroti skambučius abiem būdais ir palyginti")
    compare.add_argument("--inputs", type=Path, default=Path("bendra_medziaga"), help="katalogas su manifest.csv")
    compare.add_argument("--data-root", type=Path, default=Path(os.environ.get("DATA_ROOT", ".")),
                         help="katalogas, kuriame yra dataset/ (numatyta: DATA_ROOT arba dabartinis)")
    compare.add_argument("--output", type=Path, default=Path("data/results"), help="kiekvieno skambučio rezultatai")
    compare.add_argument("--reports", type=Path, default=Path("reports/part2"), help="palyginimo ataskaita")
    compare.add_argument("--modes", nargs="+", choices=["python", "spark"], default=["python", "spark"])
    compare.add_argument("--master", default="local[4]", help="Spark režimas (numatyta: local[4])")
    compare.add_argument("--limit", type=int, help="tik N trumpiausių skambučių, greitam bandymui")
    compare.add_argument("--config", type=Path, default=Path("config"),
                         help="katalogas su models.toml ir prompts.toml (numatyta: config)")
    compare.set_defaults(func=cmd_compare)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
