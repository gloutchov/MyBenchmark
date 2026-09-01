# Guida autore casi / Case Author Quick Start

## Italiano

### 1. Creare lo scheletro

Eseguire dalla root del repository:

```bash
python3 benchmark.py case create api_contract \
  --title-it "Contratto API" \
  --title-en "API contract" \
  --category architecture \
  --weight 1.25 \
  --manual-rubric
```

L'ID deve contenere soltanto lettere ASCII, numeri, `-` o `_`. Il comando rifiuta directory esistenti e crea lo scheletro tramite rinomina atomica, senza sovrascrivere file.

### 2. Personalizzare il caso

La directory generata contiene:

```text
cases/api_contract/
├── case.json          # manifesto, titoli bilingui, categoria, peso e path
├── prompt.md          # richiesta completa consegnata al modello
├── fixture/           # repository sintetico iniziale e intenzionalmente incompleto
├── grader.py          # controlli automatici indipendenti dal prompt
└── manual-rubric.md   # opzionale; valutazione umana separata
```

Il manifesto segue [`schemas/case.schema.json`](schemas/case.schema.json) ed è limitato a 64 KiB. I path devono essere relativi, usare `/`, restare nella directory del caso e non attraversare symlink. L'ID deve coincidere con il nome della directory. Il peso deve essere finito, maggiore di zero e non superiore a 100.

Sostituire il prompt e la fixture di esempio con materiali completamente sintetici. Il prompt deve contenere tutto ciò che serve: durante il benchmark sono vietati rete, repository esterni e directory temporanee di sistema.

### 3. Scrivere il grader

`grader.py` riceve come primo argomento la workspace candidata e deve stampare un singolo oggetto JSON:

```json
{
  "score": 25,
  "max_score": 100,
  "checks": [
    {
      "id": "comportamento_osservabile",
      "points": 25,
      "earned": 25,
      "detail": "verifica superata"
    }
  ]
}
```

Regole obbligatorie:

- gli ID dei check sono non vuoti e univoci;
- la somma di `points` è esattamente 100;
- `earned` è compreso fra zero e i punti del check;
- `score` coincide con la somma di `earned`;
- la fixture iniziale ottiene meno di 60/100;
- test e grader non usano credenziali o rete reale.

### 4. Validare

Prima di eseguire il comando, revisionare sempre il grader: è codice fidato eseguito con i permessi dell'utente e non dentro la sandbox dell'agente.

```bash
python3 benchmark.py case validate api_contract
```

Senza ID vengono validati tutti i casi:

```bash
python3 benchmark.py case validate
```

La validazione controlla struttura, campi sconosciuti, path, file richiesti, symlink esterni, protocollo JSON del grader, totale di 100 punti e calibrazione della baseline.

### 5. Eseguire e aggiungere a un profilo

Il caso scoperto è selezionabile senza modifiche al core:

```bash
python3 benchmark.py run --cases api_contract --models NOME_MODELLO
```

Per includerlo in un profilo stabile, aggiungere il suo ID alla lista corrispondente in `benchmark.json`. Committare `case.json`, prompt, fixture, grader e rubrica prima del run: il preflight rifiuta input modificati o non tracciati.

La rubrica manuale, se dichiarata, viene copiata accanto agli artefatti del tentativo come `manual-rubric.md`. Il suo punteggio non modifica `grade.json`, `result.json` o la classifica automatica.

## English

### 1. Create the scaffold

Run from the repository root:

```bash
python3 benchmark.py case create api_contract \
  --title-it "Contratto API" \
  --title-en "API contract" \
  --category architecture \
  --weight 1.25 \
  --manual-rubric
```

The ID may contain only ASCII letters, digits, `-`, or `_`. The command refuses an existing directory and creates the scaffold through an atomic rename without overwriting files.

### 2. Customize the case

The generated directory contains:

```text
cases/api_contract/
├── case.json          # manifest, bilingual titles, category, weight, and paths
├── prompt.md          # complete request delivered to the model
├── fixture/           # synthetic, intentionally incomplete starting repository
├── grader.py          # automatic checks independent from the prompt
└── manual-rubric.md   # optional, separate human assessment
```

The manifest follows [`schemas/case.schema.json`](schemas/case.schema.json) and is limited to 64 KiB. Paths must be relative, use `/`, remain inside the case directory, and not traverse symlinks. The ID must match the directory name. Weight must be finite, greater than zero, and no greater than 100.

Replace the example prompt and fixture with entirely synthetic material. The prompt must be self-contained: benchmark tasks cannot use the network, external repositories, or system temporary directories.

### 3. Write the grader

`grader.py` receives the candidate workspace as its first argument and must print one JSON object using the contract shown above. Check IDs must be unique, points must total exactly 100, earned points must stay within each check's range, and `score` must equal total earned points. The initial fixture must score below 60/100. Tests and graders must not use real credentials or networking.

### 4. Validate

Always review the grader first: it is trusted code executed with the user's permissions, outside the agent sandbox.

```bash
python3 benchmark.py case validate api_contract
python3 benchmark.py case validate
```

The command checks structure, unknown fields, paths, required files, external symlinks, the grader JSON contract, the 100-point total, and baseline calibration.

### 5. Run and add to a profile

The discovered case is selectable without changing core code:

```bash
python3 benchmark.py run --cases api_contract --models MODEL_NAME
```

Add its ID to a `benchmark.json` profile for stable grouped runs. Commit the manifest, prompt, fixture, grader, and optional rubric first; preflight rejects dirty or untracked inputs.

When declared, the manual rubric is copied next to each attempt's artifacts as `manual-rubric.md`. Its score does not alter `grade.json`, `result.json`, or the automatic leaderboard.
