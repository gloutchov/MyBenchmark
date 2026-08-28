# Piano di sviluppo / Development Plan

Versione corrente / Current version: **0.1.1**

## Milestone 1 – Benchmark locale funzionale

- Obiettivo: confrontare modelli Ollama attraverso Pi con task derivati da `AGENTS.md`, grading automatico e report ispezionabile.
- Branch previsto: `milestone/1-local-benchmark`
- Incremento versione: `0.1.0`
- Attività: runner isolato, rilevamento modelli, quattro casi, grader, metriche, report, documentazione bilingue e CI.
- Criteri di accettazione: `doctor` rileva l'ambiente; un run smoke produce artefatti e report; i grader hanno massimo 100 e le fixture iniziali restano sotto 60; test unitari verdi.
- Test: compileall, unittest, doctor locale, smoke Pi/Ollama.
- Documentazione: README, manuali, security model, MAP, AGENTS e piano.
- Stato: **implementazione in verifica; patch 0.1.1 approvata con CI verde; prove benchmark finali e avallo della Milestone 1 ancora richiesti prima della chiusura**.

### Checklist chiusura

- [ ] Branch milestone creato
- [x] Implementazione completata
- [x] Test automatici aggiunti
- [ ] Test automatici eseguiti su tutti i target CI
- [x] Smoke test Pi/Ollama eseguito (timeout e grading post-mortem verificati)
- [x] Versione sincronizzata
- [x] README aggiornato
- [x] ISTRUZIONI.md aggiornato
- [x] INSTRUCTIONS.md aggiornato
- [x] SECURITY_MODEL.md aggiornato
- [x] MAP.md aggiornato
- [x] AGENTS.md aggiornato con note progetto
- [x] PLAN.md aggiornato
- [ ] Approvazione esplicita del progettista
- [ ] Commit finale
- [ ] PR o merge verso main
- [ ] CI verificata su branch/PR e main
- [ ] Tag (non previsto per questa milestone iniziale)
- [ ] Release (non prevista per questa milestone iniziale)

## Patch prioritaria 0.1.1 – Ripristino CI e calibrazione `targeted_patch`

- Obiettivo: riportare la CI di `main` in stato verde correggendo la calibrazione iniziale del caso `targeted_patch`.
- Branch previsto: `patch/0.1.1-targeted-patch-calibration`
- Incremento versione: `+0.0.1`
- Attività: determinare se la fixture iniziale è stata completata o contaminata accidentalmente; ripristinare una baseline intenzionalmente incompleta e coerente con il prompt; verificare il grader senza ridurne copertura, punteggio massimo o soglia; mantenere fixture e grader immutati durante ogni benchmark attivo.
- Criteri di accettazione: il grader conserva un massimo di 100 punti; la fixture iniziale di `targeted_patch` ottiene meno di 60; gli altri casi mantengono la calibrazione prevista; tutti i test passano senza allentare asserzioni o soglie; la CI termina con successo su macOS, Windows e Linux.
- Test: `python3 -m compileall -q benchmark.py src cases tests`; `python3 -m unittest discover -s tests -v`; esecuzione diretta del grader sulla fixture iniziale; verifica GitHub Actions sui tre sistemi operativi.
- Documentazione: aggiornare `PLAN.md` con esito e checklist; aggiornare README, manuali, `SECURITY_MODEL.md`, `MAP.md` o `AGENTS.md` solo se il comportamento o la struttura cambiano.
- Release: nessuna GitHub release per questa patch, come approvato dal progettista; creare il tag `v0.1.1` dopo merge e CI verde su `main`.
- Stato: **correzione completata e approvata; baseline a 25/100 e CI branch/PR verde su macOS, Windows e Linux; merge e tag `v0.1.1` autorizzati**.

## Milestone 2 – Riproducibilità e sandbox

- Obiettivo: aggiungere ordine randomizzato registrato, backend opzionale di isolamento OS e metriche hardware/energia dove disponibili.
- Branch previsto: `milestone/2-reproducibility-sandbox`
- Incremento versione: `+0.1.0`
- Attività: adapter sandbox multipiattaforma, test processi/rete, schema risultati compatibile, confronto statistico tra run.
- Criteri di accettazione: uscita dalla workspace bloccata tecnicamente nel backend sandbox; modalità corrente mantenuta e segnalata; report aggregato su più run.
- Test: unit, integrazione, sicurezza e smoke macOS/Windows/Linux.
- Documentazione: tutti i manuali, security model e MAP.
- Stato: pianificata.

## Milestone 3 – Casi personali estensibili

- Obiettivo: rendere semplice importare nuovi casi e pesi senza modificare il core.
- Branch previsto: `milestone/3-case-sdk`
- Incremento versione: `+0.1.0`
- Attività: schema manifesto per caso, validatore, template, guida autore e rubriche manuali opzionali.
- Criteri di accettazione: un nuovo caso può essere aggiunto da template e validato con un comando.
- Test: schema, casi corrotti, compatibilità report.
- Documentazione: guida bilingue e quick start autore.
- Stato: pianificata.

## Milestone 4 – Finalissima dashboard interattiva

- Obiettivo: aggiungere una prova pratica finale in cui i modelli migliori trasformano gli stessi risultati reali dei profili `smoke`, `standard` e `full` in una dashboard interattiva, offline, accessibile e verificabile, riutilizzabile in seguito come lettore dei nuovi report del benchmark.
- Branch previsto: `milestone/4-results-dashboard-showcase`
- Incremento versione: `+0.1.0`
- Attività: nuovo caso `results_dashboard` e profilo separato `showcase`; comando `dashboard-data` che riceve una o più directory di run, combina `run.json` e `report.json`, conserva profilo e provenienza e genera un unico `dashboard-data.json` tramite whitelist dei soli campi necessari; fotografia immutabile dello stesso dataset reale per tutti i finalisti; visualizzazione del funnel `smoke` → `standard` → `full`, con partecipanti e passaggi tra le fasi senza classificare automaticamente come falliti i modelli non eseguiti nelle fasi successive; classifiche per profilo, andamento dei modelli, confronto metriche, filtri, ordinamento e dettaglio task; importazione successiva di uno o più report compatibili senza ricostruire l'app; applicazione statica HTML/CSS/JavaScript senza dipendenze runtime esterne; gestione di errori, timeout, dati mancanti e stati vuoti; tema chiaro/scuro e lingua italiano/inglese con preferenze persistenti; layout responsive e accessibilità da tastiera; rubrica visuale manuale e artefatti ispezionabili.
- Criteri di accettazione: tutti i finalisti ricevono la stessa copia immutabile dei report reali selezionati e gli stessi limiti; il dataset aggregato distingue run e profili e non contiene percorsi assoluti, comandi, prompt, risposte integrali, log o altri dati non necessari; la dashboard funziona completamente offline, non modifica i dati sorgente e non contiene valori o nomi di modelli hardcoded; i dati visualizzati corrispondono ai report e nuovi report compatibili possono essere importati localmente; funnel, classifiche separate, filtri, ordinamento, dettagli, lingua e tema sono operativi; gli stati anomali sono leggibili; il grader automatico ha massimo 100 punti, mantiene la fixture iniziale sotto la soglia di completamento e verifica la generalità con un secondo dataset non fornito nel prompt; il punteggio tecnico resta distinto dalla valutazione visuale umana; workspace, patch e istruzioni di avvio restano disponibili per la revisione finale.
- Test: calibrazione del grader; unit test per aggregazione, whitelist, provenienza e compatibilità schema; verifica che l'export non includa percorsi, prompt, comandi o log; test delle trasformazioni con un dataset alternativo per rilevare valori hardcoded; test di integrazione dell'app; test browser per importazione locale, funnel, filtri, ordinamento, responsive, accessibilità di base, persistenza e assenza di richieste remote; test negativi con JSON invalido, campi mancanti, timeout e token non disponibili; smoke multipiattaforma con un modello compatibile.
- Documentazione: README, manuali bilingui, quick start della finalissima e del comando `dashboard-data`, schema del dataset aggregato, SECURITY_MODEL, MAP, AGENTS e piano; rubrica manuale documentata con criteri ripetibili.
- Stato: pianificata; da eseguire soltanto sui finalisti dopo i profili `smoke`, `standard` e `full`.
