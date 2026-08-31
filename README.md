# LocalAgent Benchmark

Benchmark personale, ripetibile e offline per confrontare modelli Ollama usati come coding agent tramite [Pi](https://pi.dev). Gli scenari derivano dalle regole operative di questo repository: patch piccole, architettura modulare, test, sicurezza, configurazione, i18n, documentazione e disciplina Git.

Personal, repeatable, offline benchmark for comparing Ollama models used as coding agents through [Pi](https://pi.dev). Its scenarios derive from this repository's operating rules: small patches, modular architecture, tests, security, configuration, i18n, documentation, and Git discipline.

Stato / Status: **0.3.0 candidate – sandbox OS multipiattaforma / cross-platform OS sandbox**
Piattaforme / Platforms: macOS, Windows, Linux
Licenza / License: Apache-2.0

## Cosa misura / What it measures

Il benchmark valuta il risultato completo dell'agente, non una singola risposta testuale:

- qualità funzionale tramite grader e test indipendenti dal prompt;
- rispetto di scope, API e file non correlati;
- sicurezza di path, scritture e log;
- configurazione validata, i18n e preferenze UI;
- aggiornamento coordinato di versione, piano e documentazione;
- stato di uscita, timeout, errori tool, token e tempo end-to-end.

The benchmark evaluates the complete agent outcome rather than a single text response: functional quality, scope discipline, security, configuration/i18n, documentation, Git workflow, failures, tokens, and end-to-end time.

Il punteggio composito pesa **qualità 80%**, **completamento 10%**, **velocità relativa 5%** ed **efficienza token relativa 5%**. Qualità e tempi restano visibili separatamente; un modello veloce che non completa il task non viene favorito in modo sostanziale.

## Requisiti / Requirements

- Python 3.10 o successivo;
- Git;
- Ollama avviato su `http://127.0.0.1:11434`;
- Pi installato e disponibile come comando `pi`;
- almeno un modello Ollama già scaricato e capace di tool calling.

La sandbox OS è opzionale: macOS usa `sandbox-exec`; Linux richiede `bwrap`, `unshare` e user/network namespace utilizzabili; Windows 10/11 usa AppContainer. Ogni backend viene applicato solo dopo un probe reale. `doctor` mostra sempre il backend e le capacità effettivamente disponibili.

The OS sandbox is optional: macOS uses `sandbox-exec`; Linux requires `bwrap`, `unshare`, and usable user/network namespaces; Windows 10/11 uses AppContainer. Each backend is enabled only after a real probe. `doctor` always reports the backend and capabilities that are actually available.

Non servono pacchetti Python esterni. Pi 0.84.3 è la versione verificata durante la creazione; il comando `doctor` aiuta a rilevare incompatibilità future.

No external Python packages are required. Pi 0.84.3 was the version verified during development; `doctor` helps detect future incompatibilities.

## Avvio rapido / Quick start

```bash
python3 benchmark.py doctor
python3 benchmark.py list
python3 benchmark.py run --profile smoke --models qwen3.5:9b-Q4_K_M
```

Per richiedere isolamento OS senza accettare fallback:

```bash
python3 benchmark.py run --profile smoke --models qwen3.5:9b-Q4_K_M --sandbox required
```

Per un primo confronto di tutti i modelli installati:

```bash
python3 benchmark.py run --profile standard
```

For a more reliable final comparison, run the full profile three times:

```bash
python3 benchmark.py run --profile full --repetitions 3
```

Un run completo con molti modelli può richiedere ore. Conviene prima eseguire `smoke`, eliminare i modelli incompatibili con gli strumenti e poi usare `standard` o `full` sui finalisti.

## Profili / Profiles

| Profilo | Casi | Uso consigliato |
|---|---:|---|
| `smoke` | 1 | Verifica rapida di integrazione Pi/Ollama e tool calling |
| `standard` | 3 | Confronto principale su implementazione, sicurezza e architettura |
| `full` | 4 | Aggiunge versioning, documentazione e disciplina Git |

È possibile selezionare modelli e casi esplicitamente:

```bash
python3 benchmark.py run \
  --models devstral-small-2:latest qwen3.6:27b \
  --cases targeted_patch secure_workspace \
  --repetitions 2 \
  --timeout 1800 \
  --seed 20260829
```

Su PowerShell, inserire il comando su una sola riga oppure usare il carattere di continuazione appropriato.

## Output e lettura / Output and interpretation

Ogni run crea `results/YYYYMMDD-HHMMSS/` con:

- `REPORT.md` e `report.json`: classifica, isolamento effettivo, metriche disponibili e dettaglio;
- `run.json`: ambiente/hardware, versioni, backend sandbox effettivo, commit/stato Git, modelli, seed, ordine task, hash input e policy di esecuzione, warmup e stato d'integrità;
- per ogni modello/caso: workspace finale, eventi JSONL di Pi, risposta finale, stderr, stato Git, patch, score e singoli check.

All'avvio il runner rifiuta `AGENTS.md`, `.gitignore`, prompt, fixture o grader selezionati se modificati rispetto a Git. Crea poi un unico snapshot dei soli file tracciati e della policy di esecuzione, escludendo cache e output ignorati, e registra hash e tree Git delle baseline. Ogni task riceve una directory `.benchmark-scratch/` interna e ignorata da Git; `TMPDIR`, `TMP` e `TEMP` puntano lì. Path shell risolti fuori workspace, tentativi espliciti di rete, modifiche al repository o allo snapshot e baseline non uniformi escludono dalla classifica l'intero modello coinvolto; una modifica allo snapshot interrompe anche la matrice. Il report mostra stato e dettaglio delle violazioni prima della classifica.

At startup the runner rejects selected benchmark inputs that differ from Git, creates one frozen snapshot containing tracked files and the execution policy (excluding ignored caches and outputs), and records input hashes and baseline Git trees. Each task gets an internal Git-ignored `.benchmark-scratch/` directory used by `TMPDIR`, `TMP`, and `TEMP`. Shell paths resolved outside the workspace, explicit network attempts, repository/snapshot mutation, or a divergent baseline disqualify the affected model. Snapshot mutation also aborts the remaining matrix. Integrity status and violation details are shown before the leaderboard.

Il comando termina con exit code `1` se almeno una task va in timeout o Pi restituisce un errore, pur completando il resto della matrice e generando il report. Un punteggio sotto 60 senza errore operativo non cambia l'exit code: è un risultato del modello, non un guasto del runner.

Esamina sempre `grade.json`, `diff.patch` e il workspace dei due o tre modelli migliori. I grader misurano requisiti osservabili, ma non sostituiscono il giudizio su leggibilità, chiarezza delle spiegazioni o buon gusto architetturale.

Always inspect `grade.json`, `diff.patch`, and the final workspace for the top candidates. Automated graders do not replace human judgment about readability, explanations, or architectural taste.

I tempi includono ragionamento, strumenti e test e sono quindi una misura di produttività end-to-end. Confrontali solo sulla stessa macchina, con lo stesso profilo e carico simile. Il warmup esclude il caricamento iniziale dal tempo del task; `run.json` conserva le metriche del warmup separatamente.

Ogni `result.json` include inoltre metriche POSIX dei processi figli e, sui sistemi Linux che espongono contatori RAPL leggibili, energia host-wide. Campo `available`, provider e scope impediscono di confondere un dato assente o di sistema con il consumo esclusivo del modello.

Each `result.json` also includes POSIX child-process metrics and, on Linux systems exposing readable RAPL counters, host-wide energy. Availability, provider, and scope fields keep missing or system-wide data from being presented as model-exclusive consumption.

## Confronto multi-run / Multi-run comparison

Aggregare run compatibili senza ricopiare manualmente i punteggi:

```bash
python3 benchmark.py compare results/RUN-1 results/RUN-2 results/RUN-3
```

Il comando produce `comparison.json` e `COMPARISON.md` con media, mediana, deviazione standard e intervallo al 95% approssimato, limitato al dominio naturale della metrica. Rifiuta directory duplicate e confronti tra versioni/parametri, profili, input, digest modello, backend sandbox, piattaforme o hardware differenti; i modelli esclusi dall'integrità non ricevono campioni.

The command writes `comparison.json` and `COMPARISON.md` with mean, median, standard deviation, and an approximate 95% interval bounded to each metric's natural domain. It rejects duplicate directories and runs with different versions/parameters, profiles, inputs, model digests, sandbox backends, platforms, or recorded hardware; integrity-disqualified models do not contribute samples.

## Configurazione / Configuration

[`benchmark.json`](benchmark.json) centralizza URL Ollama, comando Pi, timeout, thinking, contesto, token massimi, warmup, sandbox, profili, casi e pesi. `"models": "installed"` rileva tutti i modelli da `/api/tags`; una lista esplicita rende il set stabile. `defaults.sandbox` accetta `audit`, `auto` o `required`; il default conservativo e retrocompatibile è `audit`.

La temperatura è zero per ridurre la varianza. Le ripetizioni restano necessarie: tool calling e generazione locale non sono perfettamente deterministici. L'ordine delle task viene randomizzato e registrato; `--seed` permette di riprodurlo. Per un confronto decisionale usare almeno tre ripetizioni e la stessa alimentazione/condizione termica.

## Isolamento e privacy / Isolation and privacy

Il runner crea per ogni task un repository Git nuovo da uno snapshot condiviso, copia al suo interno questo `AGENTS.md`, premette al prompt una policy di confine bilingue e usa una directory Pi separata. La policy vieta rete e path esterni e indica `.benchmark-scratch/` per test e file temporanei. Pi riceve `--offline` e Ollama usa loopback. Le fixture includono i materiali richiesti dal caso e non contengono credenziali reali.

For each task, the runner creates a fresh Git repository from the shared snapshot, copies this `AGENTS.md`, prepends a bilingual boundary policy to the prompt, and uses a separate Pi directory. The policy forbids network and external paths and designates `.benchmark-scratch/` for tests and temporary files. Pi receives `--offline`, and Ollama remains on loopback. Fixtures include the materials required by each case and contain no real credentials.

`--sandbox audit` conserva il comportamento 0.1.x: policy e rilevamento, senza blocco OS. `auto` usa il backend nativo quando supera il probe e altrimenti registra un fallback esplicito; `required` interrompe prima delle task se l'isolamento non è disponibile. Su macOS Seatbelt blocca letture/scritture nelle aree utente esterne e limita la rete alla porta loopback di Ollama, ma `sandbox-exec` è deprecato. Su Linux `unshare` crea un network namespace vuoto e bubblewrap limita filesystem e processi; un broker host raggiungibile solo tramite socket Unix inoltra verso l'unico endpoint Ollama configurato. Su Windows AppContainer viene avviato senza capability di rete, con ACL temporanee sui soli path necessari, Job Object kill-on-close e un named pipe autorizzato per il SID esatto del container verso lo stesso broker a destinazione fissa.

`--sandbox audit` preserves the 0.1.x behavior: policy and detection without OS enforcement. `auto` uses a native backend only after a successful probe and records an explicit fallback otherwise; `required` stops before tasks when enforcement is unavailable. On macOS, Seatbelt blocks external user-file access and restricts networking to Ollama's loopback port, but `sandbox-exec` is deprecated. On Linux, `unshare` creates an empty network namespace and bubblewrap limits filesystems and processes; a host broker reachable only through a Unix socket forwards to the single configured Ollama endpoint. On Windows, AppContainer runs without network capabilities, with temporary ACLs on only the required paths, a kill-on-close Job Object, and a named pipe authorized for the container's exact SID to the same fixed-destination broker.

An enforced backend narrows risk but does not make untrusted real data safe by itself. Required runtime paths remain readable, graders and brokers run as trusted host processes, result artifacts may contain sensitive content, and `audit`/`auto` fallback remain detection rather than containment. Read [SECURITY_MODEL.md](SECURITY_MODEL.md).

## Sviluppo / Development

```bash
python3 -m compileall -q benchmark.py src cases tests
python3 -m unittest discover -s tests -v
```

Per rigenerare un report esistente:

```bash
python3 benchmark.py report results/20260825-120000
```

Non modificare le fixture durante un run. Per aggiungere un caso, crea `cases/<id>/prompt.md`, `fixture/`, `grader.py`, registra caso e profilo in `benchmark.json`, quindi aggiungi test di calibrazione.

## Distribuzione / Distribution

Il progetto viene eseguito direttamente dal checkout. I tag sorgente non includono ancora wheel o artifact binari; un'eventuale distribuzione fuori checkout richiederà packaging smoke e checksum SHA-256 secondo [`PLAN.md`](PLAN.md).

## Documentazione / Documentation

- [Manuale italiano](ISTRUZIONI.md)
- [English manual](INSTRUCTIONS.md)
- [Avvio rapido Linux / Linux quick start](QUICK-START_Linux.md)
- [Avvio rapido Windows / Windows quick start](QUICK-START_Windows.md)
- [Modello di sicurezza bilingue](SECURITY_MODEL.md)
- [Piano di sviluppo](PLAN.md)
- [Mappa del repository](MAP.md)
- [Regole per agenti e maintainer](AGENTS.md)
