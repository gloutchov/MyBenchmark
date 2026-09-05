# Finalissima dashboard / Dashboard showcase

Questa procedura prepara lo stesso dataset congelato per tutti i modelli finalisti e avvia il caso `results_dashboard`. La dashboard candidata è statica, offline e priva di dipendenze runtime. I risultati raw restano sorgenti immutabili.

This workflow prepares the same frozen dataset for every finalist and runs the `results_dashboard` case. Candidate dashboards are static, offline, and dependency-free at runtime. Raw results remain immutable sources.

## 1. Raccogliere i run / Collect runs

Completare prima `smoke`, `standard` e `full` sui modelli scelti. Conservare ogni directory completa sotto `results/`; non modificare `run.json`, `report.json` o gli artefatti delle task.

First complete `smoke`, `standard`, and `full` for the selected models. Keep every complete directory under `results/`; do not edit `run.json`, `report.json`, or task artifacts.

Per lo sviluppo del sistema, senza benchmark reale, è sufficiente validare il dataset sintetico già incluso:

For system development without a real benchmark, validate the bundled synthetic dataset:

```bash
python3 benchmark.py case validate results_dashboard
python3 -m unittest tests.test_dashboard_data -v
```

## 2. Generare il dataset ridotto / Generate the bounded dataset

Indicare una o più directory di run schema 2 o 3:

Pass one or more schema 2 or 3 run directories:

```bash
python3 benchmark.py dashboard-data \
  results/SMOKE-RUN \
  results/STANDARD-RUN \
  results/FULL-RUN \
  --output results/finalists-dashboard-data.json
```

L'esportatore legge soltanto `run.json` e `report.json`, limita ogni sorgente a 32 MiB e produce schema 1 tramite whitelist. Mantiene ID run, profilo, hash SHA-256, commit, stato sandbox/integrità, partecipanti, classifiche e metriche task necessarie. Esclude path assoluti, prompt, risposte, comandi, log, evidenze di violazione e messaggi di errore liberi. Input e output devono restare nella root del progetto; l'output non può trovarsi dentro un run sorgente. Un file esistente viene sostituito solo con `--force`, atomicamente.

The exporter reads only `run.json` and `report.json`, caps each source at 32 MiB, and emits schema 1 through a whitelist. It retains run IDs, profiles, SHA-256 hashes, commits, sandbox/integrity status, participants, leaderboards, and required task metrics. It excludes absolute paths, prompts, responses, commands, logs, violation evidence, and free-form errors. Inputs and output must stay under the project root; output cannot live inside a source run. Existing files are replaced atomically only with `--force`.

Ispezionare il JSON prima di congelarlo. Il funnel usa `continued_to_next` e `not_run_in_next`: quest'ultimo significa soltanto che il modello non compare nel profilo seguente, non che abbia fallito.

Inspect the JSON before freezing it. The funnel uses `continued_to_next` and `not_run_in_next`; the latter only means that a model does not appear in the next profile, not that it failed.

## 3. Congelare l'input della finalissima / Freeze the final input

Dopo la revisione, sostituire intenzionalmente il dataset sintetico:

After review, intentionally replace the synthetic dataset:

```bash
python3 benchmark.py dashboard-data \
  results/SMOKE-RUN results/STANDARD-RUN results/FULL-RUN \
  --output cases/results_dashboard/fixture/dashboard-data.json \
  --force
python3 benchmark.py case validate results_dashboard
```

Dopo una validazione riuscita, controllare e committare intenzionalmente la sola fixture congelata:

After successful validation, inspect and intentionally commit only the frozen fixture:

```bash
git status --short
git diff -- cases/results_dashboard/fixture/dashboard-data.json
git add -- cases/results_dashboard/fixture/dashboard-data.json
git diff --cached --name-only
git diff --cached --check
git commit -m "test: freeze showcase finalist dataset"
git status --short
```

L'elenco di `git diff --cached --name-only` deve contenere soltanto `cases/results_dashboard/fixture/dashboard-data.json`, salvo altri aggiornamenti intenzionali già revisionati. Non usare `git add .`: manifesti, prompt, grader, rubriche o modifiche estranee non devono entrare accidentalmente nel commit. L'ultimo `git status --short` non deve mostrare input protetti modificati; revisionare e committare separatamente eventuali aggiornamenti intenzionali del piano o della documentazione prima del run. Il push non è necessario per un run locale; quando serve condividere il commit o attivare la CI, eseguire `git push` sul branch corrente.

The `git diff --cached --name-only` output must contain only `cases/results_dashboard/fixture/dashboard-data.json`, unless other intentional changes have already been reviewed. Do not use `git add .`: manifests, prompts, graders, rubrics, or unrelated changes must not enter the commit accidentally. The final `git status --short` must not show modified protected inputs; review and commit any intentional plan or documentation updates separately before the run. A push is not required for a local run; when the commit must be shared or CI triggered, run `git push` on the current branch.

Il preflight richiede che `AGENTS.md`, `.gitignore`, manifesto, prompt, fixture, grader e rubrica selezionati siano puliti: così tutti i finalisti ricevono la stessa copia e lo stesso hash.

Preflight requires `AGENTS.md`, `.gitignore`, and the selected manifest, prompt, fixture, grader, and rubric to be clean, ensuring that every finalist receives the same copy and hash.

## 4. Eseguire i finalisti / Run finalists

```bash
python3 benchmark.py run \
  --profile showcase \
  --models MODEL-A MODEL-B \
  --sandbox required \
  --seed 20260903
```

Il punteggio automatico è tecnico. La rubrica visuale da 20 punti viene copiata accanto a ogni workspace ma resta esclusa dalla classifica automatica.

The automatic score is technical. The 20-point visual rubric is copied next to each workspace but remains outside the automatic leaderboard.

Un run integro resta valido anche quando nessun candidato supera 60/100. Conservare timeout, errori, punteggi sotto soglia e baseline non modificate come esiti negativi del test; non modificare il dataset o il grader per far passare un candidato.

An integrity-valid run remains valid even when no candidate exceeds 60/100. Preserve timeouts, errors, below-threshold scores, and unchanged baselines as negative test outcomes; do not modify the dataset or grader to make a candidate pass.

## 5. Revisionare la dashboard / Review the dashboard

Per ogni finalista, entrare nella relativa `workspace/` e avviare un server locale:

For each finalist, enter its `workspace/` and start a local server:

```bash
python3 -m http.server 8000
```

Aprire `http://127.0.0.1:8000/` e verificare almeno:

Open `http://127.0.0.1:8000/` and verify at least:

La dashboard dovrebbe caricare automaticamente il `dashboard-data.json` presente nella propria `workspace/`. Se richiede “Scegli file” / “Choose file”, selezionare quel file nella stessa cartella di `index.html`; non selezionare `run.json`, `report.json` o gli artefatti raw. Se il pulsante non produce alcun effetto e la pagina mostra ancora `Dashboard implementation pending`, la baseline non è stata implementata: registrare l'esito senza tentare di correggere la workspace.

The dashboard should automatically load the `dashboard-data.json` in its own `workspace/`. If it asks to “Choose file”, select that file beside `index.html`; do not select `run.json`, `report.json`, or raw artifacts. If the button has no effect and the page still shows `Dashboard implementation pending`, the baseline was not implemented: record the outcome without attempting to repair the workspace.

- desktop ampio e stretto / wide and narrow desktop;
- italiano, inglese e modalità automatica / Italian, English, and automatic language;
- tema chiaro, scuro e automatico / light, dark, and automatic theme;
- tastiera, focus visibile e annunci live / keyboard, visible focus, and live announcements;
- funnel, filtri, ordinamento e dettaglio task / funnel, filters, sorting, and task details;
- import multiplo, collisioni, JSON invalido e metriche mancanti / multi-file import, collisions, invalid JSON, and missing metrics;
- pannello Network senza richieste remote / no remote requests in the Network panel.

Annotare il giudizio in un file separato. Una dashboard non funzionante può ricevere `0/20` o “non applicabile”; resta comunque un esito valido del benchmark e non modifica i 100 punti automatici. Non modificare `grade.json`, `result.json` o il dataset congelato.

Record the assessment in a separate file. A non-functional dashboard may receive `0/20` or “not applicable”; it remains a valid benchmark outcome and does not change the 100 automatic points. Do not edit `grade.json`, `result.json`, or the frozen dataset.

## Privacy e limiti / Privacy and limitations

Il dataset ridotto può comunque rivelare nomi locali dei modelli, titoli dei casi, punteggi, tempi e hash collegabili ai run conservati. Trattarlo come dato locale potenzialmente sensibile. La whitelist riduce l'esposizione ma non rende sicura la pubblicazione automatica. La qualità visuale, il comportamento in un browser reale e la fedeltà dei dati devono essere verificati manualmente prima di scegliere la dashboard finale.

The reduced dataset may still reveal local model names, case titles, scores, timings, and hashes linkable to retained runs. Treat it as potentially sensitive local data. The whitelist reduces exposure but does not make automatic publication safe. Visual quality, real-browser behavior, and data fidelity require manual review before selecting the final dashboard.
