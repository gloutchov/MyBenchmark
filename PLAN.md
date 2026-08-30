# Piano di sviluppo / Development Plan

Versione corrente / Current version: **0.1.2**

## Milestone 1 – Benchmark locale funzionale

- Obiettivo: confrontare modelli Ollama attraverso Pi con task derivati da `AGENTS.md`, grading automatico e report ispezionabile.
- Branch previsto: `milestone/1-local-benchmark`
- Incremento versione: `0.1.0`
- Attività: runner isolato, rilevamento modelli, quattro casi, grader, metriche, report, documentazione bilingue e CI.
- Criteri di accettazione: `doctor` rileva l'ambiente; un run smoke produce artefatti e report; i grader hanno massimo 100 e le fixture iniziali restano sotto 60; test unitari verdi.
- Test: compileall, unittest, doctor locale, smoke Pi/Ollama.
- Documentazione: README, manuali, security model, MAP, AGENTS e piano.
- Stato: **implementazione e verifica locale completate; il full diagnostico `20260829-120212` ha evidenziato confini incompleti e una fixture incoerente, corretti nella patch 0.1.2; la verifica reale mirata `20260829-164305` è valida; patch unita e pubblicata su `main`, CI verde su branch e `main`, tag `v0.1.2` pubblicato e branch patch rimosso; resta da eseguire il nuovo full conclusivo**.

### Checklist chiusura

- [x] Branch di lavoro creato (`patch/0.1.2-run-integrity`)
- [x] Implementazione completata
- [x] Test automatici aggiunti
- [x] Test automatici eseguiti su macOS, Windows e Ubuntu
- [x] Smoke test Pi/Ollama eseguito (timeout e grading post-mortem verificati)
- [x] Versione sincronizzata
- [x] README aggiornato
- [x] ISTRUZIONI.md aggiornato
- [x] INSTRUCTIONS.md aggiornato
- [x] SECURITY_MODEL.md aggiornato
- [x] MAP.md aggiornato
- [x] AGENTS.md aggiornato con note progetto
- [x] PLAN.md aggiornato
- [x] Approvazione esplicita del progettista per merge, tag, push e rimozione branch
- [x] Commit implementativi e documentali completati
- [x] Merge fast-forward verso `main` e push completati
- [x] CI verificata sul branch (`33260010840`) e su `main` (`33260064872`)
- [x] Tag `v0.1.2` pubblicato tramite patch di integrità
- [x] Nessuna GitHub release per la patch ordinaria; richiesti soltanto tag e push

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

## Patch prioritaria 0.1.2 – Integrità dei run e baseline congelate

- Obiettivo: impedire che una task alteri gli input dei tentativi successivi e rendere automaticamente non classificabili modelli o risultati con violazioni di workspace, baseline o provenienza.
- Branch previsto: `patch/0.1.2-run-integrity`
- Incremento versione: `+0.0.1`
- Attività principali: ripristinare `targeted_patch` dopo la modifica esterna osservata nel run `20260828-204650`; bloccare input selezionati sporchi; creare prima della matrice un solo snapshot dei file tracciati e della policy di esecuzione; registrare SHA-256 effettivi, commit/stato Git, tree baseline, seed e ordine; randomizzare le task; effettuare unload/warmup a ogni cambio modello; preparare `.benchmark-scratch/` interna e assegnarla alle variabili temporanee; confrontare repository e snapshot prima/dopo le task; risolvere path shell rispetto ai cambi directory, proteggere l'intera root, auditare tentativi di rete e distinguere traversal confinati; non eseguire grader da snapshot alterati; escludere l'intero modello per violazioni o baseline divergenti; mostrare motivo/target/evidenza; riesaminare eventi legacy; includere nella fixture `milestone_closure` la `LICENSE` richiesta da `AGENTS.md`.
- Criteri di accettazione: la baseline `targeted_patch` resta sotto 60; tutte le workspace dello stesso caso ricevono hash input effettivo e tree baseline identici; path esterni, rete o mutazioni escludono l'intero modello; un traversal di prova risolto nello scratch interno non è una violazione; pattern shell non-path come programmi `awk` non producono falsi positivi; una mutazione dello snapshot interrompe la matrice prima del grader; il report mostra stato e dettagli prima della classifica; `doctor` segnala input sporchi; lo stesso seed produce lo stesso ordine; i run precedenti vengono riesaminati senza riscrivere i risultati originali.
- Test richiesti: compileall; unittest; calibrazione diretta di tutte le fixture; test mirati per snapshot/policy hash, scratch, seed, path strutturati e shell, rete, falsi positivi `awk`, riesame report, disqualifica modello, baseline di minoranza e flusso runner simulato; `doctor`; smoke Pi/Ollama con `qwen3.8:27b-q4_K_M` e `gpt-oss:20b`; verifica reale mirata di `milestone_closure` dopo il commit correttivo.
- Documentazione: README, manuali bilingui, `SECURITY_MODEL.md`, `MAP.md`, `AGENTS.md` e `PLAN.md`.
- Release: nessuna GitHub release per questa patch ordinaria, come autorizzato dal progettista; tag `v0.1.2` pubblicato dopo merge e CI verde su `main`.
- Stato: **correzioni successive al full diagnostico implementate e committate; 24 test automatici locali e CI multipiattaforma verdi, inclusa la regressione per path assoluti di stile estraneo all'host aggiunta dopo il primo passaggio CI; il riesame in sola lettura di `20260829-120212` esclude soltanto Qwen per `/tmp`, repository reale e rete, senza falsi positivi sui pattern testuali di GPT-OSS; la verifica reale `20260829-164305` completa `milestone_closure` con Qwen a 100/100, integrità valida e scratch interno; merge e push su `main`, tag `v0.1.2` e rimozione del branch patch completati; resta da eseguire il nuovo confronto full**.

### Checklist patch 0.1.2

- [x] Branch patch creato
- [x] Fixture contaminata ripristinata e ricalibrata a 25/100
- [x] Implementazione completata
- [x] Test mirati aggiunti
- [x] Compileall e unittest locali eseguiti
- [x] Smoke reale Pi/Ollama eseguito
- [x] Full diagnostico `20260829-120212` analizzato senza modificare gli artefatti originali
- [x] `LICENSE` richiesta aggiunta alla fixture `milestone_closure`
- [x] Policy congelata e `.benchmark-scratch/` interna aggiunte
- [x] Audit path/rete versionato e report dettagliato calibrati sul full
- [x] Verifica reale `20260829-164305`: Qwen `milestone_closure` 100/100, integrità valida, 945,1 s
- [x] Versione sincronizzata
- [x] README aggiornato
- [x] ISTRUZIONI.md aggiornato
- [x] INSTRUCTIONS.md aggiornato
- [x] SECURITY_MODEL.md aggiornato
- [x] MAP.md aggiornato
- [x] AGENTS.md aggiornato
- [x] PLAN.md aggiornato
- [x] Approvazione esplicita del progettista per merge, tag, push e rimozione branch
- [x] Commit implementativi creati sul branch patch
- [x] Merge fast-forward verso `main` e push completati
- [x] CI verificata sul branch (`33260010840`) e su `main` (`33260064872`)
- [x] Tag `v0.1.2` pubblicato
- [x] Branch patch locale e remoto eliminato dopo le verifiche
- [x] Nessuna GitHub release: per questa patch ordinaria sono richiesti soltanto tag e push

## Milestone 2 – Sandbox e metriche di sistema

- Obiettivo: aggiungere un backend opzionale di isolamento OS e metriche hardware/energia dove disponibili, completando la prevenzione tecnica oltre ai controlli d'integrità introdotti nella 0.1.2.
- Branch previsto: `milestone/2-reproducibility-sandbox`
- Incremento versione: `+0.1.0`
- Attività: adapter sandbox multipiattaforma, test processi/rete e letture indirette, metriche hardware/energia, schema risultati compatibile e confronto statistico tra run. Ordine randomizzato, seed e provenienza restano la base già consegnata dalla patch 0.1.2.
- Criteri di accettazione: uscita dalla workspace bloccata tecnicamente nel backend sandbox; modalità corrente mantenuta e segnalata; report aggregato su più run.
- Test: unit, integrazione, sicurezza e smoke macOS/Windows/Linux.
- Documentazione: tutti i manuali, security model e MAP.
- Stato: **in corso sul branch `milestone/2-reproducibility-sandbox`; adapter `audit`/`auto`/`required`, backend Seatbelt e bubblewrap, metriche hardware/rusage/RAPL, schema 3 retroleggibile e comando `compare` sono implementati. I probe reali Seatbelt per lettura indiretta e rete sono verdi. Dopo il diagnostico `20260830-102245`, lo smoke reale corretto `20260830-102400` ha completato `targeted_patch` con Qwen 9B a 100/100 in 234,9 s, integrità valida, repository pulito, Seatbelt enforced, profilo hashato e metriche registrate. Restano verifica multipiattaforma CI, decisione sul limite Windows, sincronizzazione versione 0.2.0 e chiusura prima dell'avallo al merge.**

### Checklist milestone 2

- [x] Branch milestone creato
- [x] Modalità audit mantenuta e dichiarata
- [x] Selezione `auto` con fallback esplicito e `required` fail-closed
- [x] Backend macOS Seatbelt con file utente e rete limitata a Ollama loopback
- [x] Backend Linux bubblewrap con filesystem e process tree isolati
- [ ] Backend Windows AppContainer oppure limite audit-only accettato esplicitamente dal progettista
- [x] Metriche hardware, rusage e RAPL opzionale con provider/scope
- [x] Schema risultati/report 3 compatibile con lettura schema 2
- [x] Confronto statistico tra run compatibili
- [x] Test unitari e negativi aggiunti
- [x] Test automatici locali completi e probe OS macOS eseguiti
- [x] Smoke Pi/Ollama con sandbox reale eseguito (`20260830-102400`)
- [ ] CI macOS, Windows e Linux verificata
- [ ] Versione 0.2.0 sincronizzata
- [x] README e manuali aggiornati per il comportamento corrente
- [x] SECURITY_MODEL e MAP aggiornati
- [x] AGENTS e PLAN aggiornati
- [ ] Approvazione esplicita del progettista prima del merge
- [ ] Commit finale, PR/merge, CI `main`, tag `v0.2.0` e release previsti verificati

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
