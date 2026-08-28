"""Command-line interface."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .config import ConfigError, load_config
from .ollama import OllamaError
from .report import write_report
from .runner import BenchmarkError, doctor, run_benchmark


ROOT = Path(__file__).resolve().parents[2]


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="benchmark.py",
        description="Benchmark personale offline per Pi + Ollama",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=ROOT / "benchmark.json",
        help="Percorso della configurazione (default: benchmark.json)",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("doctor", help="Verifica Pi, Git, Ollama, modelli e casi")
    subparsers.add_parser("list", help="Elenca profili, casi e modelli rilevati")

    run = subparsers.add_parser("run", help="Esegue il benchmark")
    run.add_argument("--profile", default="standard", help="Profilo da eseguire")
    run.add_argument("--models", nargs="+", help="Modelli Ollama (default dalla configurazione)")
    run.add_argument("--cases", nargs="+", help="Casi specifici, ignorando il profilo")
    run.add_argument("--repetitions", type=int, help="Ripetizioni per modello/caso")
    run.add_argument("--timeout", type=int, help="Timeout di ogni task in secondi")
    warmup = run.add_mutually_exclusive_group()
    warmup.add_argument("--warmup", dest="warmup", action="store_true", help="Forza warmup")
    warmup.add_argument("--no-warmup", dest="warmup", action="store_false", help="Disabilita warmup")
    run.set_defaults(warmup=None)
    run.add_argument("--output", type=Path, help="Directory output esplicita")

    report = subparsers.add_parser("report", help="Rigenera il report di un run")
    report.add_argument("run_dir", type=Path)
    return parser


def _print_doctor(payload: dict) -> None:
    for check in payload["checks"]:
        mark = "OK" if check["ok"] else "ERRORE"
        print(f"[{mark:6}] {check['name']}: {check['detail']}")
    if payload["models"]:
        print("\nModelli Ollama:")
        for model in payload["models"]:
            size = model.get("size")
            size_text = f"{size / (1024 ** 3):.1f} GiB" if size else "dimensione sconosciuta"
            print(f"  - {model['name']} ({size_text})")


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        config = load_config(args.config)
        if args.command == "doctor":
            payload = doctor(config)
            _print_doctor(payload)
            return 0 if payload["ok"] else 1
        if args.command == "list":
            payload = doctor(config)
            print("Profili:")
            for name, ids in config.profiles.items():
                print(f"  - {name}: {', '.join(ids)}")
            print("\nCasi:")
            for case in config.cases.values():
                print(f"  - {case.id}: {case.title} [{case.category}, peso {case.weight:g}]")
            print("\nModelli Ollama:")
            for model in payload["models"]:
                print(f"  - {model['name']}")
            return 0 if payload["ok"] else 1
        if args.command == "run":
            run_dir = run_benchmark(
                config,
                profile=args.profile,
                requested_models=args.models,
                requested_cases=args.cases,
                repetitions=args.repetitions,
                timeout_seconds=args.timeout,
                use_warmup=args.warmup,
                output_dir=args.output,
            )
            print(f"\nBenchmark completato: {run_dir}")
            print(f"Report: {run_dir / 'REPORT.md'}")
            report_payload = json.loads((run_dir / "report.json").read_text(encoding="utf-8"))
            failed = [item for item in report_payload.get("results", []) if item.get("status") != "ok"]
            if failed:
                print(f"Attenzione: {len(failed)} task terminate con errore o timeout.", file=sys.stderr)
                return 1
            return 0
        if args.command == "report":
            report = write_report(args.run_dir.resolve())
            print(json.dumps(report["leaderboard"], indent=2, ensure_ascii=False))
            return 0
    except (ConfigError, BenchmarkError, OllamaError, OSError) as exc:
        print(f"Errore: {exc}", file=sys.stderr)
        return 2
    return 2
