# Modello di sicurezza / Security Model

## Modello operativo / Operating model

LocalAgent Benchmark copia fixture sintetiche in repository Git dedicati, avvia Pi in modalità non interattiva e usa l'API OpenAI-compatible di Ollama su loopback. Ogni tentativo ha una directory Pi separata e conserva workspace, eventi, log, patch e valutazione.

LocalAgent Benchmark copies synthetic fixtures into dedicated Git repositories, launches Pi non-interactively, and uses Ollama's OpenAI-compatible API over loopback. Each attempt has an isolated Pi configuration directory and retains its workspace, events, logs, patch, and grade.

## Asset e confini / Assets and boundaries

- Il repository del benchmark, `AGENTS.md` e i grader sono input fidati.
- Prompt e fixture inclusi nel repository sono input controllati, ma il loro contenuto viene comunque trattato come dati per il modello.
- Le risposte del modello, gli argomenti tool e i file prodotti sono output non fidati.
- Ollama è un servizio locale separato; il confine HTTP è `ollama.url`.
- Il filesystem esterno alla workspace del singolo caso non appartiene allo scope dell'agente.

## Controlli implementati / Implemented controls

- Configurazione centrale validata all'avvio; URL e ID caso vengono controllati.
- Nessuna dipendenza Python di runtime e nessun download automatico di modelli.
- Pi viene avviato con `--offline`, telemetria disabilitata e risorse globali non necessarie disabilitate.
- `PI_CODING_AGENT_DIR` punta alla directory del run; il file provider contiene solo il placeholder Ollama, non una chiave reale.
- Ogni tentativo parte da una copia nuova e da un commit Git baseline.
- Timeout per task e terminazione del gruppo processo su sistemi POSIX.
- Grader eseguiti come processi separati, con timeout e senza scrittura di bytecode.
- Fixture e test non contengono segreti reali; i valori di test sensibili vengono costruiti a runtime e non stampati.
- Output sotto `results/`, escluso da Git per default.
- Ollama viene interrogato tramite URL configurato; il default è loopback HTTP.

## Segreti e logging / Secrets and logging

Il benchmark non richiede API key. Non inserire token, password, repository privati o documenti personali nei prompt o nelle fixture. Gli eventi JSONL di Pi possono contenere integralmente prompt, risposte, comandi, output tool e frammenti di file. Trattare l'intera directory `results/` come potenzialmente sensibile.

The benchmark requires no API key. Do not place tokens, passwords, private repositories, or personal documents in prompts or fixtures. Pi JSONL events may contain complete prompts, responses, commands, tool output, and file excerpts. Treat all of `results/` as potentially sensitive.

## Rete / Network

Il runner non contatta servizi Internet. `--offline` disattiva le operazioni di rete iniziali di Pi, mentre le richieste necessarie a Ollama restano locali. Questo controllo non è un firewall: un comando shell generato dal modello può tentare accessi di rete se il sistema operativo li consente.

The runner does not contact Internet services. Pi startup networking is disabled, while required Ollama traffic remains local. This is not a firewall: model-generated shell commands may attempt network access when allowed by the operating system.

## Filesystem e permessi / Filesystem and permissions

Pi riceve strumenti `read`, `bash`, `edit`, `write`, `grep`, `find` e `ls` perché le task richiedono modifica e test. Il working directory è confinato logicamente alla fixture, ma Pi e la shell ereditano i permessi dell'utente: non esiste ancora un sandbox OS che impedisca tecnicamente letture o scritture esterne.

Pi receives file and shell tools because tasks require editing and testing. Its working directory is logically scoped to the fixture, but Pi and its shell inherit the user's permissions: no OS sandbox currently enforces the workspace boundary.

## Validazione e processi / Validation and processes

I grader sono codice fidato versionato. Non aggiungere grader provenienti da terzi senza revisione: vengono eseguiti con i permessi dell'utente. I file JSON dei risultati sono prodotti localmente e non devono essere usati come comandi. Il report effettua rendering Markdown di nomi modello locali; aprirlo solo in viewer fidati se i nomi provengono da un server Ollama non controllato.

## Limiti residui / Residual risks

- Nessun isolamento OS per Pi o per i comandi shell del modello.
- Nessun blocco di rete a livello kernel.
- Un modello può creare processi figli che sopravvivono su piattaforme dove la terminazione del gruppo non è disponibile.
- Un grader difettoso o malevolo ha accesso ai permessi dell'utente.
- Log e workspace possono occupare molto spazio o contenere dati che il modello ha letto.
- I modelli locali e Ollama sono supply-chain esterne al repository.
- Un modello può manipolare `.git`, cancellare file della fixture o tentare di leggere i grader; la valutazione resta affidata a controlli post-run, non a isolamento anticheating.

## Raccomandazioni / Recommendations

- Eseguire con account non privilegiato e fixture esclusivamente sintetiche.
- Usare un container o sandbox OS senza rete per casi aggiunti da fonti non fidate.
- Revisionare prompt, fixture e grader prima di ogni run.
- Cancellare in modo consapevole i risultati non più necessari e non pubblicarli senza revisione.
- Mantenere Pi e Ollama aggiornati solo attraverso fonti verificate; registrare le versioni per confronti longitudinali.
- Non modificare il default loopback in un endpoint remoto senza consenso esplicito e documentazione dei dati inviati.

## Test di sicurezza / Security tests

Il caso `secure_workspace` controlla traversal, path assoluti, fuga via symlink, scrittura atomica e redazione. I test del runner verificano validazione configurazione, parser eventi e calibrazione dei grader. Una futura milestone deve aggiungere un backend sandbox e test specifici per processi figli e rete.
