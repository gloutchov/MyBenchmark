# LocalAgent Benchmark

Benchmark personale, ripetibile e offline per confrontare modelli Ollama usati come coding agent tramite [Pi](https://pi.dev). Gli scenari derivano dalle regole operative di questo repository: patch piccole, architettura modulare, test, sicurezza, configurazione, i18n, documentazione e disciplina Git.

Personal, repeatable, offline benchmark for comparing Ollama models used as coding agents through [Pi](https://pi.dev). Its scenarios derive from this repository's operating rules: small patches, modular architecture, tests, security, configuration, i18n, documentation, and Git discipline.

Stato / Status: **0.1.2 – benchmark con controlli d'integrità / integrity-aware benchmark**
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

Non servono pacchetti Python esterni. Pi 0.84.3 è la versione verificata durante la creazione; il comando `doctor` aiuta a rilevare incompatibilità future.

No external Python packages are required. Pi 0.84.3 was the version verified during development; `doctor` helps detect future incompatibilities.

## Avvio rapido / Quick start

```bash
python3 benchmark.py doctor
python3 benchmark.py list
python3 benchmark.py run --profile smoke --models qwen3.5:9b-Q4_K_M
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

- `REPORT.md` e `report.json`: classifica e dettaglio;
- `run.json`: ambiente, versioni, commit/stato Git, modelli, seed, ordine task, hash input, warmup e stato d'integrità;
- per ogni modello/caso: workspace finale, eventi JSONL di Pi, risposta finale, stderr, stato Git, patch, score e singoli check.

All'avvio il runner rifiuta `AGENTS.md`, `.gitignore`, prompt, fixture o grader selezionati se modificati rispetto a Git. Crea poi un unico snapshot dei soli file tracciati per l'intero run, escludendo cache e output ignorati, e registra hash e tree Git delle baseline. Accessi espliciti fuori workspace, modifiche al repository o allo snapshot e baseline non uniformi escludono dalla classifica l'intero modello coinvolto; una modifica allo snapshot interrompe anche la matrice. Il report mostra sempre lo stato d'integrità prima della classifica.

At startup the runner rejects selected benchmark inputs that differ from Git, creates one frozen snapshot containing tracked files only (excluding ignored caches and outputs), and records input hashes and baseline Git trees. Explicit out-of-workspace access, repository/snapshot mutation, or a divergent baseline disqualifies the affected model. Snapshot mutation also aborts the remaining matrix. Integrity status is shown before the leaderboard.

Il comando termina con exit code `1` se almeno una task va in timeout o Pi restituisce un errore, pur completando il resto della matrice e generando il report. Un punteggio sotto 60 senza errore operativo non cambia l'exit code: è un risultato del modello, non un guasto del runner.

Esamina sempre `grade.json`, `diff.patch` e il workspace dei due o tre modelli migliori. I grader misurano requisiti osservabili, ma non sostituiscono il giudizio su leggibilità, chiarezza delle spiegazioni o buon gusto architetturale.

Always inspect `grade.json`, `diff.patch`, and the final workspace for the top candidates. Automated graders do not replace human judgment about readability, explanations, or architectural taste.

I tempi includono ragionamento, strumenti e test e sono quindi una misura di produttività end-to-end. Confrontali solo sulla stessa macchina, con lo stesso profilo e carico simile. Il warmup esclude il caricamento iniziale dal tempo del task; `run.json` conserva le metriche del warmup separatamente.

## Configurazione / Configuration

[`benchmark.json`](benchmark.json) centralizza URL Ollama, comando Pi, timeout, thinking, contesto, token massimi, warmup, profili, casi e pesi. `"models": "installed"` rileva tutti i modelli da `/api/tags`; una lista esplicita rende il set stabile.

La temperatura è zero per ridurre la varianza. Le ripetizioni restano necessarie: tool calling e generazione locale non sono perfettamente deterministici. L'ordine delle task viene randomizzato e registrato; `--seed` permette di riprodurlo. Per un confronto decisionale usare almeno tre ripetizioni e la stessa alimentazione/condizione termica.

## Isolamento e privacy / Isolation and privacy

Il runner crea per ogni task un repository Git nuovo da uno snapshot condiviso, copia al suo interno questo `AGENTS.md` e usa una directory Pi separata. Pi riceve `--offline` e Ollama usa loopback. Le fixture non contengono credenziali reali.

Attenzione: gli strumenti `bash` e `write` di Pi non sono un sandbox del sistema operativo. I nuovi controlli rilevano mutazioni e molti accessi espliciti, ma non impediscono tecnicamente ogni lettura esterna o comando offuscato. Esegui il benchmark con un account non privilegiato e leggi [SECURITY_MODEL.md](SECURITY_MODEL.md) prima di aggiungere casi con dati reali.

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

Il progetto viene eseguito direttamente dal checkout e non produce ancora release o artifact. Quando sarà prevista una distribuzione, saranno aggiunti wheel/pacchetto, smoke test fuori dal checkout e checksum SHA-256 secondo [`PLAN.md`](PLAN.md).

## Documentazione / Documentation

- [Manuale italiano](ISTRUZIONI.md)
- [English manual](INSTRUCTIONS.md)
- [Modello di sicurezza bilingue](SECURITY_MODEL.md)
- [Piano di sviluppo](PLAN.md)
- [Mappa del repository](MAP.md)
- [Regole per agenti e maintainer](AGENTS.md)
