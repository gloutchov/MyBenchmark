# Modello di sicurezza / Security Model

## Modello operativo / Operating model

LocalAgent Benchmark verifica gli input rispetto a Git, crea una fotografia unica di prompt, fixture, grader, `AGENTS.md`, `.gitignore` e policy di esecuzione, copia quella fotografia in repository Git dedicati, seleziona e registra la modalità sandbox, avvia Pi in modalità non interattiva e usa l'API OpenAI-compatible di Ollama su loopback. Ogni tentativo ha una directory Pi separata, uno scratch interno e conserva workspace, eventi, log, patch, valutazione, metriche e audit d'integrità.

LocalAgent Benchmark checks inputs against Git, creates one frozen snapshot of prompts, fixtures, graders, `AGENTS.md`, `.gitignore`, and the execution policy, copies that snapshot into dedicated Git repositories, selects and records the sandbox mode, launches Pi non-interactively, and uses Ollama's OpenAI-compatible API over loopback. Each attempt has an isolated Pi configuration directory, an internal scratch area, and retains its workspace, events, logs, patch, grade, metrics, and integrity audit.

## Asset e confini / Assets and boundaries

- Il repository del benchmark, `AGENTS.md` e i grader sono input fidati.
- Prompt e fixture inclusi nel repository sono input controllati, ma il loro contenuto viene comunque trattato come dati per il modello.
- Le risposte del modello, gli argomenti tool e i file prodotti sono output non fidati.
- Ollama è un servizio locale separato; il confine HTTP è `ollama.url`.
- Il filesystem esterno alla workspace del singolo caso non appartiene allo scope dell'agente.

## Controlli implementati / Implemented controls

- Configurazione centrale validata all'avvio; URL, ID caso e modalità sandbox vengono controllati.
- Preflight Git obbligatorio per gli input selezionati: file modificati o non tracciati in `AGENTS.md`, `.gitignore`, prompt, fixture o grader bloccano il run.
- Snapshot condiviso creato una sola volta prima della matrice usando soltanto file tracciati da Git, con esclusione di cache/output ignorati e SHA-256 separati per istruzioni, policy di esecuzione, prompt, fixture, grader e input effettivo complessivo.
- Ogni workspace registra commit e tree Git della baseline; input o baseline divergenti vengono rilevati dal report.
- Nessuna dipendenza Python di runtime e nessun download automatico di modelli.
- Pi viene avviato con `--offline`, telemetria disabilitata e risorse globali non necessarie disabilitate; la policy bilingue preposta al prompt vieta rete e path esterni.
- `PI_CODING_AGENT_DIR` punta a una directory nuova per ogni task; il file provider contiene solo il placeholder Ollama, non una chiave reale. Una task non può quindi alterare la configurazione Pi di quella successiva.
- Ogni tentativo parte da una copia nuova e da un commit Git baseline; `.benchmark-scratch/` è interna, ignorata in Git e assegnata a `TMPDIR`, `TMP` e `TEMP`.
- Prima e dopo ogni task vengono confrontati i file Git tracciati e non ignorati del repository; le mutazioni attribuibili alla task invalidano il modello.
- L'audit versionato risolve path strutturati e argomenti shell rispetto alla workspace e ai cambi `cd` deterministici, riconosce path assoluti POSIX e Windows indipendentemente dal sistema host, distingue traversal confinati nello scratch da target esterni, protegge l'intera root del benchmark e riconosce comandi o codice di rete comuni. Dalla versione audit 3 separa i payload heredoc letterali dal controllo shell, continuando però a esaminare rete negli heredoc consegnati a interpreti; una violazione esclude l'intero modello dalla classifica.
- Il report mostra motivo, target ed evidenza delle violazioni e può riesaminare eventi di audit precedenti senza riscrivere i `result.json` originali.
- Lo snapshot viene ricontrollato prima e dopo ogni task; se cambia, il grader non viene eseguito e la matrice si interrompe.
- Ordine task randomizzato con seed registrato; unload e warmup sono ripetuti a ogni cambio modello.
- Timeout per task e terminazione del gruppo processo su sistemi POSIX.
- Grader eseguiti come processi separati, con timeout e senza scrittura di bytecode.
- Fixture e test non contengono segreti reali; i valori di test sensibili vengono costruiti a runtime e non stampati.
- Output sotto `results/`, escluso da Git per default.
- Ollama viene interrogato tramite URL configurato; il default è loopback HTTP.
- Tre modalità esplicite: `audit` non applica isolamento OS; `auto` usa un backend soltanto dopo un probe riuscito e registra il fallback; `required` interrompe il run se il backend non è applicabile.
- Su macOS il backend `macos-seatbelt` nega letture e scritture sotto home, volumi e directory temporanee esterne, consente soltanto il metadata `lstat` della radice home necessario a risolvere il symlink di Pi, poi abilita workspace, directory Pi e installazione Pi necessaria; la rete outbound è negata salvo la porta loopback configurata per Ollama. Il profilo e il relativo SHA-256 vengono conservati nello scratch della task. I processi figli ereditano le restrizioni.
- Su Linux `linux-bubblewrap` costruisce un mount namespace da una root vuota, monta read-only le directory runtime di sistema, monta read-write soltanto workspace e directory Pi, usa `/tmp` effimero e separa PID, IPC e UTS. La rete host resta condivisa per raggiungere Ollama ed è dichiarata non isolata.
- Backend richiesto, backend effettivo e capacità filesystem/processi/rete sono registrati sia nel manifesto sia nel risultato; il report li mostra prima della classifica.
- Hardware logico, memoria, rusage POSIX e contatori energetici Linux RAPL leggibili sono registrati con provider, scope e disponibilità; nessuna dipendenza o elevazione automatica viene introdotta.
- Il comando `compare` accetta soltanto directory distinte e run compatibili per versione/parametri, profilo, input, digest modello, backend, piattaforma e hardware e non aggrega modelli già esclusi per integrità.

## Segreti e logging / Secrets and logging

Il benchmark non richiede API key. Non inserire token, password, repository privati o documenti personali nei prompt o nelle fixture. Gli eventi JSONL di Pi possono contenere integralmente prompt, risposte, comandi, output tool e frammenti di file. Trattare l'intera directory `results/` come potenzialmente sensibile.

The benchmark requires no API key. Do not place tokens, passwords, private repositories, or personal documents in prompts or fixtures. Pi JSONL events may contain complete prompts, responses, commands, tool output, and file excerpts. Treat all of `results/` as potentially sensitive.

## Rete / Network

Il runner non contatta servizi Internet. `--offline` disattiva le operazioni di rete iniziali di Pi, mentre le richieste necessarie a Ollama restano locali. La policy vieta la rete e l'audit registra pattern espliciti come `curl`, `wget`, operazioni Git remote e chiamate Python HTTP/socket note. Seatbelt su macOS nega tecnicamente l'outbound salvo la porta loopback di Ollama. Bubblewrap usa ancora la rete host; in modalità `audit`, su Linux e su Windows l'audit non è un firewall.

The runner does not contact Internet services. Pi startup networking is disabled, while required Ollama traffic remains local. The policy forbids networking, and the audit records explicit patterns such as `curl`, `wget`, remote Git operations, and known Python HTTP/socket calls. Seatbelt on macOS technically denies outbound connections except Ollama's loopback port. Bubblewrap still uses host networking; in `audit` mode, on Linux, and on Windows, the audit is not a firewall.

## Filesystem e permessi / Filesystem and permissions

Pi riceve strumenti `read`, `bash`, `edit`, `write`, `grep`, `find` e `ls` perché le task richiedono modifica e test. Il working directory è confinato logicamente alla fixture e lo scratch previsto resta sotto quella root; gli sconfinamenti espliciti vengono sempre auditati. Con un backend applicato, Pi e i figli vengono inoltre limitati dal sistema operativo; in `audit-only` ereditano ancora i permessi dell'utente.

Pi receives file and shell tools because tasks require editing and testing. Its working directory is logically scoped to the fixture, and the designated scratch area remains under that root; explicit escapes are always audited. When a backend is applied, the OS additionally restricts Pi and its children; in `audit-only` mode they still inherit the user's permissions.

## Validazione e processi / Validation and processes

I grader sono codice fidato versionato e vengono eseguiti dalla copia congelata soltanto dopo la verifica del relativo hash. Non sono eseguiti nel backend sandbox e mantengono i permessi dell'utente: non aggiungere grader provenienti da terzi senza revisione. I file JSON dei risultati sono prodotti localmente e non devono essere usati come comandi. Il report effettua rendering Markdown di nomi modello locali; aprirlo solo in viewer fidati se i nomi provengono da un server Ollama non controllato.

## Limiti residui / Residual risks

- `audit`, il fallback di `auto` e Windows non applicano isolamento OS; il manifesto lo segnala esplicitamente.
- `sandbox-exec` è deprecato da Apple e può essere assente o rifiutare il probe; il backend non usa l'App Sandbox firmata. Directory runtime di sistema restano leggibili e la policy deve essere rivalidata dopo aggiornamenti macOS/Pi.
- Bubblewrap richiede supporto kernel/user namespace, lascia leggibili directory runtime come `/usr` e `/etc` e non isola la rete host in questa versione.
- Per scelta progettuale, la 0.2.0 non integra un backend AppContainer Windows: `audit` e `auto` restano audit-only e `required` fallisce senza fallback. Questa limitazione è accettata per la release, non equivale a isolamento OS.
- L'audit post-run non è un reference monitor: comandi shell costruiti dinamicamente, espansioni non deterministiche, semantiche complesse o codice offuscato possono leggere file esterni o usare la rete senza includere un indicatore riconoscibile negli argomenti registrati; euristiche future possono anche richiedere calibrazione contro nuovi falsi positivi.
- Il confronto del repository rileva scritture a file tracciati o non ignorati, ma non letture e non file creati in aree ignorate diverse dalla directory del run.
- Le mutazioni alle sorgenti vengono rilevate e attribuite, ma non ripristinate automaticamente per preservare prove e modifiche utente; occorre revisione prima del run successivo.
- Nessun blocco di rete a livello kernel in audit-only o nel backend Linux.
- Un modello può creare processi figli che sopravvivono su piattaforme dove la terminazione del gruppo non è disponibile.
- Un grader difettoso o malevolo ha accesso ai permessi dell'utente.
- Log e workspace possono occupare molto spazio o contenere dati che il modello ha letto.
- I modelli locali e Ollama sono supply-chain esterne al repository.
- Un modello può ancora tentare di manipolare `.git` nella propria workspace; grader e snapshot restano fuori dalle mount consentite, ma l'audit e gli hash continuano a essere necessari come controllo indipendente.
- Le metriche POSIX possono non includere completamente tutti i discendenti; i contatori RAPL sono host-wide, possono includere altri carichi e spesso non sono disponibili senza permessi aggiuntivi.

## Raccomandazioni / Recommendations

- Eseguire con account non privilegiato e fixture esclusivamente sintetiche.
- Usare `--sandbox required` per impedire fallback quando l'isolamento è requisito del run.
- Su Linux usare un ulteriore contenimento di rete esterno se le fixture non sono pienamente sintetiche.
- Revisionare prompt, fixture e grader prima di ogni run.
- Non ignorare errori `inputs`, `violations_detected` o `snapshot_compromised` e non reinserire manualmente modelli esclusi nella classifica.
- Cancellare in modo consapevole i risultati non più necessari e non pubblicarli senza revisione.
- Mantenere Pi e Ollama aggiornati solo attraverso fonti verificate; registrare le versioni per confronti longitudinali.
- Non modificare il default loopback in un endpoint remoto senza consenso esplicito e documentazione dei dati inviati.

## Test di sicurezza / Security tests

Il caso `secure_workspace` controlla traversal, path assoluti, fuga via symlink, scrittura atomica e redazione. I test del runner verificano validazione configurazione, calibrazione dei grader, snapshot e policy hash, scratch interno, ordine con seed, path shell risolti in stile POSIX e Windows su ogni host, traversal confinato, pattern testuali e payload heredoc non eseguibili, tentativi di rete anche in heredoc eseguibili, riesame dei report, esclusione completa del modello e divergenze di baseline. I test della milestone 2 coprono selezione/fallback/required, capacità non sovrastimate, profilo Seatbelt, mount bubblewrap, lettura indiretta tramite figlio, restrizione a una sola porta loopback, schema metriche e rifiuto di confronti incompatibili. I probe OS macOS sono verdi; lo smoke reale `20260830-102400` ha completato `targeted_patch` a 100/100 con integrità valida e Seatbelt enforced. Resta obbligatoria la CI macOS/Windows/Linux dopo l'audit 3 prima della chiusura.
