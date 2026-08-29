# Modello di sicurezza / Security Model

## Modello operativo / Operating model

LocalAgent Benchmark verifica gli input rispetto a Git, crea una fotografia unica di prompt, fixture, grader, `AGENTS.md`, `.gitignore` e policy di esecuzione, copia quella fotografia in repository Git dedicati, avvia Pi in modalità non interattiva e usa l'API OpenAI-compatible di Ollama su loopback. Ogni tentativo ha una directory Pi separata, uno scratch interno e conserva workspace, eventi, log, patch, valutazione e audit d'integrità.

LocalAgent Benchmark checks inputs against Git, creates one frozen snapshot of prompts, fixtures, graders, `AGENTS.md`, `.gitignore`, and the execution policy, copies that snapshot into dedicated Git repositories, launches Pi non-interactively, and uses Ollama's OpenAI-compatible API over loopback. Each attempt has an isolated Pi configuration directory, an internal scratch area, and retains its workspace, events, logs, patch, grade, and integrity audit.

## Asset e confini / Assets and boundaries

- Il repository del benchmark, `AGENTS.md` e i grader sono input fidati.
- Prompt e fixture inclusi nel repository sono input controllati, ma il loro contenuto viene comunque trattato come dati per il modello.
- Le risposte del modello, gli argomenti tool e i file prodotti sono output non fidati.
- Ollama è un servizio locale separato; il confine HTTP è `ollama.url`.
- Il filesystem esterno alla workspace del singolo caso non appartiene allo scope dell'agente.

## Controlli implementati / Implemented controls

- Configurazione centrale validata all'avvio; URL e ID caso vengono controllati.
- Preflight Git obbligatorio per gli input selezionati: file modificati o non tracciati in `AGENTS.md`, `.gitignore`, prompt, fixture o grader bloccano il run.
- Snapshot condiviso creato una sola volta prima della matrice usando soltanto file tracciati da Git, con esclusione di cache/output ignorati e SHA-256 separati per istruzioni, policy di esecuzione, prompt, fixture, grader e input effettivo complessivo.
- Ogni workspace registra commit e tree Git della baseline; input o baseline divergenti vengono rilevati dal report.
- Nessuna dipendenza Python di runtime e nessun download automatico di modelli.
- Pi viene avviato con `--offline`, telemetria disabilitata e risorse globali non necessarie disabilitate; la policy bilingue preposta al prompt vieta rete e path esterni.
- `PI_CODING_AGENT_DIR` punta alla directory del run; il file provider contiene solo il placeholder Ollama, non una chiave reale.
- Ogni tentativo parte da una copia nuova e da un commit Git baseline; `.benchmark-scratch/` è interna, ignorata in Git e assegnata a `TMPDIR`, `TMP` e `TEMP`.
- Prima e dopo ogni task vengono confrontati i file Git tracciati e non ignorati del repository; le mutazioni attribuibili alla task invalidano il modello.
- L'audit versionato risolve path strutturati e argomenti shell rispetto alla workspace e ai cambi `cd` deterministici, riconosce path assoluti POSIX e Windows indipendentemente dal sistema host, distingue traversal confinati nello scratch da target esterni, protegge l'intera root del benchmark e riconosce comandi o codice di rete comuni; una violazione esclude l'intero modello dalla classifica.
- Il report mostra motivo, target ed evidenza delle violazioni e può riesaminare eventi di audit precedenti senza riscrivere i `result.json` originali.
- Lo snapshot viene ricontrollato prima e dopo ogni task; se cambia, il grader non viene eseguito e la matrice si interrompe.
- Ordine task randomizzato con seed registrato; unload e warmup sono ripetuti a ogni cambio modello.
- Timeout per task e terminazione del gruppo processo su sistemi POSIX.
- Grader eseguiti come processi separati, con timeout e senza scrittura di bytecode.
- Fixture e test non contengono segreti reali; i valori di test sensibili vengono costruiti a runtime e non stampati.
- Output sotto `results/`, escluso da Git per default.
- Ollama viene interrogato tramite URL configurato; il default è loopback HTTP.

## Segreti e logging / Secrets and logging

Il benchmark non richiede API key. Non inserire token, password, repository privati o documenti personali nei prompt o nelle fixture. Gli eventi JSONL di Pi possono contenere integralmente prompt, risposte, comandi, output tool e frammenti di file. Trattare l'intera directory `results/` come potenzialmente sensibile.

The benchmark requires no API key. Do not place tokens, passwords, private repositories, or personal documents in prompts or fixtures. Pi JSONL events may contain complete prompts, responses, commands, tool output, and file excerpts. Treat all of `results/` as potentially sensitive.

## Rete / Network

Il runner non contatta servizi Internet. `--offline` disattiva le operazioni di rete iniziali di Pi, mentre le richieste necessarie a Ollama restano locali. La policy vieta la rete e l'audit registra pattern espliciti come `curl`, `wget`, operazioni Git remote e chiamate Python HTTP/socket note. Questi controlli non sono un firewall: un comando generato dal modello può tentare accessi di rete se il sistema operativo li consente.

The runner does not contact Internet services. Pi startup networking is disabled, while required Ollama traffic remains local. The policy forbids networking, and the audit records explicit patterns such as `curl`, `wget`, remote Git operations, and known Python HTTP/socket calls. These controls are not a firewall: model-generated commands may still attempt network access when the operating system allows it.

## Filesystem e permessi / Filesystem and permissions

Pi riceve strumenti `read`, `bash`, `edit`, `write`, `grep`, `find` e `ls` perché le task richiedono modifica e test. Il working directory è confinato logicamente alla fixture e lo scratch previsto resta sotto quella root; gli sconfinamenti espliciti vengono auditati. Pi e la shell ereditano però i permessi dell'utente: non esiste ancora un sandbox OS che impedisca tecnicamente letture o scritture esterne.

Pi receives file and shell tools because tasks require editing and testing. Its working directory is logically scoped to the fixture, and the designated scratch area remains under that root; explicit escapes are audited. Pi and its shell still inherit the user's permissions: no OS sandbox currently enforces the workspace boundary.

## Validazione e processi / Validation and processes

I grader sono codice fidato versionato e vengono eseguiti dalla copia congelata soltanto dopo la verifica del relativo hash. Non aggiungere grader provenienti da terzi senza revisione: vengono eseguiti con i permessi dell'utente. I file JSON dei risultati sono prodotti localmente e non devono essere usati come comandi. Il report effettua rendering Markdown di nomi modello locali; aprirlo solo in viewer fidati se i nomi provengono da un server Ollama non controllato.

## Limiti residui / Residual risks

- Nessun isolamento OS per Pi o per i comandi shell del modello.
- L'audit post-run non è un reference monitor: comandi shell costruiti dinamicamente, espansioni non deterministiche, semantiche complesse o codice offuscato possono leggere file esterni o usare la rete senza includere un indicatore riconoscibile negli argomenti registrati; euristiche future possono anche richiedere calibrazione contro nuovi falsi positivi.
- Il confronto del repository rileva scritture a file tracciati o non ignorati, ma non letture e non file creati in aree ignorate diverse dalla directory del run.
- Le mutazioni alle sorgenti vengono rilevate e attribuite, ma non ripristinate automaticamente per preservare prove e modifiche utente; occorre revisione prima del run successivo.
- Nessun blocco di rete a livello kernel.
- Un modello può creare processi figli che sopravvivono su piattaforme dove la terminazione del gruppo non è disponibile.
- Un grader difettoso o malevolo ha accesso ai permessi dell'utente.
- Log e workspace possono occupare molto spazio o contenere dati che il modello ha letto.
- I modelli locali e Ollama sono supply-chain esterne al repository.
- Un modello può ancora tentare di manipolare `.git`, cancellare file o leggere i grader; hash, snapshot e audit invalidano i casi osservabili, ma la prevenzione completa resta affidata alla futura sandbox OS.

## Raccomandazioni / Recommendations

- Eseguire con account non privilegiato e fixture esclusivamente sintetiche.
- Usare un container o sandbox OS senza rete per casi aggiunti da fonti non fidate.
- Revisionare prompt, fixture e grader prima di ogni run.
- Non ignorare errori `inputs`, `violations_detected` o `snapshot_compromised` e non reinserire manualmente modelli esclusi nella classifica.
- Cancellare in modo consapevole i risultati non più necessari e non pubblicarli senza revisione.
- Mantenere Pi e Ollama aggiornati solo attraverso fonti verificate; registrare le versioni per confronti longitudinali.
- Non modificare il default loopback in un endpoint remoto senza consenso esplicito e documentazione dei dati inviati.

## Test di sicurezza / Security tests

Il caso `secure_workspace` controlla traversal, path assoluti, fuga via symlink, scrittura atomica e redazione. I test del runner verificano validazione configurazione, calibrazione dei grader, snapshot e policy hash, scratch interno, ordine con seed, path shell risolti in stile POSIX e Windows su ogni host, traversal confinato, pattern testuali non-path, tentativi di rete, riesame dei report, esclusione completa del modello e divergenze di baseline. Uno smoke Pi/Ollama reale ha verificato due workspace con baseline identica e integrità valida; il full diagnostico `20260829-120212` ha calibrato il nuovo audit contro `/tmp`, repository reale, rete e un falso positivo `awk`. La verifica reale `20260829-164305` ha poi completato `milestone_closure` con Qwen a 100/100 e integrità valida, usando soltanto `.benchmark-scratch/` per lo smoke e il traversal negativo. Una futura milestone deve aggiungere un backend sandbox e test specifici per processi figli, letture indirette e rete.
