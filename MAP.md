# Mappa repository / Repository Map

```text
.
├── benchmark.py                    # entry point locale senza installazione
├── benchmark.json                  # configurazione centrale, profili e root discovery casi
├── schemas/case.schema.json        # schema pubblico dei manifesti case.json
├── src/localagent_bench/
│   ├── cli.py                      # doctor/list/run/report/compare e comandi case create/validate
│   ├── config.py                   # modello e validazione configurazione
│   ├── case_sdk.py                 # discovery, manifesti, validatore e template atomico dei casi
│   ├── integrity.py                # preflight Git, snapshot, SHA-256 e drift repository
│   ├── ollama.py                   # client locale tags/version/warmup/unload
│   ├── pi_adapter.py               # Pi, parsing JSONL, scratch e audit path/rete versionato
│   ├── runner.py                   # ordine seeded, policy, workspace, controlli e artefatti
│   ├── grading.py                  # esecuzione isolata e timeout dei grader
│   ├── sandbox.py                  # selezione, probe e launch Seatbelt/bubblewrap/AppContainer/audit
│   ├── sandbox_transport.py        # broker Ollama Unix e shim Node a destinazione fissa
│   ├── windows_appcontainer.py     # profilo, ACL/DACL, named pipe e Job Object Windows
│   ├── system_metrics.py           # hardware, rusage POSIX e RAPL opzionale
│   ├── comparison.py               # compatibilità e statistiche tra più run
│   └── report.py                   # aggregazione, metriche, disqualifiche e Markdown
├── cases/
│   ├── targeted_patch/             # manifesto, bugfix, regressioni, scope e README
│   ├── secure_workspace/           # manifesto, path, symlink, atomicità e redazione
│   ├── config_i18n/                # manifesto, validazione, persistenza, lingua e tema
│   └── milestone_closure/          # branch, versioning, docs e stop pre-merge
│       ├── case.json               # titoli bilingui, categoria, peso e path confinati
│       ├── prompt.md               # richiesta consegnata al modello
│       ├── fixture/                # repository iniziale, inclusa LICENSE richiesta
│       ├── grader.py               # controlli esterni al prompt
│       └── manual-rubric.md        # valutazione umana opzionale, fuori score automatico
├── tests/
│   ├── test_case_sdk.py            # schema, path corrotti, template, CLI e calibrazione
│   └── ...                         # runner, parser, sandbox, metriche, confronti e grader
├── results/                        # output, snapshot input, hash e workspace; ignorato da Git
├── .github/workflows/ci.yml        # Actions Node 24: compile, test e documenti su tre OS
├── AGENTS.md                       # modus operandi copiato in ogni fixture
├── README.md                       # overview bilingue e quick start
├── ISTRUZIONI.md                   # manuale italiano
├── INSTRUCTIONS.md                 # manuale inglese
├── QUICK-START_Linux.md            # prerequisiti, smoke e diagnosi Linux
├── QUICK-START_Windows.md          # prerequisiti, smoke e diagnosi Windows
├── QUICK-START_Case-Author.md       # creazione, schema, grader, validazione e sicurezza
├── SECURITY_MODEL.md               # controlli, rischi e limiti bilingui
├── PLAN.md                         # milestone, criteri e checklist
├── VERSION                         # versione canonica
├── pyproject.toml                  # metadata Python, senza dipendenze runtime
└── LICENSE                         # Apache License 2.0
```

`results/` nasce al primo run. `benchmark-context/` contiene la fotografia condivisa e verificata di manifesti, prompt, fixture, grader, rubriche e `EXECUTION_POLICY.snapshot.md`; `run.json` registra commit/stato Git, seed, ordine task, SHA-256, versione audit, sandbox effettiva, hardware, warmup e violazioni. Ogni tentativo contiene una `workspace/` deliberatamente modificabile dal modello, una `.benchmark-scratch/` interna ignorata da Git (profilo Seatbelt o socket del broker Linux quando applicabili), una `.pi-agent/` per-task e artefatti fratelli (`result.json`, `grade.json`, `pi-events.jsonl`, `diff.patch` e l'eventuale `manual-rubric.md`), inclusi tree baseline, audit, backend e metriche di sistema. Su Windows, metadata di cleanup e sole fasi/conteggi byte del broker vengono registrati negli artefatti runtime; il named pipe vive nel namespace AppContainer della sessione. `comparison-*` contiene `comparison.json` e `COMPARISON.md` per run compatibili. I file sorgente sotto `cases/` non devono essere modificati durante un'esecuzione; il preflight li richiede puliti e il confronto post-task rileva cambiamenti successivi.
