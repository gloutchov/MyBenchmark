Esegui l'hardening mirato del modulo `safenotes`, senza cambiare le firme pubbliche e senza aggiungere dipendenze:

- `resolve_workspace_path(root, relative_path)` deve accettare solo path relativi confinati nella root; deve rifiutare path assoluti, segmenti `..` e fughe tramite symlink. Deve funzionare anche per un file finale ancora inesistente.
- `atomic_write_text(root, relative_path, text)` deve usare la validazione precedente, creare le directory interne necessarie e sostituire il file in modo atomico senza lasciare file temporanei.
- `redact_message(message)` deve eliminare dai messaggi i valori associati, senza distinzione maiuscole/minuscole, a `api_key=...`, `token: ...` e `password = ...`. I valori terminano al primo spazio, virgola o punto e virgola; il resto del messaggio va preservato.

Aggiungi test positivi e negativi, aggiorna `SECURITY_MODEL.md` con controlli e limiti residui e aggiorna il README se necessario. Esegui i test. Non stampare nei test o nei log i valori segreti usati come fixture.
