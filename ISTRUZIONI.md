# Manuale utente – LocalAgent Benchmark

## 1. Scopo

LocalAgent Benchmark confronta modelli locali Ollama quando lavorano come coding agent attraverso Pi. Ogni modello riceve input copiati dallo stesso snapshot congelato di `AGENTS.md`, manifesto, prompt e fixture Git. Il risultato viene misurato con controlli automatici e conservato per revisione manuale.

## 2. Requisiti

- Python 3.10+ e Git nel `PATH`;
- Ollama installato, avviato e raggiungibile su loopback;
- Pi installato come comando `pi`;
- modelli Ollama già scaricati;
- spazio libero sufficiente per una copia delle fixture per ogni esecuzione.

Per l'isolamento OS opzionale servono `sandbox-exec` utilizzabile su macOS; `bwrap`, `unshare` e user/network namespace utilizzabili su Linux; oppure Windows 10/11 con AppContainer. `doctor` esegue un probe reale e mostra disponibilità, backend e capacità effettive senza installare componenti. Le procedure specifiche sono in [QUICK-START_Linux.md](QUICK-START_Linux.md) e [QUICK-START_Windows.md](QUICK-START_Windows.md).

Verificare l'ambiente:

```bash
python3 benchmark.py doctor
```

Il comando mostra versioni, controlli falliti, modelli rilevati e stato di pulizia degli input senza eseguire task agentici.

## 3. Primo avvio

Elencare profili, casi e modelli:

```bash
python3 benchmark.py list
```

Eseguire un solo caso su un modello piccolo per verificare il tool calling:

```bash
python3 benchmark.py run --profile smoke --models qwen3.5:9b-Q4_K_M
```

Se il modello termina e produce un report, passare al profilo standard:

```bash
python3 benchmark.py run --profile standard
```

## 4. Flussi principali

### Confronto rapido

Usare `smoke` con tutti i modelli. Serve soprattutto a individuare modelli che non emettono correttamente chiamate agli strumenti.

### Confronto ordinario

Usare `standard`: comprende una patch mirata, un hardening di sicurezza e una funzionalità di configurazione/i18n.

### Scelta finale

Usare `full --repetitions 3` soltanto sui finalisti. Il quarto caso verifica branch, versione, documentazione, piano e stop prima del merge.

Quando i finalisti sono definiti, usare il profilo separato `showcase`: il caso `results_dashboard` chiede a ciascun modello di costruire una dashboard statica dallo stesso dataset congelato. Non aggiungere il caso ai profili precedenti, perché la valutazione visuale deve restare una finalissima distinta.

### Selezione manuale

`--models` accetta uno o più nomi esatti mostrati da `ollama list`. `--cases` accetta gli ID elencati dal comando `list`. `--timeout` è espresso in secondi; `--output` sceglie una directory nuova o vuota. Il runner randomizza l'ordine delle task; `--seed NUMERO` permette di riprodurre esattamente lo stesso ordine, registrato anche in `run.json`. `--sandbox` accetta `audit`, `auto` o `required`: `required` è la scelta corretta quando il run non deve continuare senza isolamento OS.

### Confronto statistico tra run

```bash
python3 benchmark.py compare results/RUN-1 results/RUN-2 results/RUN-3
```

Il confronto accetta soltanto directory distinte e run con versione/parametri, profilo, casi, fingerprint input, digest modello, backend sandbox, piattaforma e hardware registrato compatibili. Genera `comparison.json` e `COMPARISON.md` con media, mediana, deviazione standard e intervallo al 95% approssimato, limitato al dominio naturale della metrica. I modelli assenti o esclusi per integrità non ricevono un campione per quel run.

### Dataset e finalissima dashboard

Per testare il sistema senza un benchmark Pi/Ollama reale:

```bash
python3 -m unittest tests.test_dashboard_data -v
python3 benchmark.py case validate results_dashboard
```

Dopo i run reali, aggregare profili anche diversi con il comando dedicato, non con `compare`:

```bash
python3 benchmark.py dashboard-data \
  results/SMOKE-RUN results/STANDARD-RUN results/FULL-RUN \
  --output results/finalists-dashboard-data.json
```

Il comando accetta `run.json` e `report.json` schema 2 o 3, con massimo 32 MiB per file. Produce schema dashboard 1, registra hash e commit e usa una whitelist: mantiene soltanto profilo, sandbox, integrità sintetica, partecipanti, classifiche e metriche task. Non copia path, prompt, risposte, comandi, log, evidenze di violazione o messaggi di errore liberi. Input e output devono restare nella root del progetto; non è consentito scrivere dentro un run sorgente. Per sostituire atomicamente un output già esistente aggiungere `--force`.

Revisionare il JSON, quindi congelarlo nella fixture:

```bash
python3 benchmark.py dashboard-data \
  results/SMOKE-RUN results/STANDARD-RUN results/FULL-RUN \
  --output cases/results_dashboard/fixture/dashboard-data.json \
  --force
python3 benchmark.py case validate results_dashboard
```

Committare l'input prima del run, poi eseguire soltanto i finalisti con `python3 benchmark.py run --profile showcase --models MODEL-A MODEL-B --sandbox required`. Il runner consegna la stessa fotografia a tutti. Il grader tecnico vale 100 punti e usa anche un dataset nascosto; la rubrica visuale da 20 punti resta manuale e separata. Per avvio locale, import multiplo e checklist browser seguire [QUICK-START_Showcase.md](QUICK-START_Showcase.md).

## 5. Configurazione

`benchmark.json` contiene tutti i parametri modificabili:

- `ollama.url`: endpoint locale;
- `pi.command`: comando e argomenti iniziali di Pi;
- `models`: `installed` oppure lista stabile;
- `defaults`: timeout, ripetizioni, thinking, warmup, keep-alive, contesto, output massimo, temperatura e modalità sandbox;
- `profiles`: gruppi di casi;
- `cases.directory`: directory, interna al repository, da cui scoprire i manifesti `case.json`.

La configurazione viene validata all'avvio. Non contiene e non deve contenere segreti. Il valore `apiKey` generato per il provider Ollama è il placeholder letterale `ollama`, ignorato dal server locale.

### Creazione e validazione di casi personali

Creare uno scheletro autocontenuto:

```bash
python3 benchmark.py case create api_contract \
  --title-it "Contratto API" \
  --title-en "API contract" \
  --category architecture \
  --weight 1.25 \
  --manual-rubric
```

Il comando crea `case.json`, `prompt.md`, `fixture/`, `grader.py` e, se richiesta, `manual-rubric.md`. I metadati e il peso vivono nel manifesto; per eseguire il caso non serve modificare il core. Aggiungere l'ID a un profilo di `benchmark.json` soltanto se deve far parte stabilmente di quel gruppo.

Dopo aver personalizzato materiali sintetici e controlli, validare il caso:

```bash
python3 benchmark.py case validate api_contract
```

Senza ID, `case validate` controlla tutti i casi. Verifica schema strutturale, path confinati, file richiesti, contratto JSON del grader, somma di 100 punti e baseline sotto 60. Il grader viene eseguito con i permessi dell'utente e fuori dalla sandbox dell'agente: revisionare sempre il codice dei casi importati prima della validazione. La guida completa è in [QUICK-START_Case-Author.md](QUICK-START_Case-Author.md).

## 6. Come leggere il report

Il totale combina qualità (80%), completamento (10%), velocità relativa (5%) ed efficienza token relativa (5%). Una task è completata a 60/100 con uscita Pi corretta.

Leggere prima **Ambiente e isolamento** e **Integrità del run**. La prima sezione distingue backend richiesto ed effettivo e non presenta il fallback come sandbox. Un modello che riferisce esplicitamente un path risolto fuori workspace, tenta la rete, modifica il repository o lo snapshot, oppure riceve una baseline divergente viene escluso integralmente dalla classifica anche se il grader ha assegnato punti. Una mutazione dello snapshot interrompe le task successive. Il report elenca modello, caso, ripetizione, motivo, target ed evidenza; `run.json` conserva hardware, sandbox, commit e stato Git iniziali, seed, ordine, hash degli input e della policy, e violazioni. Ogni `result.json` conserva tree della baseline, versione dell'audit, metriche di sistema e dettagli originali.

- Dare priorità a `quality_score` e ai casi più simili al proprio lavoro.
- Usare `median_duration_seconds` per capire l'attesa quotidiana.
- Usare `tool_errors` per scoprire incompatibilità nel tool calling.
- Confrontare `score_stddev` dopo almeno tre ripetizioni.
- Trattare energia RAPL come misura host-wide: è utile soltanto a parità di macchina e carico, non come consumo esclusivo del modello.
- Aprire `diff.patch` e `workspace/` prima di scegliere il modello.
- Se esiste `manual-rubric.md`, compilarla separatamente: non entra nel punteggio automatico.

Il modello primo in classifica non è automaticamente il migliore per ogni uso. Per attività security-sensitive può essere preferibile il migliore nel caso `secure_workspace`; per manutenzione ordinaria conta di più `targeted_patch`.

## 7. Riproducibilità

Usare stessa configurazione, stesso profilo, stesso numero di ripetizioni, stesso seed e stesso computer. Chiudere carichi pesanti e mantenere condizioni termiche/alimentazione comparabili. Prima di ogni cambio modello il runner scarica il modello precedente, registra un nuovo warmup e poi avvia la task, così l'ordine randomizzato non mantiene più modelli residenti involontariamente.

All'avvio `AGENTS.md`, `.gitignore`, manifesti, prompt, fixture, grader e rubriche selezionati devono essere puliti rispetto a Git. Il runner copia una volta in `benchmark-context/` soltanto i file tracciati e la policy di esecuzione, escludendo cache e output ignorati, e tutte le workspace nascono da quella fotografia. Gli hash degli input includono anche manifesto e rubrica. Ogni workspace contiene `.benchmark-scratch/`, ignorata da Git e usata anche come `TMPDIR`, `TMP` e `TEMP`: i modelli devono usarla per smoke test e file temporanei senza ricorrere a `/tmp`. Non modificare né sorgenti né snapshot durante il run. La temperatura zero limita, ma non elimina, la variabilità. Conservare l'intera directory del run quando il risultato deve essere confrontato nel tempo.

## 8. Risoluzione problemi

- `Ollama non raggiungibile`: avviare Ollama e verificare `ollama list`.
- `pi: comando non trovato`: installare Pi o modificare `pi.command` con il percorso corretto.
- `Modelli non installati`: usare il nome esatto restituito da `doctor` oppure eseguire `ollama pull` separatamente.
- `timeout`: aumentare `--timeout`; controllare anche memoria e log `stderr.log`.
- score basso con uscita corretta: leggere `grade.json`; il modello può aver risposto senza modificare i file o aver interpretato male un vincolo.
- token a zero: alcune combinazioni provider/modello non riportano usage; la qualità resta valida, mentre l'efficienza token non viene premiata.
- `Input benchmark modificati`: ripristinare o committare intenzionalmente `AGENTS.md`, `.gitignore` e i file dei casi prima di riprovare; non usare una fixture già completata.
- `Manifesto mancante` o `paths.*`: completare `case.json`, usare soltanto path relativi POSIX interni al caso e rimuovere symlink sui path dichiarati; rieseguire `case validate`.
- errore `max_score`, `points`, `earned` o baseline: correggere il contratto del grader; i check devono totalizzare 100 e la fixture iniziale deve restare sotto 60.
- errore `dashboard-data`: verificare schema 2/3, coerenza del profilo, directory distinte e path interni alla root; usare `--force` soltanto dopo aver revisionato il file da sostituire.
- `violations_detected`: leggere prima la tabella **Violazioni rilevate**, poi aprire `report.json`, `run.json` e il relativo `pi-events.jsonl`; il modello indicato è escluso e non va reinserito manualmente in classifica. La rigenerazione del report applica l'audit corrente agli eventi più vecchi senza cambiare i `result.json` originali.
- `snapshot_compromised`: il runner ha interrotto la matrice perché la fotografia condivisa non è più affidabile; conservare gli artefatti per diagnosi e avviare un nuovo run solo dopo aver risolto la causa.
- `Sandbox OS richiesta ma non disponibile`: installare/abilitare il backend indicato da `doctor`, usare consapevolmente `--sandbox auto` per consentire fallback oppure `--sandbox audit` per il comportamento storico.
- `linux-bubblewrap` non disponibile: verificare `bwrap`, `unshare` e la policy di user namespace seguendo il quick start Linux; non eseguire il benchmark come root per aggirare il probe.
- `windows-appcontainer` non disponibile: eseguire `doctor` come utente standard e verificare ACL, profilo AppContainer e named pipe seguendo il quick start Windows.

Il runner restituisce exit code `1` se una o più task terminano con errore o timeout oppure se l'integrità non è valida, ma scrive comunque il report disponibile. Uno score basso con stato `ok` e integrità `ok` è invece un risultato valido e non rende fallito il comando.

## 9. Sicurezza e privacy

Non inserire dati privati, repository reali o credenziali nelle fixture. Manifesti e template non concedono permessi: un grader importato resta codice non fidato finché non viene revisionato, perché validazione e grading lo eseguono sul processo host. `audit` e il fallback di `auto` non sono sandbox. Il backend macOS restringe file utente esterni e rete salvo Ollama loopback ed è basato sulla deprecata interfaccia `sandbox-exec`. Su Linux Pi opera in un network namespace vuoto e raggiunge soltanto il broker Ollama tramite un socket Unix interno alla workspace. Su Windows AppContainer non riceve capability di rete e usa un named pipe dedicato al suo SID; ACL temporanee concedono solo i path necessari e un Job Object termina i discendenti. Broker e grader restano processi fidati eseguiti fuori sandbox. Il dataset dashboard omette contenuti raw ma conserva nomi modello, titoli, metriche e hash: resta un file locale potenzialmente sensibile e non deve essere pubblicato automaticamente. Consultare `SECURITY_MODEL.md`.

## 10. Limiti noti

- I grader automatici non misurano interamente leggibilità o qualità delle spiegazioni.
- Le rubriche manuali sono artefatti di supporto: il runner non raccoglie né aggrega il punteggio umano.
- I tempi dipendono da hardware, quantizzazione, pressione di memoria e temperatura.
- Il runner è progettato per provider Ollama; non offre ancora un adapter Codex di controllo.
- I task sono sintetici e devono essere ampliati quando cambia il tipo di lavoro abituale.
- Il backend Linux dipende da user/network namespace non privilegiati; su host con policy kernel o AppArmor più restrittive il probe fallisce e `required` interrompe il run.
- AppContainer concede lettura al runtime Pi e applica/rimuove ACL e profilo in best effort; un arresto anomalo del launcher può richiedere pulizia o diagnosi manuale.
- Il broker inoltra soltanto alla destinazione Ollama configurata, ma non autentica né filtra semanticamente il contenuto delle richieste.
- Comandi dinamici o offuscati possono ancora eludere l'audit quando non è attivo un backend enforced.
- `sandbox-exec` è deprecato e può non essere disponibile in future versioni macOS; `required` evita fallback silenziosi.
- Le metriche POSIX possono non includere integralmente tutti i discendenti; RAPL misura il sistema host e può non essere leggibile senza privilegi.
- Il grader della dashboard verifica trasformazioni e requisiti osservabili, ma responsive, resa visuale, tastiera e assenza di richieste remote richiedono anche una prova in browser e la rubrica manuale sul workspace candidato.
