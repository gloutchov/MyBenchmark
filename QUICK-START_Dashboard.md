# Dashboard ufficiale / Official results dashboard

Questa guida riguarda la dashboard mantenuta dal progetto in `dashboard/`. La dashboard candidata costruita dai modelli nel profilo `showcase` è invece una prova separata: un risultato da valutare, non l'interfaccia ufficiale.

This guide covers the project-maintained dashboard in `dashboard/`. The candidate dashboard built by models in the `showcase` profile is a separate test outcome, not the official interface.

## Apertura immediata / Open immediately

Fare doppio clic su `dashboard/index.html`, oppure aprirlo dal browser. La pagina funziona senza server e mostra lo snapshot pubblico revisionato incluso nel repository.

Double-click `dashboard/index.html`, or open it from the browser. The page works without a server and displays the reviewed public snapshot bundled with the repository.

Questa modalità non cerca automaticamente i run più recenti. Per quelli usare il launcher Python.

This mode does not discover newer runs automatically. Use the Python launcher for those.

## Risultati locali correnti / Current local results

Dalla root del repository:

From the repository root:

```bash
python3 dashboard.py
```

Il launcher:

- cerca le directory compatibili direttamente sotto `results/`;
- costruisce in memoria lo stesso dataset ridotto di `dashboard-data`;
- serve soltanto gli asset autorizzati e il dataset pubblico su `127.0.0.1`;
- sceglie una porta libera, apre il browser e stampa l'URL;
- non modifica i run, non crea export e non espone i file raw.

The launcher discovers compatible directories directly below `results/`, builds the sanitized dataset in memory, serves only allowlisted assets and public data on `127.0.0.1`, selects an available port, and opens the browser. It neither modifies runs nor creates exports or serves raw files.

Terminare con `Ctrl+C`. Se non viene trovato alcun run compatibile, la dashboard usa lo snapshot incluso.

Stop it with `Ctrl+C`. If no compatible run is found, the dashboard uses the bundled snapshot.

## Sorgenti esplicite / Explicit sources

Selezionare run specifici:

Select specific runs:

```bash
python3 dashboard.py \
  results/SMOKE-RUN \
  results/STANDARD-RUN \
  results/FULL-RUN
```

Aprire un export pubblico già creato:

Open an existing public export:

```bash
python3 dashboard.py --dataset results/finalists-dashboard-data.json
```

Non aprire automaticamente il browser o scegliere una porta:

Do not open the browser automatically, or choose a port:

```bash
python3 dashboard.py --no-open
python3 dashboard.py --no-open --port 8765
```

I path devono restare nella root del progetto. `--dataset` e le directory di run sono alternative. La porta `0`, usata per default, sceglie automaticamente una porta disponibile.

Paths must remain inside the project root. `--dataset` and positional run directories are mutually exclusive. Port `0`, the default, automatically selects an available port.

## Quale file scegliere / Which file to choose

Il controllo **Scegli file / Choose files** della pagina accetta soltanto file `dashboard-data.json` compatibili. Non selezionare:

The page's **Scegli file / Choose files** control accepts compatible `dashboard-data.json` files only. Do not select:

- `run.json`;
- `report.json` o `REPORT.md`;
- `result.json`, `grade.json`, log o patch;
- una directory completa di run;
- lo snapshot JavaScript `dashboard/data/snapshot.js`.

Creare prima il file corretto con:

First create the correct file with:

```bash
python3 benchmark.py dashboard-data \
  results/SMOKE-RUN results/STANDARD-RUN results/FULL-RUN \
  --output results/finalists-dashboard-data.json
```

Revisionare il JSON e poi selezionare `results/finalists-dashboard-data.json`. È possibile scegliere più export insieme: run identici vengono deduplicati, mentre ID uguali con contenuti diversi vengono rifiutati. Ogni file può occupare al massimo 32 MiB.

Review the JSON, then select `results/finalists-dashboard-data.json`. Multiple exports may be selected together: identical runs are deduplicated, while matching IDs with different contents are rejected. Each file is capped at 32 MiB.

L'importazione resta nella memoria della scheda del browser. Non invia dati, non scrive file e si annulla ricaricando la pagina. Solo lingua e tema vengono memorizzati come preferenze locali.

Imports remain in the browser tab's memory. No data is uploaded and no file is written; reload the page to discard imported data. Only language and theme are retained as local preferences.

## Aggiornare lo snapshot incluso / Refresh the bundled snapshot

Questa operazione è destinata ai maintainer e non serve per leggere nuovi run. Prima aggiornare e revisionare `cases/results_dashboard/fixture/dashboard-data.json`, poi eseguire:

This maintainer operation is not needed to view new runs. First update and review `cases/results_dashboard/fixture/dashboard-data.json`, then run:

```bash
python3 dashboard.py --refresh-snapshot --force
node --test dashboard/tests/dashboard.test.js
git diff -- dashboard/data/snapshot.js
```

Committare lo snapshot soltanto se riproduce esattamente la fixture pubblica revisionata. Il launcher normale non esegue mai questa scrittura.

Commit the snapshot only when it exactly reproduces the reviewed public fixture. Normal launcher operation never performs this write.

## Risoluzione problemi / Troubleshooting

- **Vedo lo snapshot invece dei run nuovi / I see the snapshot instead of new runs**: `index.html` aperto direttamente usa intenzionalmente lo snapshot; avviare `python3 dashboard.py`.
- **Il browser non si apre / The browser does not open**: usare `python3 dashboard.py --no-open` e aprire l'URL stampato.
- **Porta occupata / Port already in use**: omettere `--port`, usare `--port 0` o scegliere un altro numero.
- **Run ignorato / Run skipped**: verificare che la directory immediatamente sotto `results/` contenga `run.json` e `report.json` schema 2 o 3 compatibili. Passarla esplicitamente per ottenere un errore dettagliato.
- **File rifiutato / File rejected**: verificare che sia un export schema dashboard 1 creato da `dashboard-data`, non un report raw, e che non superi 32 MiB.
- **Il browser limita `file://` / Browser restricts `file://`**: usare `python3 dashboard.py`; la UI resta identica e opera soltanto su loopback.

## Privacy

La dashboard non usa CDN, telemetria, API o asset remoti. Lo snapshot e gli export omettono prompt, risposte, comandi, log, path assoluti, evidenze di violazione ed errori liberi. Conservano però nomi modello, titoli dei casi, punteggi, tempi, metriche e hash: revisionarli prima della condivisione.

The dashboard uses no CDN, telemetry, API, or remote asset. The snapshot and exports omit prompts, responses, commands, logs, absolute paths, violation evidence, and free-form errors. They still retain model names, case titles, scores, timings, metrics, and hashes; review them before sharing.
