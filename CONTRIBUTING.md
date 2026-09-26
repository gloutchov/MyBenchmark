# Contributing / Contribuire

Contributions are welcome when they keep the benchmark reproducible, offline by
default, and safe for local workspaces. Open an issue before large architectural
changes; focused fixes can go directly to a pull request.

I contributi sono benvenuti quando mantengono il benchmark riproducibile,
offline per impostazione predefinita e sicuro per le workspace locali. Apri una
issue prima di modifiche architetturali ampie; le correzioni circoscritte possono
andare direttamente in una pull request.

## Development checks / Verifiche di sviluppo

Use Python 3.10 or newer. Node.js is required only for the dashboard and landing
page JavaScript tests. Before submitting a pull request, run:

Usa Python 3.10 o successivo. Node.js serve solo per i test JavaScript della
dashboard e della landing page. Prima di aprire una pull request esegui:

```bash
python3 -m compileall -q benchmark.py dashboard.py src cases tests
python3 -m unittest discover -s tests -v
node --test dashboard/tests/dashboard.test.js site/tests/site.test.js
python3 benchmark.py case validate
```

Landing-page changes also require a local static preview and a real-browser
review of desktop/mobile layouts, Italian/English content, all theme modes,
keyboard focus, overflow, console output, and network requests. Keep the site
runtime dependency-free and update both dictionaries together.

Le modifiche alla landing richiedono anche un'anteprima statica locale e una
verifica in browser reale di layout desktop/mobile, italiano/inglese, tutti i
temi, tastiera e focus, overflow, console e richieste di rete. Mantieni il sito
senza dipendenze runtime e aggiorna insieme i due dizionari.

Keep changes small, update the bilingual documentation with user-visible
behavior, and update `SECURITY_MODEL.md` for changes to sandboxing, filesystem,
networking, logging, result data, or the dashboard. Follow the repository rules
in [`AGENTS.md`](AGENTS.md).

Mantieni le modifiche piccole, aggiorna la documentazione bilingue per i
comportamenti visibili e aggiorna `SECURITY_MODEL.md` quando cambiano sandbox,
filesystem, rete, logging, dati dei risultati o dashboard. Segui le regole del
repository in [`AGENTS.md`](AGENTS.md).

Never commit credentials, private repositories, personal fixtures, raw result
directories, generated `dashboard/data/snapshot.js` files, or the local source
video `assets/Dashboard.mov`. Review graders in full: validation and grading
execute them with host-user permissions.

Non committare credenziali, repository privati, fixture personali, directory di
risultati raw, file generati `dashboard/data/snapshot.js` o il video sorgente
locale `assets/Dashboard.mov`. Revisiona sempre i grader integralmente:
validazione e grading li eseguono con i permessi dell'utente host.
