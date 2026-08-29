# User Manual – LocalAgent Benchmark

## 1. Purpose

LocalAgent Benchmark compares local Ollama models acting as coding agents through Pi. Every model receives inputs copied from the same frozen snapshot of `AGENTS.md`, prompt, and Git fixture. Independent checks score the resulting workspace, while raw artifacts remain available for human review.

## 2. Requirements

- Python 3.10+ and Git on `PATH`;
- Ollama running on the configured loopback endpoint;
- Pi available as the `pi` command;
- one or more downloaded Ollama models;
- enough disk space for one fixture workspace per attempt.

Verify the environment without running an agent task:

```bash
python3 benchmark.py doctor
```

The command also verifies that `AGENTS.md`, `.gitignore`, prompts, fixtures, and graders are clean relative to Git.

## 3. First run

List profiles, cases, and models:

```bash
python3 benchmark.py list
```

Start with one small model and the smoke profile:

```bash
python3 benchmark.py run --profile smoke --models qwen3.5:9b-Q4_K_M
```

Then compare all installed models with the standard profile:

```bash
python3 benchmark.py run --profile standard
```

## 4. Main workflows

- `smoke` checks Pi/Ollama integration and basic tool calling.
- `standard` covers a targeted patch, security hardening, and validated configuration/i18n.
- `full` adds milestone closure, versioning, documentation, and Git discipline.

Use `--models` for exact Ollama model names, `--cases` for explicit case IDs, `--timeout` for a per-task limit in seconds, and `--output` for a new or empty destination. Tasks are randomized; pass `--seed NUMBER` to reproduce the exact order recorded in `run.json`. Run the full profile three times on shortlisted models when making a final choice.

## 5. Configuration

`benchmark.json` is the central configuration file. It defines the Ollama URL, Pi command, model selection, timeout, repetitions, thinking level, warmup, context and output limits, temperature, profiles, cases, and weights.

Configuration is validated at startup. It must not contain secrets. The generated Ollama provider uses the literal dummy key `ollama`, which the local server ignores.

## 6. Reading results

The composite score weighs quality at 80%, completion at 10%, relative speed at 5%, and relative token efficiency at 5%. A task counts as complete when Pi exits normally and its grade is at least 60/100.

Read **Run integrity** before the leaderboard. A model is entirely disqualified if it explicitly references a path resolved outside its workspace, attempts network access, mutates the benchmark repository or frozen snapshot, or receives a divergent baseline. Snapshot mutation also aborts the remaining matrix. The report lists model, case, repetition, reason, target, and evidence; `run.json` records Git provenance, seed, task order, input and policy hashes, and violations. Each `result.json` records its baseline tree, audit version, and original details.

- Prioritize quality and the cases closest to your real work.
- Use median duration to estimate day-to-day waiting time.
- Tool errors reveal model/provider tool-calling problems.
- Score standard deviation becomes useful after at least three repetitions.
- Inspect the patch and final workspace for top-ranked models.

The overall winner is not necessarily best for every activity. A security-heavy workflow may favor the best `secure_workspace` score, while ordinary maintenance may favor `targeted_patch`.

## 7. Reproducibility

Use the same configuration, profile, repetitions, seed, hardware, and similar system load. At each model switch the runner unloads the previous model, records a new warmup, and then starts the task. Selected inputs must be clean at startup; only tracked files and the execution policy are copied once into `benchmark-context/`, excluding ignored caches and outputs. Every workspace contains a Git-ignored `.benchmark-scratch/` directory also used for `TMPDIR`, `TMP`, and `TEMP`; models must use it for smoke tests and temporary files instead of `/tmp`. Do not modify source inputs or the snapshot during a run. Temperature zero reduces but does not eliminate variance.

## 8. Troubleshooting

- `Ollama non raggiungibile`: start Ollama and check `ollama list`.
- `pi: command not found`: install Pi or update `pi.command`.
- Missing model: use the exact name shown by `doctor`.
- Timeout: increase `--timeout` and inspect `stderr.log`.
- Low score with a successful exit: inspect `grade.json`; the model may have answered without editing or missed a constraint.
- Zero usage tokens: some model/provider combinations omit usage; quality remains valid, while token efficiency receives no credit.
- `Input benchmark modificati`: restore or intentionally commit the listed benchmark inputs before rerunning.
- `violations_detected`: read **Detected violations**, then inspect `report.json`, `run.json`, and the corresponding `pi-events.jsonl`; do not manually restore the disqualified model to the leaderboard. Regenerating a report applies the current audit to older events without changing their original `result.json` files.
- `snapshot_compromised`: preserve the diagnostic artifacts, fix the cause, and start a new run.

The runner exits with code `1` when one or more tasks end in an error or timeout or when integrity is not valid, while still writing the available report. A low grade with status `ok` and integrity `ok` is a valid model result and does not fail the command.

## 9. Security and privacy

Do not add private data, real repositories, or credentials to cases without a dedicated OS-level sandbox. Pi's `--offline` mode disables its startup network activity, while the audit recognizes common network commands and code patterns; neither firewalls shell commands generated by a model. Hashes and audits detect integrity failures but do not replace OS isolation. Read `SECURITY_MODEL.md` before extending the benchmark.

## 10. Known limitations

- Automatic graders cannot fully judge code taste or explanation quality.
- Timing depends on hardware, quantization, memory pressure, and thermals.
- The runner currently targets Ollama and does not include a Codex control adapter.
- Synthetic tasks should evolve with your actual workflow.
- The audit resolves structured and shell paths, including deterministic directory changes, and recognizes common network patterns; dynamic commands, complex shell semantics, or obfuscated code may still evade it until the OS sandbox is implemented.
