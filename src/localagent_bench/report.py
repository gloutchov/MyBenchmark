"""Aggregate benchmark results into machine- and human-readable reports."""

from __future__ import annotations

import json
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any


def _mean(values: list[float]) -> float:
    return statistics.fmean(values) if values else 0.0


def _median(values: list[float]) -> float:
    return statistics.median(values) if values else 0.0


def _fmt_seconds(value: float) -> str:
    minutes, seconds = divmod(int(round(value)), 60)
    return f"{minutes}m {seconds:02d}s" if minutes else f"{seconds}s"


def _load_results(run_dir: Path) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for path in sorted(run_dir.glob("models/*/cases/*/result.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(payload, dict):
            payload["_path"] = str(path.relative_to(run_dir))
            results.append(payload)
    return results


def build_report(run_dir: Path) -> dict[str, Any]:
    results = _load_results(run_dir)
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for result in results:
        grouped[str(result.get("model", "unknown"))].append(result)

    eligible = [
        item
        for item in results
        if item.get("status") == "ok" and float(item.get("grade", {}).get("score", 0)) >= 60
    ]
    fastest_by_case: dict[tuple[str, int], float] = {}
    fewest_tokens_by_case: dict[tuple[str, int], int] = {}
    for item in eligible:
        key = (str(item.get("case_id")), int(item.get("repetition", 1)))
        duration = float(item.get("duration_seconds", 0))
        tokens = int(item.get("metrics", {}).get("usage", {}).get("output", 0))
        if duration > 0:
            fastest_by_case[key] = min(fastest_by_case.get(key, duration), duration)
        if tokens > 0:
            fewest_tokens_by_case[key] = min(fewest_tokens_by_case.get(key, tokens), tokens)

    leaderboard: list[dict[str, Any]] = []
    for model, items in grouped.items():
        weighted_scores: list[tuple[float, float]] = []
        durations: list[float] = []
        output_tokens: list[float] = []
        speed_ratios: list[float] = []
        token_ratios: list[float] = []
        completed = 0
        for item in items:
            score = float(item.get("grade", {}).get("score", 0))
            weight = float(item.get("case_weight", 1))
            weighted_scores.append((score, weight))
            duration = float(item.get("duration_seconds", 0))
            durations.append(duration)
            tokens = int(item.get("metrics", {}).get("usage", {}).get("output", 0))
            if tokens:
                output_tokens.append(float(tokens))
            if item.get("status") == "ok" and score >= 60:
                completed += 1
                key = (str(item.get("case_id")), int(item.get("repetition", 1)))
                fastest = fastest_by_case.get(key)
                fewest = fewest_tokens_by_case.get(key)
                if fastest and duration:
                    speed_ratios.append(min(1.0, fastest / duration) * 100)
                if fewest and tokens:
                    token_ratios.append(min(1.0, fewest / tokens) * 100)
        denominator = sum(weight for _, weight in weighted_scores)
        quality = sum(score * weight for score, weight in weighted_scores) / denominator if denominator else 0
        completion = completed / len(items) * 100 if items else 0
        speed = _mean(speed_ratios)
        token_efficiency = _mean(token_ratios)
        overall = 0.80 * quality + 0.10 * completion + 0.05 * speed + 0.05 * token_efficiency
        scores = [score for score, _ in weighted_scores]
        case_scores: dict[str, list[float]] = defaultdict(list)
        for item in items:
            case_scores[str(item.get("case_id", "unknown"))].append(float(item.get("grade", {}).get("score", 0)))
        leaderboard.append(
            {
                "model": model,
                "overall_score": round(overall, 2),
                "quality_score": round(quality, 2),
                "completion_rate": round(completion, 2),
                "speed_score": round(speed, 2),
                "token_efficiency_score": round(token_efficiency, 2),
                "median_duration_seconds": round(_median(durations), 3),
                "median_output_tokens": round(_median(output_tokens), 1),
                "score_stddev": round(statistics.pstdev(scores), 2) if len(scores) > 1 else 0.0,
                "successful_tasks": completed,
                "total_tasks": len(items),
                "case_scores": {case_id: round(_mean(values), 2) for case_id, values in sorted(case_scores.items())},
            }
        )
    leaderboard.sort(key=lambda row: (-row["overall_score"], -row["quality_score"], row["median_duration_seconds"]))

    return {
        "schema_version": 1,
        "formula": {
            "overall": "0.80*quality + 0.10*completion + 0.05*speed + 0.05*token_efficiency",
            "completion_threshold": 60,
            "notes": "Speed and token efficiency are relative to the fastest/leanest successful run for each case and repetition.",
        },
        "leaderboard": leaderboard,
        "results": results,
    }


def render_markdown(report: dict[str, Any], run_dir: Path) -> str:
    leaderboard = report.get("leaderboard", [])
    lines = [
        "# LocalAgent Benchmark Report",
        "",
        f"Run: `{run_dir.name}`",
        "",
        "## Classifica",
        "",
        "| # | Modello | Totale | Qualità | Completamento | Velocità | Token eff. | Tempo mediano | Token output | σ score |",
        "|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for index, row in enumerate(leaderboard, 1):
        lines.append(
            "| {rank} | `{model}` | {overall:.1f} | {quality:.1f} | {completion:.0f}% | {speed:.1f} | "
            "{tokens_eff:.1f} | {duration} | {tokens:.0f} | {stddev:.1f} |".format(
                rank=index,
                model=row["model"],
                overall=row["overall_score"],
                quality=row["quality_score"],
                completion=row["completion_rate"],
                speed=row["speed_score"],
                tokens_eff=row["token_efficiency_score"],
                duration=_fmt_seconds(row["median_duration_seconds"]),
                tokens=row["median_output_tokens"],
                stddev=row["score_stddev"],
            )
        )
    if not leaderboard:
        lines.append("| – | Nessun risultato valido | – | – | – | – | – | – | – | – |")

    case_ids = sorted({str(item.get("case_id")) for item in report.get("results", [])})
    if case_ids:
        lines.extend(
            [
                "",
                "## Qualità per caso",
                "",
                "| Modello | " + " | ".join(f"`{case_id}`" for case_id in case_ids) + " |",
                "|---|" + "---:|" * len(case_ids),
            ]
        )
        for row in leaderboard:
            cells = [f"{row.get('case_scores', {}).get(case_id, 0):.1f}" for case_id in case_ids]
            lines.append(f"| `{row['model']}` | " + " | ".join(cells) + " |")

    lines.extend(
        [
            "",
            "Il punteggio totale pesa qualità 80%, completamento 10%, velocità relativa 5% ed efficienza token relativa 5%. "
            "Una task è completata quando `pi` termina correttamente e il grader assegna almeno 60/100.",
            "",
            "## Dettaglio per task",
            "",
            "| Modello | Caso | Rip. | Stato | Punti | Tempo | Tool/errori | Output token |",
            "|---|---|---:|---|---:|---:|---:|---:|",
        ]
    )
    for result in sorted(report.get("results", []), key=lambda item: (str(item.get("model")), str(item.get("case_id")), int(item.get("repetition", 1)))):
        metrics = result.get("metrics", {})
        lines.append(
            "| `{model}` | `{case}` | {repetition} | {status} | {score:.1f} | {duration} | {tools}/{errors} | {tokens} |".format(
                model=result.get("model", "?"),
                case=result.get("case_id", "?"),
                repetition=result.get("repetition", 1),
                status=result.get("status", "?"),
                score=float(result.get("grade", {}).get("score", 0)),
                duration=_fmt_seconds(float(result.get("duration_seconds", 0))),
                tools=metrics.get("tool_calls", 0),
                errors=metrics.get("tool_errors", 0),
                tokens=metrics.get("usage", {}).get("output", 0),
            )
        )

    lines.extend(["", "## Lettura dei risultati", ""])
    if leaderboard:
        best = leaderboard[0]
        if not any(row["successful_tasks"] for row in leaderboard):
            lines.append(
                "Nessun modello ha completato una task sopra soglia senza errori o timeout. "
                "I punteggi parziali restano utili per diagnosticare il lavoro prodotto, ma questo run non identifica un vincitore operativo."
            )
        else:
            lines.append(
                f"Il miglior punteggio composito di questo run è **{best['model']}** ({best['overall_score']:.1f}/100). "
                "Controlla comunque i punteggi dei singoli casi e le patch: il modello migliore in assoluto può non essere quello più adatto alle task che svolgi più spesso."
            )
    else:
        lines.append("Il run non contiene ancora risultati. Esegui il benchmark prima di interpretare il report.")
    lines.extend(
        [
            "",
            "I tempi includono ragionamento, chiamate agli strumenti e test: rappresentano la produttività end-to-end, non il throughput puro di Ollama. "
            "Confronta i tempi solo sullo stesso computer, con lo stesso profilo e senza altri carichi pesanti.",
            "",
        ]
    )
    return "\n".join(lines)


def write_report(run_dir: Path) -> dict[str, Any]:
    report = build_report(run_dir)
    (run_dir / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (run_dir / "REPORT.md").write_text(render_markdown(report, run_dir), encoding="utf-8")
    return report
