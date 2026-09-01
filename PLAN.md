# Piano di sviluppo / Development Plan

Versione corrente / Current version: **0.3.0**

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
- Stato: **milestone integrata con fast-forward su `main` dopo l'approvazione esplicita del progettista. Il run standard `20260830-182507` ha individuato il diniego `realpath` degli antenati della workspace, poi corretto concedendo soltanto metadata letterali sui path autorizzati. Compileall e 40 test sono verdi; i probe macOS verificano `realpath`, sostituzione interna, lettura esterna negata e rete limitata. Dopo il diagnostico `20260830-201021`, lo smoke valido `20260830-202615` ha completato `targeted_patch` con Qwen 9B MLX a 100/100 in 151,9 s, integrità valida, Seatbelt enforced e tre tool `edit` riusciti. Le CI finali del branch (`33418463014`), della PR (`33418466714`) e di `main` (`33418580601`) sono verdi su macOS, Windows e Ubuntu. Tag `v0.2.0`, push e rimozione del branch sono autorizzati nel workflow corrente; la GitHub release non è inclusa nell'autorizzazione e resta pendente. Il confronto `comparison-m2-real-bounded`, il limite Windows audit-only accettato e il follow-up M3 restano invariati.**

### Checklist milestone 2

- [x] Branch milestone creato
- [x] Modalità audit mantenuta e dichiarata
- [x] Selezione `auto` con fallback esplicito e `required` fail-closed
- [x] Backend macOS Seatbelt con file utente e rete limitata a Ollama loopback
- [x] Backend Linux bubblewrap con filesystem e process tree isolati
- [x] Limite Windows audit-only accettato esplicitamente dal progettista per la 0.2.0
- [x] Follow-up per AppContainer Windows e isolamento rete Linux pianificato nella milestone 3
- [x] Metriche hardware, rusage e RAPL opzionale con provider/scope
- [x] Schema risultati/report 3 compatibile con lettura schema 2
- [x] Confronto statistico tra run compatibili con versione, parametri e digest verificati
- [x] Confronto reale di due run compatibili verificato (`comparison-m2-real-bounded`)
- [x] Test unitari e negativi aggiunti
- [x] Regressione Node/Pi per `realpath` e scrittura interna aggiunta; accesso esterno ancora negato
- [x] Test automatici locali completi e probe OS macOS rieseguiti dopo la correzione
- [x] Smoke diagnostico `config_i18n` (`20260830-201021`): 11 `write` riusciti senza `EPERM`; timeout e violazione modello separati dal fix
- [x] Smoke Pi/Ollama valido con sandbox reale rieseguito dopo la correzione (`20260830-202615`, 100/100, integrità valida)
- [x] CI finale macOS, Windows e Linux rieseguita dopo la correzione (push `33328347558`, PR `33328349531`)
- [x] Versione 0.2.0 sincronizzata
- [x] README e manuali aggiornati per il comportamento corrente
- [x] SECURITY_MODEL e MAP aggiornati
- [x] AGENTS e PLAN aggiornati
- [x] Approvazione esplicita del progettista prima del merge (2026-08-31)
- [x] Commit finale e merge fast-forward della PR #2 verso `main`
- [x] CI verificata sul branch (`33418463014`), sulla PR (`33418466714`) e su `main` (`33418580601`)
- [x] Tag `v0.2.0`, push e rimozione branch autorizzati dal progettista nel workflow di chiusura
- [ ] GitHub release `v0.2.0` da autorizzare, pubblicare e verificare separatamente

## Milestone 3 – Parità sandbox multipiattaforma

- Obiettivo: rendere `required` realmente enforced anche su Windows e chiudere il gap di rete del backend Linux, così che il benchmark possa essere eseguito e pubblicato con confini equivalenti e verificabili su macOS, Windows e Linux.
- Branch previsto: `milestone/3-cross-platform-sandbox`
- Incremento versione: `+0.1.0`
- Attività: prototipare e selezionare l'API Windows supportata più adatta tra AppContainer/LPAC e le API correnti di isolamento dei processi Win32; avviare Pi/Node e tutti i figli con identità e capacità minime; concedere accesso soltanto a workspace e configurazione Pi della task; negare directory utente, credenziali, registry non necessario e rete generica; progettare un trasporto locale ristretto verso Ollama senza aprire l'outbound; terminare in modo affidabile l'intero albero processi; mantenere probe, capability manifest, fallback `auto` esplicito e `required` fail-closed. Su Linux usare un network namespace bubblewrap e un proxy o trasporto locale minimo verso Ollama, eliminando la condivisione della rete host. Conservare Seatbelt macOS come regressione di riferimento e documentarne la deprecazione.
- Criteri di accettazione: `required` applica un backend OS su tutti e tre i sistemi supportati; Pi e i figli non possono leggere o scrivere fuori dalle directory concesse; la rete raggiunge soltanto il canale Ollama previsto e non Internet né altre porte locali; timeout e cancellazione terminano i discendenti; nessun backend richiede privilegi amministrativi impliciti; backend, capacità, limiti e fallback sono registrati senza sovrastimarli; un probe fallito interrompe `required` senza eseguire task.
- Test: unit e test negativi per selezione backend, ACL/capability, path assoluti, traversal, symlink/junction/reparse point, registry e rete; processi figli indiretti e sopravvissuti; porte loopback consentite e negate; probe reali Windows e Linux; smoke Pi/Ollama enforced su host Windows e Linux; regressione macOS; CI sui tre OS; verifica che gli stessi criteri di integrità e lo stesso schema report valgano per ogni backend.
- Documentazione: README e manuali bilingui, quick start dedicati Windows/Linux, `SECURITY_MODEL.md`, `MAP.md`, `AGENTS.md` e piano; prerequisiti, limiti residui e troubleshooting per ogni backend.
- Release: milestone rilasciabile con GitHub release; artifact o pacchetto installabile e checksum SHA-256 se viene introdotta distribuzione fuori checkout.
- Stato: **milestone integrata con fast-forward su `main` dopo l'approvazione esplicita del progettista del 2026-08-31. Linux usa `unshare` per un network namespace vuoto, bubblewrap per filesystem/processi e un broker Unix a destinazione Ollama fissa. Windows usa AppContainer senza capability di rete, ACL/DACL sul SID esatto, named pipe nel namespace della sessione e Job Object kill-on-close. Lo smoke Windows reale in `required` è verde nel run `20260901-133810` dopo le correzioni emerse sul runtime Pi/Node/Python, sul broker e sul tool shell; compileall e 53 test locali sono verdi (5 probe non applicabili su Windows). Le CI del branch `33425751027` e `33430691610` e la CI post-merge su `main` `33430803855` restano verdi su macOS, Ubuntu e Windows. I run benchmark Pi/Ollama reali sono stati verificati soltanto su macOS e Windows; lo smoke Linux reale non è stato eseguito, è documentato nel README ed è accettato come limite noto per il tag `v0.3.0`. Le correzioni Windows e commit, merge, tag e push sono stati approvati dal progettista il 2026-09-01; la GitHub release resta separata e non autorizzata.**

### Checklist milestone 3

- [x] Branch milestone creato (`milestone/3-cross-platform-sandbox`)
- [x] Architettura broker Ollama a destinazione fissa definita senza aprire Internet
- [x] Linux bubblewrap aggiornato con network namespace e socket Unix interno alla workspace
- [x] Windows AppContainer implementato senza capability di rete e con named pipe dedicato
- [x] Job Object Windows kill-on-close applicato prima di avviare il processo
- [x] ACL Windows temporanee limitate a workspace, configurazione Pi e runtime Pi
- [x] Probe fail-closed e fallback `auto` esplicito mantenuti
- [x] Test strutturali e negativi iniziali aggiunti
- [x] Probe reali Linux e Windows verificati in CI (`33424327842`)
- [x] Correzioni emerse dai probe multipiattaforma completate
- [x] Smoke Pi/Ollama enforced su Windows eseguito (`20260901-133810`: stato e integrità `ok`)
- [ ] Smoke Pi/Ollama enforced su Linux eseguito (non disponibile; limite noto accettato e documentato nel README)
- [x] Versione 0.3.0 sincronizzata
- [x] README, quick start, manuali, SECURITY_MODEL, MAP e AGENTS aggiornati
- [x] Compileall e 53 test rieseguiti dopo le correzioni Windows (verdi; 5 probe OS non applicabili su Windows)
- [x] CI finale del branch verificata dopo la documentazione (`33425552438`)
- [x] Approvazione esplicita del progettista prima del merge originario (2026-08-31)
- [x] Correzioni emerse dallo smoke Windows revisionate e approvate (2026-09-01)
- [x] Commit finale, merge fast-forward verso `main` e CI su `main` (`33430803855`)
- [x] Commit, merge, tag `v0.3.0` e push della chiusura Windows autorizzati (2026-09-01)
- [ ] GitHub release `v0.3.0` da autorizzare, pubblicare e verificare separatamente

## Milestone 4 – Casi personali estensibili

- Obiettivo: rendere semplice importare nuovi casi e pesi senza modificare il core.
- Branch previsto: `milestone/4-case-sdk`
- Incremento versione: `+0.1.0`
- Attività: schema manifesto per caso, validatore, template, guida autore e rubriche manuali opzionali.
- Criteri di accettazione: un nuovo caso può essere aggiunto da template e validato con un comando.
- Test: schema, casi corrotti, compatibilità report.
- Documentazione: guida bilingue e quick start autore.
- Stato: pianificata.

## Milestone 5 – Finalissima dashboard interattiva

- Obiettivo: aggiungere una prova pratica finale in cui i modelli migliori trasformano gli stessi risultati reali dei profili `smoke`, `standard` e `full` in una dashboard interattiva, offline, accessibile e verificabile, riutilizzabile in seguito come lettore dei nuovi report del benchmark.
- Branch previsto: `milestone/5-results-dashboard-showcase`
- Incremento versione: `+0.1.0`
- Attività: nuovo caso `results_dashboard` e profilo separato `showcase`; comando `dashboard-data` che riceve una o più directory di run, combina `run.json` e `report.json`, conserva profilo e provenienza e genera un unico `dashboard-data.json` tramite whitelist dei soli campi necessari; fotografia immutabile dello stesso dataset reale per tutti i finalisti; visualizzazione del funnel `smoke` → `standard` → `full`, con partecipanti e passaggi tra le fasi senza classificare automaticamente come falliti i modelli non eseguiti nelle fasi successive; classifiche per profilo, andamento dei modelli, confronto metriche, filtri, ordinamento e dettaglio task; importazione successiva di uno o più report compatibili senza ricostruire l'app; applicazione statica HTML/CSS/JavaScript senza dipendenze runtime esterne; gestione di errori, timeout, dati mancanti e stati vuoti; tema chiaro/scuro e lingua italiano/inglese con preferenze persistenti; layout responsive e accessibilità da tastiera; rubrica visuale manuale e artefatti ispezionabili.
- Criteri di accettazione: tutti i finalisti ricevono la stessa copia immutabile dei report reali selezionati e gli stessi limiti; il dataset aggregato distingue run e profili e non contiene percorsi assoluti, comandi, prompt, risposte integrali, log o altri dati non necessari; la dashboard funziona completamente offline, non modifica i dati sorgente e non contiene valori o nomi di modelli hardcoded; i dati visualizzati corrispondono ai report e nuovi report compatibili possono essere importati localmente; funnel, classifiche separate, filtri, ordinamento, dettagli, lingua e tema sono operativi; gli stati anomali sono leggibili; il grader automatico ha massimo 100 punti, mantiene la fixture iniziale sotto la soglia di completamento e verifica la generalità con un secondo dataset non fornito nel prompt; il punteggio tecnico resta distinto dalla valutazione visuale umana; workspace, patch e istruzioni di avvio restano disponibili per la revisione finale.
- Test: calibrazione del grader; unit test per aggregazione, whitelist, provenienza e compatibilità schema; verifica che l'export non includa percorsi, prompt, comandi o log; test delle trasformazioni con un dataset alternativo per rilevare valori hardcoded; test di integrazione dell'app; test browser per importazione locale, funnel, filtri, ordinamento, responsive, accessibilità di base, persistenza e assenza di richieste remote; test negativi con JSON invalido, campi mancanti, timeout e token non disponibili; smoke multipiattaforma con un modello compatibile.
- Documentazione: README, manuali bilingui, quick start della finalissima e del comando `dashboard-data`, schema del dataset aggregato, SECURITY_MODEL, MAP, AGENTS e piano; rubrica manuale documentata con criteri ripetibili.
- Stato: pianificata; da eseguire soltanto sui finalisti dopo i profili `smoke`, `standard` e `full`.
