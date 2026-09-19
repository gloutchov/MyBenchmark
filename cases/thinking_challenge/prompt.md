# Pianificazione deterministica multi-vincolo / Deterministic multi-constraint planning

Completa il piccolo progetto Python `releaseplanner`. Devi implementare un pianificatore esatto e deterministico per scegliere un sottoinsieme di iniziative di una release. La valutazione considera soltanto comportamento osservabile, test e documentazione: non esporre né salvare la tua catena di pensiero.

Complete the small Python project `releaseplanner`. Implement an exact, deterministic planner that selects a subset of release initiatives. Evaluation uses only observable behavior, tests, and documentation: do not expose or persist your chain of thought.

## Contratto API / API contract

Implementa / implement:

```python
from releaseplanner import PlanningError, plan_release

result = plan_release(spec)
```

`spec` è un dizionario con esattamente questi campi / is a dictionary with exactly these fields:

- `budget`: intero non negativo / non-negative integer;
- `risk_limit`: intero non negativo / non-negative integer;
- `team_capacities`: mappa non vuota `team -> capacità intera non negativa` / non-empty mapping from team to non-negative integer capacity;
- `required_categories`: lista senza duplicati di categorie che devono essere rappresentate / duplicate-free list of categories that must be represented;
- `mandatory`: lista senza duplicati di ID che devono essere selezionati / duplicate-free list of initiative IDs that must be selected;
- `initiatives`: lista da 1 a 18 iniziative / list containing 1 to 18 initiatives.

Ogni iniziativa contiene esattamente / Each initiative contains exactly:

```json
{
  "id": "auth",
  "value": 12,
  "cost": 4,
  "risk": 2,
  "category": "security",
  "team_effort": {"backend": 2, "mobile": 1},
  "requires": ["foundation"],
  "conflicts": ["legacy-auth"]
}
```

Regole di validazione / Validation rules:

- `id`, categorie e nomi team sono stringhe non vuote; gli ID sono univoci;
- `value`, `cost`, `risk`, capacità e impegni team sono interi non negativi; `bool` non è un intero valido;
- liste e mappe hanno stringhe/chiavi univoche e non vuote;
- i team usati da `team_effort` devono essere dichiarati in `team_capacities`;
- `mandatory`, `requires` e `conflicts` devono riferirsi a ID esistenti;
- un'iniziativa non può richiedere o confliggere con se stessa e lo stesso ID non può comparire sia in `requires` sia in `conflicts`;
- le categorie richieste devono esistere nelle iniziative;
- campi mancanti o sconosciuti sono errori.

Qualsiasi input non valido deve sollevare `PlanningError`, sottoclasse di `ValueError`. La funzione non deve modificare `spec`.

Invalid input must raise `PlanningError`, a `ValueError` subclass. The function must not mutate `spec`.

## Vincoli e ottimo / Constraints and optimum

Un piano è ammissibile se / A plan is feasible when:

- costo totale `<= budget` e rischio totale `<= risk_limit`;
- l'impegno di ogni team non supera la capacità dichiarata;
- include tutti gli ID `mandatory`;
- include almeno un'iniziativa per ogni categoria richiesta;
- per ogni iniziativa selezionata include tutte le sue dipendenze dirette; questa regola rende effettive anche le dipendenze transitive;
- non seleziona due iniziative in conflitto. Il conflitto è simmetrico anche se dichiarato da un solo lato.

Fra tutti i piani ammissibili scegli, in quest'ordine / Among all feasible plans choose, in this order:

1. valore totale massimo / maximum total value;
2. costo totale minimo / minimum total cost;
3. rischio totale minimo / minimum total risk;
4. tupla lessicograficamente minima degli ID selezionati e ordinati / lexicographically smallest tuple of sorted selected IDs.

Se non esiste un piano ammissibile, solleva `PlanningError`. La soluzione deve essere esatta per tutti gli input ammessi; non usare euristiche greedy.

Raise `PlanningError` when no feasible plan exists. The solution must be exact for every allowed input; do not use greedy heuristics.

Restituisci esattamente / Return exactly:

```json
{
  "selected": ["auth", "foundation"],
  "total_value": 12,
  "total_cost": 4,
  "total_risk": 2,
  "team_usage": {"backend": 3, "data": 0, "mobile": 0}
}
```

`selected` deve essere ordinato; `team_usage` deve contenere tutti e soli i team dichiarati, inclusi quelli con uso zero.

`selected` must be sorted. `team_usage` must contain every declared team and no other team, including teams with zero usage.

## CLI, test e documentazione / CLI, tests, and documentation

- `python -m releaseplanner SPEC.json` deve leggere JSON UTF-8 e stampare soltanto il risultato JSON su stdout;
- input/file/piano non valido deve terminare con exit code `2` e un messaggio sintetico su stderr, senza traceback;
- aggiungi test per validazione, dipendenze, conflitti, ottimo, tie-break e piano impossibile;
- aggiorna `README.md` in italiano e inglese con API, CLI, vincoli e tie-break;
- mantieni il runtime privo di dipendenze esterne;
- non modificare `src/releaseplanner/formatting.py`, che rappresenta codice non correlato.

Do not use network access, external repositories, system temporary directories, or files outside the workspace.
