Completa il sottosistema di preferenze di NoteKeeper mantenendo un'architettura modulare e senza dipendenze esterne.

Contratto richiesto:

- `Settings` ha `language="auto"`, `theme="auto"`, `autosave_seconds=30`.
- `load_settings(path)` restituisce i default se il file non esiste; per JSON corrotto, tipi errati o valori non validi solleva `ConfigError`. Le chiavi sconosciute vengono ignorate per compatibilità futura.
- Lingue ammesse: `auto`, `it`, `en`. Temi ammessi: `auto`, `light`, `dark`. `autosave_seconds` è un intero (non booleano) tra 5 e 3600 inclusi.
- `save_settings(path, settings)` valida e salva JSON UTF-8 atomicamente, creando la directory se serve.
- `resolve_language(language, system_locale)` restituisce `it` in modalità automatica solo per locale italiano (`it`, `it_IT`, `it-CH`, senza distinzione maiuscole/minuscole), altrimenti `en`.
- `resolve_theme(theme, system_dark)` risolve `auto` in base al booleano `system_dark`.
- `translate(key, language)` usa dizionari italiano/inglese sincronizzati almeno per `title`, `saved`, `error`; chiavi mancanti sollevano `KeyError`. Non inserire stringhe utente hardcoded fuori dai dizionari.

Aggiungi test, aggiorna entrambi i manuali (`ISTRUZIONI.md` e `INSTRUCTIONS.md`), README e MAP. Documenta validazione e fallback. Esegui i test e non aggiungere dipendenze.
