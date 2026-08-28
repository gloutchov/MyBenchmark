La funzionalità di export Markdown della milestone 2 è già implementata e i test iniziali sono presenti. Porta la milestone allo stato “pronta per approvazione” seguendo `AGENTS.md`:

- crea il branch previsto `milestone/2-export` se non esiste;
- verifica i test automatici;
- sincronizza la versione `0.2.0` in tutti i punti canonici (`VERSION`, `pyproject.toml`, modulo `__version__`, README e PLAN);
- documenta il comando `python -m tinyjournal export JOURNAL OUTPUT` nel README bilingue e nei manuali italiano/inglese;
- aggiorna `SECURITY_MODEL.md` per il confine filesystem dell'export (output confinato nella workspace, traversal rifiutato, sostituzione atomica) e i limiti residui;
- aggiorna `MAP.md` con il modulo e i test di export;
- aggiorna stato e checklist della milestone in `PLAN.md`.

Fermati prima del merge per l'avallo esplicito del progettista. Non creare tag o release e non modificare la storia di `main`. Puoi creare un commit sul branch milestone. Riporta chiaramente verifiche eseguite e operazioni lasciate in attesa.
