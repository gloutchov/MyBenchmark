# Manuale utente – LocalAgent Benchmark

## 1. Scopo

LocalAgent Benchmark confronta modelli locali Ollama quando lavorano come coding agent attraverso Pi. Ogni modello riceve input copiati dallo stesso snapshot congelato di `AGENTS.md`, prompt e fixture Git. Il risultato viene misurato con controlli automatici e conservato per revisione manuale.

## 2. Requisiti

- Python 3.10+ e Git nel `PATH`;
- Ollama installato, avviato e raggiungibile su loopback;
- Pi installato come comando `pi`;
- modelli Ollama già scaricati;
- spazio libero sufficiente per una copia delle fixture per ogni esecuzione.

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

### Selezione manuale

`--models` accetta uno o più nomi esatti mostrati da `ollama list`. `--cases` accetta gli ID elencati dal comando `list`. `--timeout` è espresso in secondi; `--output` sceglie una directory nuova o vuota. Il runner randomizza l'ordine delle task; `--seed NUMERO` permette di riprodurre esattamente lo stesso ordine, registrato anche in `run.json`.

## 5. Configurazione

`benchmark.json` contiene tutti i parametri modificabili:

- `ollama.url`: endpoint locale;
- `pi.command`: comando e argomenti iniziali di Pi;
- `models`: `installed` oppure lista stabile;
- `defaults`: timeout, ripetizioni, thinking, warmup, keep-alive, contesto, output massimo e temperatura;
- `profiles`: gruppi di casi;
- `cases`: metadati e pesi.

La configurazione viene validata all'avvio. Non contiene e non deve contenere segreti. Il valore `apiKey` generato per il provider Ollama è il placeholder letterale `ollama`, ignorato dal server locale.

## 6. Come leggere il report

Il totale combina qualità (80%), completamento (10%), velocità relativa (5%) ed efficienza token relativa (5%). Una task è completata a 60/100 con uscita Pi corretta.

Leggere prima la sezione **Integrità del run**. Un modello che accede esplicitamente fuori workspace, modifica il repository o lo snapshot, oppure riceve una baseline divergente viene escluso integralmente dalla classifica anche se il grader ha assegnato punti. Una mutazione dello snapshot interrompe le task successive. `run.json` conserva commit e stato Git iniziali, seed, ordine, hash degli input e violazioni; ogni `result.json` conserva tree della baseline e dettaglio dell'audit.

- Dare priorità a `quality_score` e ai casi più simili al proprio lavoro.
- Usare `median_duration_seconds` per capire l'attesa quotidiana.
- Usare `tool_errors` per scoprire incompatibilità nel tool calling.
- Confrontare `score_stddev` dopo almeno tre ripetizioni.
- Aprire `diff.patch` e `workspace/` prima di scegliere il modello.

Il modello primo in classifica non è automaticamente il migliore per ogni uso. Per attività security-sensitive può essere preferibile il migliore nel caso `secure_workspace`; per manutenzione ordinaria conta di più `targeted_patch`.

## 7. Riproducibilità

Usare stessa configurazione, stesso profilo, stesso numero di ripetizioni, stesso seed e stesso computer. Chiudere carichi pesanti e mantenere condizioni termiche/alimentazione comparabili. Prima di ogni cambio modello il runner scarica il modello precedente, registra un nuovo warmup e poi avvia la task, così l'ordine randomizzato non mantiene più modelli residenti involontariamente.

All'avvio `AGENTS.md`, `.gitignore`, prompt, fixture e grader selezionati devono essere puliti rispetto a Git. Il runner copia una volta in `benchmark-context/` soltanto i file tracciati, escludendo cache e output ignorati, e tutte le workspace nascono da quella fotografia; non modificare né sorgenti né snapshot durante il run. La temperatura zero limita, ma non elimina, la variabilità. Conservare l'intera directory del run quando il risultato deve essere confrontato nel tempo.

## 8. Risoluzione problemi

- `Ollama non raggiungibile`: avviare Ollama e verificare `ollama list`.
- `pi: comando non trovato`: installare Pi o modificare `pi.command` con il percorso corretto.
- `Modelli non installati`: usare il nome esatto restituito da `doctor` oppure eseguire `ollama pull` separatamente.
- `timeout`: aumentare `--timeout`; controllare anche memoria e log `stderr.log`.
- score basso con uscita corretta: leggere `grade.json`; il modello può aver risposto senza modificare i file o aver interpretato male un vincolo.
- token a zero: alcune combinazioni provider/modello non riportano usage; la qualità resta valida, mentre l'efficienza token non viene premiata.
- `Input benchmark modificati`: ripristinare o committare intenzionalmente `AGENTS.md`, `.gitignore` e i file dei casi prima di riprovare; non usare una fixture già completata.
- `violations_detected`: aprire `report.json`, `run.json` e `pi-events.jsonl`; il modello indicato è escluso e non va reinserito manualmente in classifica.
- `snapshot_compromised`: il runner ha interrotto la matrice perché la fotografia condivisa non è più affidabile; conservare gli artefatti per diagnosi e avviare un nuovo run solo dopo aver risolto la causa.

Il runner restituisce exit code `1` se una o più task terminano con errore o timeout oppure se l'integrità non è valida, ma scrive comunque il report disponibile. Uno score basso con stato `ok` e integrità `ok` è invece un risultato valido e non rende fallito il comando.

## 9. Sicurezza e privacy

Non inserire dati privati, repository reali o credenziali nelle fixture senza un ambiente isolato dedicato. `--offline` impedisce le operazioni di rete iniziali di Pi, ma non costituisce un firewall per i comandi shell emessi dal modello. Hash e audit sono controlli di rilevamento: non sostituiscono una sandbox OS. Consultare `SECURITY_MODEL.md`.

## 10. Limiti noti

- I grader automatici non misurano interamente leggibilità o qualità delle spiegazioni.
- I tempi dipendono da hardware, quantizzazione, pressione di memoria e temperatura.
- Il runner è progettato per provider Ollama; non offre ancora un adapter Codex di controllo.
- I task sono sintetici e devono essere ampliati quando cambia il tipo di lavoro abituale.
- L'audit riconosce path strutturati fuori workspace, traversal e riferimenti shell espliciti ai percorsi protetti; comandi dinamici o offuscati possono eludere il rilevamento delle sole letture finché non viene aggiunta la sandbox OS.
