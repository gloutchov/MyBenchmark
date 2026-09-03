# Finalissima: dashboard interattiva dei risultati

Trasforma il dataset sintetico `dashboard-data.json` in una dashboard statica, completa e riutilizzabile. Lavora soltanto nella workspace, non usare la rete e non aggiungere dipendenze runtime o build step: l'app deve essere HTML/CSS/JavaScript nativo e funzionare offline tramite un piccolo server statico locale.

## Esperienza richiesta

- Apri direttamente sulla dashboard utile, senza landing page.
- Rappresenta il funnel `smoke` → `standard` → `full`: mostra partecipanti, modelli proseguiti e modelli semplicemente **non eseguiti nella fase successiva**. Non chiamare questi ultimi falliti o eliminati.
- Mostra classifiche separate per profilo, andamento dei modelli tra i profili e confronto fra qualità, completamento, velocità, token, durata e le metriche opzionali CPU/energia.
- Aggiungi filtri per profilo e modello, ordinamento accessibile della classifica e dettaglio delle singole task.
- Rendi immediatamente distinguibili successo, sotto-soglia, timeout, errore, dato mancante ed esclusione per integrità.
- Non hardcodare nomi di modelli, casi, punteggi o numero dei profili. Il layout deve reggere dataset alternativi validi.
- Aggiungi un input file multiplo che importi uno o più `dashboard-data.json` compatibili, li validi e li unisca localmente senza upload. ID run duplicati con contenuto incompatibile devono produrre un errore leggibile.
- Mantieni i dati sorgente immutati. Non effettuare richieste remote, non usare CDN, font web, analytics o telemetria.

## Contratto JavaScript verificabile

Separa trasformazioni e rendering. `app.js` deve esportare sia tramite `window.LocalAgentDashboard` sia tramite `module.exports`, quando disponibile:

- `validateDashboardData(dataset)`: restituisce `true` per schema 1 valido e solleva un errore descrittivo per input invalido;
- `mergeDashboardData(datasets)`: unisce dataset validi, deduplica run identici, rifiuta collisioni e ricalcola ordine profili e funnel;
- `createDashboardView(dataset, filters)`: restituisce un oggetto con almeno `profiles`, `runs`, `leaderboard`, `funnel`, `tasks` e `availableModels`; supporta `filters.profile`, `filters.model`, `filters.sortBy` e `filters.sortDirection` senza mutare il dataset.

Il bootstrap browser deve essere protetto in modo che `require('./app.js')` funzioni anche sotto Node senza DOM.

## Lingua, tema e accessibilità

- Dizionari italiano/inglese sincronizzati; lingua automatica dal sistema (`it` solo per locale italiano, altrimenti `en`) e override persistente.
- Tema `auto`, chiaro e scuro; `auto` segue `prefers-color-scheme`; override persistente.
- Nessuna traduzione dei nomi di modelli o dei dati sorgente.
- Struttura semantica, skip link, label associate, focus visibile, stati annunciati con regioni live e navigazione completa da tastiera.
- Layout responsive senza overflow orizzontale incontrollato; tabelle leggibili anche su schermi stretti.

Aggiorna `README.md` con avvio (`python3 -m http.server`), importazione, controlli, privacy, limiti e test. Aggiungi o completa test Node senza dipendenze che coprano trasformazioni, dataset alternativo, errori e preferenze. Non modificare `dashboard-data.json` per far passare i test.
