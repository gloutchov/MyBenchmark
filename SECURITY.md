# Security policy / Politica di sicurezza

## Supported versions / Versioni supportate

Security fixes target the latest release and the current `main` branch. Older
releases may not receive backports.

Le correzioni di sicurezza riguardano l'ultima release e il branch `main`
corrente. Le release precedenti potrebbero non ricevere backport.

## Reporting a vulnerability / Segnalare una vulnerabilità

Do not open a public issue for a suspected vulnerability. Use GitHub's private
vulnerability reporting form:

https://github.com/gloutchov/MyBenchmark/security/advisories/new

Non aprire una issue pubblica per una possibile vulnerabilità. Usa il modulo
privato GitHub indicato sopra.

Include the affected version, reproduction steps, expected impact, and any
suggested mitigation. Remove API keys, private paths, model outputs, and other
personal data before submitting the report.

Indica versione interessata, procedura di riproduzione, impatto previsto ed
eventuali mitigazioni. Rimuovi API key, path privati, output dei modelli e altri
dati personali prima dell'invio.

The maintainer will acknowledge complete reports on a best-effort basis,
coordinate validation and remediation privately, and disclose details only
after a fix or agreed mitigation is available.

Il maintainer prenderà in carico le segnalazioni complete secondo disponibilità,
coordinerà privatamente verifica e correzione e pubblicherà i dettagli solo dopo
la disponibilità di una correzione o mitigazione concordata.

## Scope / Ambito

Reports are especially useful for sandbox escapes, path traversal, unsafe
grader execution, unintended network access, secret or result leakage, and
dashboard server or import vulnerabilities. The documented residual risks and
the non-enforcing `audit` mode are not vulnerabilities by themselves; see
[`SECURITY_MODEL.md`](SECURITY_MODEL.md).

Sono particolarmente utili segnalazioni relative a evasione dalla sandbox, path
traversal, esecuzione non sicura dei grader, accesso di rete inatteso, perdita di
segreti o risultati e vulnerabilità del server o dell'import dashboard. I rischi
residui documentati e la modalità `audit`, che non applica isolamento, non sono
di per sé vulnerabilità; consulta [`SECURITY_MODEL.md`](SECURITY_MODEL.md).
