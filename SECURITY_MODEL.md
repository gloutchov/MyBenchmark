# Modello di sicurezza / Security Model

## Modello operativo / Operating model

LocalAgent Benchmark scopre i casi tramite manifesti locali, verifica gli input rispetto a Git, crea una fotografia unica di manifesti, prompt, fixture, grader, rubriche opzionali, `AGENTS.md`, `.gitignore` e policy di esecuzione, copia quella fotografia in repository Git dedicati, seleziona e registra la modalità sandbox, avvia Pi in modalità non interattiva e usa l'API OpenAI-compatible di Ollama su loopback. Ogni tentativo ha una directory Pi separata, uno scratch interno e conserva workspace, eventi, log, patch, valutazione, metriche e audit d'integrità.

LocalAgent Benchmark discovers cases through local manifests, checks inputs against Git, creates one frozen snapshot of manifests, prompts, fixtures, graders, optional rubrics, `AGENTS.md`, `.gitignore`, and the execution policy, copies that snapshot into dedicated Git repositories, selects and records the sandbox mode, launches Pi non-interactively, and uses Ollama's OpenAI-compatible API over loopback. Each attempt has an isolated Pi configuration directory, an internal scratch area, and retains its workspace, events, logs, patch, grade, metrics, and integrity audit.

## Asset e confini / Assets and boundaries

- Il repository del benchmark, `AGENTS.md` e i grader sono input fidati.
- Prompt e fixture inclusi nel repository sono input controllati, ma il loro contenuto viene comunque trattato come dati per il modello.
- Manifesti e rubriche descrivono il caso ma non concedono fiducia o permessi. Un grader importato è codice non fidato finché non viene revisionato; validazione e grading lo eseguono sul processo host.
- Le risposte del modello, gli argomenti tool e i file prodotti sono output non fidati.
- Ollama è un servizio locale separato; il confine HTTP è `ollama.url`.
- Il filesystem esterno alla workspace del singolo caso non appartiene allo scope dell'agente.

## Controlli implementati / Implemented controls

- Configurazione centrale validata all'avvio; URL, ID caso e modalità sandbox vengono controllati.
- Discovery limitata a figli diretti della directory casi configurata, che deve restare nel repository. I manifesti sono limitati a 64 KiB; il validatore rifiuta ID non portabili o discordanti, campi sconosciuti, pesi non finiti, path assoluti/Windows/traversal, path dichiarati sovrapposti, attraversamento di symlink e symlink della fixture che escono dal caso.
- `case create` usa una directory di staging interna e una rinomina atomica, rifiuta target esistenti e non sovrascrive casi.
- `case validate` controlla il protocollo JSON del grader, ID check univoci, massimo e somma punti a 100, intervalli earned, coerenza score e fixture iniziale sotto 60.
- Preflight Git obbligatorio per gli input selezionati: file modificati o non tracciati in `AGENTS.md`, `.gitignore`, manifesti, prompt, fixture, grader o rubriche bloccano il run.
- Snapshot condiviso creato una sola volta prima della matrice usando soltanto file tracciati da Git, con esclusione di cache/output ignorati e SHA-256 separati per istruzioni, policy di esecuzione, manifesto, prompt, fixture, grader, rubrica e input effettivo complessivo.
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
- Su macOS il backend `macos-seatbelt` nega letture e scritture sotto home, volumi e directory temporanee esterne, poi abilita workspace, directory Pi e installazione Pi necessaria. Per consentire a Node/Pi di risolvere con `realpath` questi path, abilita `file-read-metadata` soltanto sui loro singoli antenati protetti: la regola è letterale e non concede listing, lettura dei contenuti o scrittura nelle directory antenate. La rete outbound è negata salvo la porta loopback configurata per Ollama. Il profilo e il relativo SHA-256 vengono conservati nello scratch della task. I processi figli ereditano le restrizioni.
- Su Linux `linux-bubblewrap` viene avviato da `unshare` in user e network namespace nuovi. Costruisce un mount namespace da una root vuota, monta read-only le directory runtime di sistema, monta read-write soltanto workspace e directory Pi, usa `/tmp` effimero, separa PID, IPC e UTS e rimuove le capability. Il namespace di rete non espone interfacce configurate; un broker host a destinazione fissa inoltra dallo Unix socket nella workspace esclusivamente all'host e alla porta Ollama configurati.
- Su Windows `windows-appcontainer` crea un profilo senza capability di rete e copia il bundle CLI di Pi, Node e un runtime Python standard-library ridotto in un runtime per-task. Nella sola copia staged sostituisce il backend del tool shell di Pi con `cmd.exe /d /v:on /s /c`, aggiorna il relativo prompt alla sintassi Windows, riusa gli handle standard ereditati invece di creare pipe o handle `NUL` tramite libuv e cattura stdout/stderr e l'`ERRORLEVEL` precedente al teardown in due file univoci sotto `.benchmark-scratch`, poi letti e cancellati: evita sia il deadlock delle pipe anonime osservato con Node 24 sia `spawn EPERM` sugli handle ignorati osservato con Node 22, e distingue l'esito del comando da un crash `cmd.exe` durante il teardown AppContainer. I marker devono corrispondere esattamente o il run fallisce prima di creare il profilo. Concede ACL temporanee ricorsive al SID esatto del container soltanto su workspace, directory Pi e runtime staged, senza modificare le ACL delle installazioni di sistema o degli antenati. `cmd.exe` è un binario di sistema AppContainer-safe e i suoi figli ereditano il token ristretto. Avvia quindi il processo sospeso, lo assegna a un Job Object `kill-on-close` e poi lo riprende. Un named pipe creato nel namespace della sessione AppContainer e protetto da DACL inoltra tramite un broker host soltanto alla destinazione Ollama configurata. Profilo, ACL, runtime staged e pipe vengono rimossi in best effort; hash del bundle Pi staged, tool copiati, backend shell, fasi e conteggi byte del broker, mai i payload, sono registrati nei metadata runtime.
- Backend richiesto, backend effettivo e capacità filesystem/processi/rete sono registrati sia nel manifesto sia nel risultato; il report li mostra prima della classifica.
- Hardware logico, memoria, rusage POSIX e contatori energetici Linux RAPL leggibili sono registrati con provider, scope e disponibilità; nessuna dipendenza o elevazione automatica viene introdotta.
- Il comando `compare` accetta soltanto directory distinte e run compatibili per versione/parametri, profilo, input, digest modello, backend, piattaforma e hardware e non aggrega modelli già esclusi per integrità.
- `dashboard-data` accetta soltanto `run.json` e `report.json` schema 2/3 entro 32 MiB, richiede input e output nella root del progetto, rifiuta directory duplicate, profili incoerenti e output dentro un run sorgente. L'output viene scritto atomicamente e non viene sovrascritto senza `--force`.
- L'export dashboard usa una whitelist: conserva ID/profilo, hash SHA-256, commit, capacità sandbox, stato d'integrità sintetico, modelli, classifiche e metriche task. Non copia path assoluti, prompt, risposte, comandi, log, dettagli/evidenze delle violazioni o errori testuali liberi.
- Il caso `results_dashboard` usa una fixture sintetica congelata, JavaScript statico senza dipendenze o rete e una rubrica visuale separata. Il grader tecnico verifica un secondo dataset non visibile nella workspace per rilevare implementazioni hardcoded.
- Una rubrica manuale dichiarata viene copiata come artefatto fratello della workspace e marcata come esclusa dallo score automatico; il runner non accetta né aggrega punteggi umani.

## Segreti e logging / Secrets and logging

Il benchmark non richiede API key. Non inserire token, password, repository privati o documenti personali nei prompt o nelle fixture. Gli eventi JSONL di Pi possono contenere integralmente prompt, risposte, comandi, output tool e frammenti di file. Trattare l'intera directory `results/` come potenzialmente sensibile.

The benchmark requires no API key. Do not place tokens, passwords, private repositories, or personal documents in prompts or fixtures. Pi JSONL events may contain complete prompts, responses, commands, tool output, and file excerpts. Treat all of `results/` as potentially sensitive. Dashboard exports omit raw content but still expose local model names, case titles, scores, timings, and hashes that can be linked to retained source runs; review them before sharing.

## Rete / Network

Il runner non contatta servizi Internet. `--offline` disattiva le operazioni di rete iniziali di Pi, mentre le richieste necessarie a Ollama restano locali. La policy vieta la rete e l'audit registra pattern espliciti come `curl`, `wget`, operazioni Git remote e chiamate Python HTTP/socket note. Seatbelt su macOS nega tecnicamente l'outbound salvo la porta loopback di Ollama. Su Linux il processo confinato non condivide la rete host e raggiunge il broker solo tramite socket Unix; su Windows AppContainer non riceve capability di rete e raggiunge il broker solo tramite named pipe. I broker sono processi host fidati vincolati all'unica destinazione configurata. In modalità `audit` e nel fallback di `auto`, l'audit non è un firewall.

The runner does not contact Internet services. Pi startup networking is disabled, while required Ollama traffic remains local. The policy forbids networking, and the audit records explicit patterns such as `curl`, `wget`, remote Git operations, and known Python HTTP/socket calls. Seatbelt on macOS technically denies outbound connections except Ollama's loopback port. On Linux, the confined process does not share host networking and reaches the broker only through a Unix socket; on Windows, AppContainer receives no network capabilities and reaches it only through a named pipe. Brokers are trusted host processes pinned to the single configured destination. In `audit` mode and the `auto` fallback, the audit is not a firewall. `dashboard-data` performs only local file reads and writes; candidate dashboards must use local JSON files and cannot use remote assets, telemetry, or APIs.

## Filesystem e permessi / Filesystem and permissions

Pi riceve strumenti `read`, `bash`, `edit`, `write`, `grep`, `find` e `ls` perché le task richiedono modifica e test. Il working directory è confinato logicamente alla fixture e lo scratch previsto resta sotto quella root; gli sconfinamenti espliciti vengono sempre auditati. Con un backend applicato, Pi e i figli vengono inoltre limitati dal sistema operativo; in `audit-only` ereditano ancora i permessi dell'utente.

Pi receives file and shell tools because tasks require editing and testing. Its working directory is logically scoped to the fixture, and the designated scratch area remains under that root; explicit escapes are always audited. When a backend is applied, the OS additionally restricts Pi and its children; in `audit-only` mode they still inherit the user's permissions.

## Validazione e processi / Validation and processes

I grader sono codice fidato versionato e vengono eseguiti dalla copia congelata soltanto dopo la verifica del relativo hash. Anche `case validate` esegue il grader per controllarne protocollo e calibrazione. Nessuna delle due esecuzioni usa il backend sandbox e entrambe mantengono i permessi dell'utente: ispezionare integralmente un caso importato prima di caricare la configurazione per un run o lanciare la validazione, e non aggiungere grader provenienti da terzi senza revisione. I file JSON dei risultati sono prodotti localmente e non devono essere usati come comandi. Il report effettua rendering Markdown di nomi modello locali; aprirlo solo in viewer fidati se i nomi provengono da un server Ollama non controllato.

## Limiti residui / Residual risks

- `audit` e il fallback di `auto` non applicano isolamento OS; il manifesto lo segnala esplicitamente.
- `sandbox-exec` è deprecato da Apple e può essere assente o rifiutare il probe; il backend non usa l'App Sandbox firmata. Directory runtime di sistema restano leggibili e la policy deve essere rivalidata dopo aggiornamenti macOS/Pi.
- Bubblewrap richiede user e network namespace non privilegiati. Policy kernel o AppArmor più restrittive possono far fallire il probe; `required` si ferma invece di degradare. Directory runtime necessarie come `/usr` e `/etc` restano leggibili.
- AppContainer deve poter creare il profilo e modificare temporaneamente le ACL dei path autorizzati. Un arresto anomalo del launcher può lasciare profilo o ACE da diagnosticare e rimuovere; il runtime staged occupa temporaneamente spazio nella directory della task e le normali semantiche registry di AppContainer non equivalgono a un registry vuoto.
- Il broker limita la destinazione di rete ma non autentica, autorizza o filtra semanticamente il protocollo Ollama. Un difetto nel broker host attraverserebbe il confine del sandbox.
- L'audit post-run non è un reference monitor: comandi shell costruiti dinamicamente, espansioni non deterministiche, semantiche complesse o codice offuscato possono leggere file esterni o usare la rete senza includere un indicatore riconoscibile negli argomenti registrati; euristiche future possono anche richiedere calibrazione contro nuovi falsi positivi.
- Il confronto del repository rileva scritture a file tracciati o non ignorati, ma non letture e non file creati in aree ignorate diverse dalla directory del run.
- Le mutazioni alle sorgenti vengono rilevate e attribuite, ma non ripristinate automaticamente per preservare prove e modifiche utente; occorre revisione prima del run successivo.
- Nessun blocco di rete a livello kernel in `audit` o nel fallback di `auto`.
- Linux usa PID namespace e `die-with-parent`, Windows un Job Object kill-on-close e macOS il gruppo processo; arresti del sistema o difetti del runtime possono comunque impedire la pulizia ordinata.
- Un grader difettoso o malevolo ha accesso ai permessi dell'utente.
- Lo schema e i controlli di path non analizzano il comportamento del codice Python del grader; un manifesto strutturalmente valido può comunque accompagnare codice malevolo.
- Log e workspace possono occupare molto spazio o contenere dati che il modello ha letto.
- I modelli locali e Ollama sono supply-chain esterne al repository.
- Un modello può ancora tentare di manipolare `.git` nella propria workspace; grader e snapshot restano fuori dalle mount consentite, ma l'audit e gli hash continuano a essere necessari come controllo indipendente.
- Le metriche POSIX possono non includere completamente tutti i discendenti; i contatori RAPL sono host-wide, possono includere altri carichi e spesso non sono disponibili senza permessi aggiuntivi.
- La whitelist dashboard riduce i dati ma non anonimizza nomi di modelli/casi, metriche o hash. Un nome locale può essere sensibile e gli hash possono collegare l'export ai run conservati.
- Il grader statico/Node della dashboard non sostituisce un browser reale: richieste costruite dinamicamente, problemi responsive o difetti di accessibilità possono richiedere ispezione manuale. La pubblicazione della dashboard non è automatica.

## Raccomandazioni / Recommendations

- Eseguire con account non privilegiato e fixture esclusivamente sintetiche.
- Usare `--sandbox required` per impedire fallback quando l'isolamento è requisito del run.
- Non disabilitare policy kernel/AppArmor aziendali solo per far passare il probe Linux: usare un host approvato o accettare esplicitamente `audit`/fallback per dati esclusivamente sintetici.
- Revisionare manifesto, prompt, fixture, grader e rubrica prima di `case validate` e di ogni run.
- Non ignorare errori `inputs`, `violations_detected` o `snapshot_compromised` e non reinserire manualmente modelli esclusi nella classifica.
- Cancellare in modo consapevole i risultati non più necessari e non pubblicarli senza revisione.
- Mantenere Pi e Ollama aggiornati solo attraverso fonti verificate; registrare le versioni per confronti longitudinali.
- Non modificare il default loopback in un endpoint remoto senza consenso esplicito e documentazione dei dati inviati.
- Ispezionare `dashboard-data.json` prima di congelarlo o condividerlo; mantenere il file e le dashboard candidate locali finché non è stata completata la revisione visuale, di rete e privacy.

## Test di sicurezza / Security tests

Il caso `secure_workspace` controlla traversal, path assoluti, fuga via symlink, scrittura atomica e redazione. I test del runner verificano validazione configurazione, calibrazione dei grader, snapshot e policy hash, scratch interno, ordine con seed, path shell risolti in stile POSIX e Windows su ogni host, traversal confinato, pattern testuali e payload heredoc non eseguibili, tentativi di rete anche in heredoc eseguibili, riesame dei report, esclusione completa del modello e divergenze di baseline. I test della milestone 2 coprono selezione/fallback/required, profilo Seatbelt e compatibilità dei report. La milestone 3 aggiunge probe e integrazioni reali per namespace/bubblewrap e AppContainer, accesso consentito e negato al filesystem, network namespace vuoto, broker Unix/named-pipe a destinazione fissa, diniego di porte dirette, ACL/DACL, Job Object e cleanup. La milestone 4 aggiunge casi corrotti, limite manifesto, campi sconosciuti, ID discordanti, path traversal, symlink esterni, pesi invalidi, directory incomplete, contratti grader errati, baseline già completate, creazione atomica, rifiuto overwrite, CLI create/validate, snapshot di manifesti/rubriche e lettura dei result schema 3 precedenti. La milestone 5 aggiunge whitelist dashboard, schemi compatibili, provenienza hashata, funnel neutro, scrittura confinata/atomica, sorgenti symlink rifiutate, dataset alternativo del grader e calibrazione della nuova fixture. Compileall e 70 test sono verdi localmente, con 8 probe OS non applicabili in questo ambiente; la validazione esplicita dei cinque casi è verde. Il run reale e la revisione browser dei candidati `showcase` sono rinviati alla selezione dei finalisti.
