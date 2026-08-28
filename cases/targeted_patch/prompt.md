Un utente segnala due regressioni in PocketLedger. Applica una patch mirata, mantenendo l'API pubblica esistente:

1. `Ledger.balance()` deve sottrarre sia le voci `debit` sia le voci `refund`.
2. `add_entry()` deve rifiutare i booleani e i numeri non finiti (`NaN`, `+/-inf`) oltre agli importi non positivi.
3. `import_csv()` deve essere atomico: se una riga è invalida, non deve aggiungere nessuna voce.

Aggiungi test di regressione proporzionati e aggiorna il README per i comportamenti visibili. Non aggiungere dipendenze, non cambiare l'API e non rifattorizzare `formatting.py`. Esegui i test e riporta quelli eventualmente non eseguiti.
