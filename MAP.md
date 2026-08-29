# Mappa repository / Repository Map

```text
.
├── benchmark.py                    # entry point locale senza installazione
├── benchmark.json                  # configurazione centrale, profili, casi e pesi
├── src/localagent_bench/
│   ├── cli.py                      # parsing doctor/list/run/report, seed ed exit integrità
│   ├── config.py                   # modello e validazione configurazione
│   ├── integrity.py                # preflight Git, snapshot, SHA-256 e drift repository
│   ├── ollama.py                   # client locale tags/version/warmup/unload
│   ├── pi_adapter.py               # configurazione Pi, parsing JSONL e audit path/tool
│   ├── runner.py                   # ordine seeded, workspace, controlli e artefatti
│   ├── grading.py                  # esecuzione isolata e timeout dei grader
│   └── report.py                   # aggregazione, disqualifiche, formula e Markdown
├── cases/
│   ├── targeted_patch/             # bugfix, regressioni, scope e README
│   ├── secure_workspace/           # path, symlink, atomicità e redazione
│   ├── config_i18n/                # validazione, persistenza, lingua e tema
│   └── milestone_closure/          # branch, versioning, docs e stop pre-merge
│       ├── prompt.md               # richiesta consegnata al modello
│       ├── fixture/                # repository iniziale copiato per ogni tentativo
│       └── grader.py               # controlli esterni al prompt
├── tests/                          # test del runner, parser, report e grader
├── results/                        # output, snapshot input, hash e workspace; ignorato da Git
├── .github/workflows/ci.yml        # compile, test e documenti su tre OS
├── AGENTS.md                       # modus operandi copiato in ogni fixture
├── README.md                       # overview bilingue e quick start
├── ISTRUZIONI.md                   # manuale italiano
├── INSTRUCTIONS.md                 # manuale inglese
├── SECURITY_MODEL.md               # controlli, rischi e limiti bilingui
├── PLAN.md                         # milestone, criteri e checklist
├── VERSION                         # versione canonica
├── pyproject.toml                  # metadata Python, senza dipendenze runtime
└── LICENSE                         # Apache License 2.0
```

`results/` nasce al primo run. `benchmark-context/` contiene la fotografia condivisa e verificata degli input; `run.json` registra commit/stato Git, seed, ordine task, SHA-256, warmup e violazioni. Ogni tentativo contiene una `workspace/` deliberatamente modificabile dal modello e artefatti fratelli (`result.json`, `grade.json`, `pi-events.jsonl`, `diff.patch`), inclusi tree baseline e audit d'integrità. I file sorgente sotto `cases/` non devono essere modificati durante un'esecuzione; il preflight li richiede puliti e il confronto post-task rileva cambiamenti successivi.
