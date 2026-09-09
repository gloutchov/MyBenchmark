# Mappa repository / Repository Map

```text
.
├── benchmark.py                    # entry point locale senza installazione
├── dashboard.py                    # launcher loopback della dashboard ufficiale
├── benchmark.json                  # configurazione centrale, profili e root discovery casi
├── dashboard/                      # dashboard ufficiale statica e offline
│   ├── index.html                  # UI servita dal launcher; file:// richiede snapshot locale
│   ├── styles.css                  # temi, responsive, focus e stampa
│   ├── favicon.svg                 # icona funzionale locale
│   ├── data/snapshot.js            # output locale opzionale generato e ignorato da Git
│   ├── js/                         # core dati, i18n, rendering e stato UI modulari
│   └── tests/dashboard.test.js     # trasformazioni, fixture, i18n e vincoli statici
├── schemas/
│   ├── case.schema.json            # schema pubblico dei manifesti case.json
│   └── dashboard-data.schema.json  # dataset ridotto per la finalissima offline
├── src/localagent_bench/
│   ├── cli.py                      # doctor/list/run/report/compare/dashboard-data e comandi case
│   ├── config.py                   # modello e validazione configurazione
│   ├── case_sdk.py                 # discovery, manifesti, validatore e template atomico dei casi
│   ├── integrity.py                # preflight Git, snapshot, SHA-256 e drift repository
│   ├── ollama.py                   # client locale tags/version/warmup/unload
│   ├── pi_adapter.py               # Pi, parsing JSONL/errori terminali, scratch e audit path/rete
│   ├── runner.py                   # ordine seeded, policy, workspace, controlli e artefatti
│   ├── grading.py                  # esecuzione isolata e timeout dei grader
│   ├── sandbox.py                  # selezione, probe e launch Seatbelt/bubblewrap/AppContainer/audit
│   ├── sandbox_transport.py        # broker Ollama Unix e shim Node a destinazione fissa
│   ├── windows_appcontainer.py     # profilo, ACL/DACL, named pipe e Job Object Windows
│   ├── system_metrics.py           # hardware, rusage POSIX e RAPL opzionale
│   ├── comparison.py               # compatibilità e statistiche tra più run
│   ├── dashboard_data.py           # whitelist, provenienza, funnel e scrittura atomica dashboard
│   ├── dashboard_app.py            # discovery run, snapshot e server statico loopback in memoria
│   └── report.py                   # aggregazione, metriche, disqualifiche e Markdown
├── cases/
│   ├── targeted_patch/             # manifesto, bugfix, regressioni, scope e README
│   ├── secure_workspace/           # manifesto, path, symlink, atomicità e redazione
│   ├── config_i18n/                # manifesto, validazione, persistenza, lingua e tema
│   ├── milestone_closure/          # branch, versioning, docs e stop pre-merge
│   │   ├── case.json               # titoli bilingui, categoria, peso e path confinati
│   │   ├── prompt.md               # richiesta consegnata al modello
│   │   ├── fixture/                # repository iniziale, inclusa LICENSE richiesta
│   │   ├── grader.py               # controlli esterni al prompt
│   │   └── manual-rubric.md        # valutazione umana opzionale, fuori score automatico
│   └── results_dashboard/          # finalissima HTML/CSS/JS, dataset sintetico e dataset hidden
│       ├── case.json               # manifesto del profilo showcase
│       ├── prompt.md               # UX, API JS, i18n, tema, offline e accessibilità
│       ├── fixture/                # baseline incompleta, dataset schema 1 e test Node
│       ├── grader.py               # 100 punti tecnici e dataset alternativo non hardcoded
│       └── manual-rubric.md        # 20 punti visuali separati dalla classifica
├── tests/
│   ├── test_case_sdk.py            # schema, path corrotti, template, CLI e calibrazione
│   ├── test_dashboard_data.py      # whitelist, privacy, funnel, path, atomicità e CLI
│   ├── test_dashboard_app.py       # discovery, snapshot, confinement, server e header sicurezza
│   ├── test_dashboard_javascript.py # esecuzione della suite Node dalla suite unittest
│   └── ...                         # runner, parser/status provider, sandbox, metriche, confronti e grader
├── results/                        # output, snapshot input, hash e workspace; ignorato da Git
├── .github/workflows/ci.yml        # Actions Node 24: compile, test e documenti su tre OS
├── .github/dependabot.yml          # aggiornamenti settimanali delle GitHub Actions
├── AGENTS.md                       # modus operandi copiato in ogni fixture
├── README.md                       # overview bilingue e quick start
├── ISTRUZIONI.md                   # manuale italiano
├── INSTRUCTIONS.md                 # manuale inglese
├── QUICK-START_Linux.md            # prerequisiti, smoke e diagnosi Linux
├── QUICK-START_Windows.md          # prerequisiti, smoke e diagnosi Windows
├── QUICK-START_Case-Author.md       # creazione, schema, grader, validazione e sicurezza
├── QUICK-START_Showcase.md          # export, freeze, run finalisti e verifica browser
├── QUICK-START_Dashboard.md         # launcher, import, snapshot locale e troubleshooting
├── SECURITY_MODEL.md               # controlli, rischi e limiti bilingui
├── SECURITY.md                     # canale privato e ambito delle segnalazioni
├── CONTRIBUTING.md                 # regole e verifiche per contribuire
├── PLAN.md                         # milestone, criteri e checklist
├── VERSION                         # versione canonica
├── pyproject.toml                  # metadata Python, senza dipendenze runtime
└── LICENSE                         # Apache License 2.0
```

`results/` nasce al primo run. `benchmark-context/` contiene la fotografia condivisa e verificata di manifesti, prompt, fixture, grader, rubriche e `EXECUTION_POLICY.snapshot.md`; `run.json` registra commit/stato Git, seed, ordine task, SHA-256, versione audit, sandbox effettiva, hardware, warmup e violazioni. Ogni tentativo contiene una `workspace/` deliberatamente modificabile dal modello, una `.benchmark-scratch/` interna ignorata da Git (profilo Seatbelt o socket del broker Linux quando applicabili), una `.pi-agent/` per-task e artefatti fratelli (`result.json`, `grade.json`, `pi-events.jsonl`, `diff.patch` e l'eventuale `manual-rubric.md`), inclusi tree baseline, audit, backend e metriche di sistema. Su Windows, metadata di cleanup e sole fasi/conteggi byte del broker vengono registrati negli artefatti runtime; il named pipe vive nel namespace AppContainer della sessione. `comparison-*` contiene `comparison.json` e `COMPARISON.md` per run compatibili. `dashboard-data-*.json` contiene soltanto i campi in whitelist destinati alla finalissima o all'importazione manuale; il dataset definitivo va congelato nella fixture `results_dashboard` e committato prima del profilo `showcase`. La dashboard ufficiale usa quella fixture come fallback in memoria e, tramite `dashboard.py`, aggrega i run locali senza esporre i file raw. `dashboard/data/snapshot.js` viene creato soltanto su richiesta per l'apertura `file://` ed è ignorato da Git. `output/playwright/` e `.playwright-cli/` sono output locali ignorati. I file sorgente sotto `cases/` non devono essere modificati durante un'esecuzione; il preflight li richiede puliti e il confronto post-task rileva cambiamenti successivi.
