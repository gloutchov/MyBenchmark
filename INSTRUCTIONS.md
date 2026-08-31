# User Manual – LocalAgent Benchmark

## 1. Purpose

LocalAgent Benchmark compares local Ollama models acting as coding agents through Pi. Every model receives inputs copied from the same frozen snapshot of `AGENTS.md`, prompt, and Git fixture. Independent checks score the resulting workspace, while raw artifacts remain available for human review.

## 2. Requirements

- Python 3.10+ and Git on `PATH`;
- Ollama running on the configured loopback endpoint;
- Pi available as the `pi` command;
- one or more downloaded Ollama models;
- enough disk space for one fixture workspace per attempt.

Optional OS enforcement requires a usable `sandbox-exec` on macOS; `bwrap`, `unshare`, and usable user/network namespaces on Linux; or Windows 10/11 with AppContainer. `doctor` performs a real probe and reports availability, the effective backend, and its capabilities without installing components. Platform-specific procedures are in [QUICK-START_Linux.md](QUICK-START_Linux.md) and [QUICK-START_Windows.md](QUICK-START_Windows.md).

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

Use `--models` for exact Ollama model names, `--cases` for explicit case IDs, `--timeout` for a per-task limit in seconds, and `--output` for a new or empty destination. Tasks are randomized; pass `--seed NUMBER` to reproduce the exact order recorded in `run.json`. `--sandbox` accepts `audit`, `auto`, or `required`; use `required` when the run must not continue without OS enforcement. Run the full profile three times on shortlisted models when making a final choice.

Compare compatible runs statistically:

```bash
python3 benchmark.py compare results/RUN-1 results/RUN-2 results/RUN-3
```

The command accepts only distinct directories and runs with matching versions/parameters, profiles, cases, input fingerprints, model digests, sandbox backend, platform, and recorded hardware. It writes `comparison.json` and `COMPARISON.md` with mean, median, standard deviation, and an approximate 95% interval bounded to each metric's natural domain. Missing or integrity-disqualified models receive no sample for that run.

## 5. Configuration

`benchmark.json` is the central configuration file. It defines the Ollama URL, Pi command, model selection, timeout, repetitions, thinking level, warmup, context and output limits, temperature, sandbox mode, profiles, cases, and weights.

Configuration is validated at startup. It must not contain secrets. The generated Ollama provider uses the literal dummy key `ollama`, which the local server ignores.

## 6. Reading results

The composite score weighs quality at 80%, completion at 10%, relative speed at 5%, and relative token efficiency at 5%. A task counts as complete when Pi exits normally and its grade is at least 60/100.

Read **Environment and isolation** and **Run integrity** before the leaderboard. The former distinguishes the requested and effective backend and never labels a fallback as sandboxed. A model is entirely disqualified if it explicitly references a path resolved outside its workspace, attempts network access, mutates the benchmark repository or frozen snapshot, or receives a divergent baseline. Snapshot mutation also aborts the remaining matrix. The report lists model, case, repetition, reason, target, and evidence; `run.json` records hardware, sandbox, Git provenance, seed, task order, input and policy hashes, and violations. Each `result.json` records its baseline tree, audit version, system metrics, and original details.

- Prioritize quality and the cases closest to your real work.
- Use median duration to estimate day-to-day waiting time.
- Tool errors reveal model/provider tool-calling problems.
- Score standard deviation becomes useful after at least three repetitions.
- Treat RAPL energy as a host-wide measurement: compare it only on the same machine under similar load.
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
- `Sandbox OS richiesta ma non disponibile`: install or enable the backend reported by `doctor`, deliberately use `--sandbox auto` to permit fallback, or choose `--sandbox audit` for the historical behavior.
- `linux-bubblewrap` unavailable: check `bwrap`, `unshare`, and the user-namespace policy using the Linux quick start; do not run the benchmark as root to bypass the probe.
- `windows-appcontainer` unavailable: run `doctor` as a standard user and check ACL, AppContainer profile, and named-pipe diagnostics using the Windows quick start.

The runner exits with code `1` when one or more tasks end in an error or timeout or when integrity is not valid, while still writing the available report. A low grade with status `ok` and integrity `ok` is a valid model result and does not fail the command.

## 9. Security and privacy

Do not add private data, real repositories, or credentials to cases. `audit` and the `auto` fallback are not sandboxes. The macOS backend restricts external user files and networking except Ollama loopback and relies on the deprecated `sandbox-exec` interface. On Linux, Pi runs in an empty network namespace and reaches only the Ollama broker through a Unix socket inside the workspace. On Windows, AppContainer receives no network capabilities and uses a named pipe dedicated to its SID; temporary ACLs grant only required paths, and a Job Object terminates descendants. Brokers and graders remain trusted host processes outside the sandbox. Read `SECURITY_MODEL.md` before extending the benchmark.

## 10. Known limitations

- Automatic graders cannot fully judge code taste or explanation quality.
- Timing depends on hardware, quantization, memory pressure, and thermals.
- The runner currently targets Ollama and does not include a Codex control adapter.
- Synthetic tasks should evolve with your actual workflow.
- The Linux backend depends on unprivileged user/network namespaces; restrictive kernel or AppArmor policies make its probe fail, and `required` then stops the run.
- AppContainer grants read access to the Pi runtime and applies/removes ACLs and its profile on a best-effort basis; an abnormal launcher exit may require manual cleanup or diagnosis.
- The broker forwards only to the configured Ollama destination, but it does not authenticate or semantically filter request content.
- Dynamic or obfuscated commands may still evade the audit when no enforced backend is active.
- `sandbox-exec` is deprecated and may disappear from future macOS versions; `required` prevents silent fallback.
- POSIX child metrics may not fully include every descendant; RAPL is host-wide and may be unreadable without additional privileges.
