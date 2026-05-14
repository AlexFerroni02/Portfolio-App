# Maintainability Assessment

## 2026-05-14: Rebalancing + Data Mapping Stabilization

### Context
- Segnalati bug su ribilanciamento (input percentuali instabili) e perdita intermittente mappatura ticker.
- Richiesta nuova pagina metriche portafoglio senza benchmark.

### Decisions
- Introdotto calcolo esplicito del gap percentuale verso 100% nel servizio di ribilanciamento.
- Rafforzata la gestione dello stato Streamlit per ticker per categoria (sync stato + normalizzazione ticker).
- Bloccato il calcolo ribilanciamento quando almeno una categoria ha distribuzione invalida.
- Normalizzazione centralizzata ISIN/ticker lato persistenza mappatura.
- Salvataggio mappatura ora mostra esito reale (success/error) invece di successo incondizionato.
- Aggiunta pagina metriche dedicata con calcoli modulari in servizio separato.

### Trade-offs
- Più robustezza e chiarezza in UI, con un leggero aumento della logica di session_state.
- Normalizzazione uppercase su ticker/ISIN migliora coerenza ma uniforma il formato visualizzato.
- Metriche risk-adjusted usano modello semplice (daily returns + tasso risk-free costante).

### Operational Steps
- Eseguire test unitari completi con pytest.
- Validare flussi UI: Ribilancio (edit multipli), Gestione Dati (salvataggio mappatura), nuova pagina Metriche.
- Monitorare regressioni su import CSV e sincronizzazione prezzi Yahoo.

## 2026-05-14: Metrics/Benchmark Coherence Refinement

### Context
- Richiesta esplicita di coerenza tra metriche TWR e guadagno reale, evitando KPI dispersi e ambigui.
- Segnalato falso picco drawdown in area fine gennaio 2024 legato a vendite.

### Decisions
- Ripristinato l'uso dei versamenti netti con costi inclusi nella pagina Metriche.
- Introdotta tabella comparativa TWR vs Reale con sole metriche non equivalenti (totale e annualizzato).
- Il confronto annuale a barre ora usa reale annualizzato per anno, non cumulato totale.
- Drawdown Benchmark migrato a logica flow-adjusted su serie di rendimenti, non su valore grezzo.

### Trade-offs
- Il reale annualizzato su anni parziali (es. anno corrente) può risultare più volatile per definizione.
- La tabella comparativa riduce ridondanza ma richiede alfabetizzazione metrica minima dell'utente.

### Operational Steps
- Verifica automatica: test suite completa green (44 test).
- Verifica numerica mirata finestra 2024-01-24/2024-02-02 per assenza di falsi drawdown da flussi.

## 2026-05-14: Annualized Real Return Correction

### Context
- Segnalata incoerenza tra TWR e "Reale annualizzato" in assenza di nuovi versamenti nel periodo.

### Decisions
- Sostituita formula del reale annualizzato con metodo Modified Dietz (money-weighted) su flussi da Investito.
- Confronto annuale portato su base omogenea annualizzata per entrambe le metriche (TWR annualizzato e Reale annualizzato).
- Aggiunto test dedicato: quando non ci sono flussi nel periodo, TWR annualizzato == Reale annualizzato.

### Trade-offs
- Su anni parziali l'annualizzazione amplifica naturalmente i valori rispetto al semplice YTD.
- Differenze residue TWR vs Reale su anni con flussi rimangono attese per natura delle metriche.

### Operational Steps
- Suite test aggiornata e rieseguita con esito green (45 test).
- Validazione live pagina Metriche: colonne annualizzate allineate e coincidenti nel 2026 (assenza flussi).

## 2026-05-14: Live 5-Min Portfolio Monitor

### Context
- Richiesta una sezione Live compatta per monitorare variazione giornaliera del portafoglio e dei singoli titoli.
- Vincolo UX: refresh ogni 5 minuti solo quando la pagina Live è aperta, con fallback tollerante a dati non disponibili.

### Decisions
- Introdotta nuova pagina dedicata `Live` invece di accorpare su Dashboard, per separare dati intraday da analisi storiche.
- Creato servizio modulare `live_service` con cache a TTL 300 secondi e fallback su ultimo close EOD per ticker non aggiornati.
- Aggiunte eccezioni custom di dominio (`LiveDataError`, `QuoteFetchError`) per error handling più granulare.
- Implementata UI compatta con: stato mercato + timestamp ultimo update, KPI portafoglio giornalieri, tabella live per titolo.
- Auto-refresh realizzato con dipendenza leggera `streamlit-autorefresh`, attivo solo nella pagina Live e disattivabile via toggle.

### Trade-offs
- L'orario di mercato è una stima generalista (Europe/Rome) e non distingue in dettaglio tra borse con calendari diversi.
- Il fallback EOD privilegia continuità UX rispetto alla purezza del dato intraday quando Yahoo non risponde.
- L'aggiunta della dipendenza esterna migliora robustezza del refresh ma introduce un piccolo costo manutentivo.

### Operational Steps
- Eseguire `pytest` completo dopo ogni modifica del servizio Live o della tabella UI live.
- Monitorare in produzione il numero di ticker in fallback per identificare eventuali limiti API o simboli non validi.
- Validare periodicamente la UX mobile (densità tabella e KPI) e l'aderenza al requisito di compattezza.

## 2026-05-14: Performance Merge + Live Promo Motion

### Context
- Richiesta UX di accorpare Metriche e Benchmark in una vista unica più orientata al flusso decisionale.
- Richiesta UI di mantenere la pagina Live in sidebar, aggiungendo però elementi in movimento con effetto "attention".

### Decisions
- Accorpate Benchmark e Metriche nella pagina `Performance` usando tab dedicate nello stesso entrypoint.
- Rimosso il link diretto a Metriche dalla sidebar per ridurre ridondanza navigazionale.
- Mantenuta una pagina `Metriche` legacy minimale con redirect guidato verso `Performance`.
- Aggiunta barra promo animata in sidebar per aumentare discoverability della sezione Live.
- Aggiunta barra ticker animata nella pagina Live con variazioni percentuali dei principali titoli.

### Trade-offs
- Maggior concentrazione di contenuto nella pagina Performance richiede titoli/tab molto espliciti.
- La barra animata aumenta engagement ma introduce una lieve componente visiva continua da monitorare lato accessibilità.
- Pagina Metriche legacy resta per backward compatibility URL, ma non è più entry principale.

### Operational Steps
- Verificare con utenti frequenti che il nuovo naming `Performance` sia intuitivo quanto i vecchi label separati.
- Monitorare leggibilità della barra animata Live su schermi piccoli e ridurre velocità se necessario.
- Rieseguire test regressione dopo eventuale estrazione futura di componenti comuni per tab Performance.

## 2026-05-14: Global Sticky Live Bar Tuning

### Context
- Richiesta una barra animata più lenta e sempre visibile in alto, con adattamento al tema scuro.
- Richiesta esplicita di rimuovere la barra animata interna alla pagina Live.

### Decisions
- Trasformata la promo Live in barra top sticky globale, renderizzata in `make_sidebar` ma fuori dal container sidebar.
- Ridotta la velocità animazione (scorrimento più lento) per migliorare leggibilità.
- Aggiornata la palette per usare variabili tema Streamlit (`--text-color`, `--secondary-background-color`, `--primary-color`).
- Rimossa la barra ticker interna dalla pagina Live per evitare duplicazioni visive.
- Ripristinati i valori reali nella barra top (ticker + variazione %) invece della sola stringa promozionale.
- Stato mercato in pagina Live reso esplicito con badge visivo `MERCATO APERTO`/`MERCATO CHIUSO`.

### Trade-offs
- Una barra sticky globale aumenta attenzione ma occupa spazio verticale costante.
- L'adattamento via CSS variables dipende dalla disponibilità delle variabili tema nell'host Streamlit.

### Operational Steps
- Validare su tema chiaro/scuro che contrasto e velocità restino leggibili.
- Monitorare feedback utente su eventuale riduzione ulteriore della velocità di scorrimento.

## 2026-05-14: Dynamic Live Bar Removal

### Context
- Richiesta di rimuovere completamente la barra dinamica perché non gradita in UX.
- Necessità di ripulire tutte le dipendenze e funzioni collegate per evitare codice morto.

### Decisions
- Rimossa la barra dinamica globale dalla UI condivisa.
- Rimossi helper, import e chiamate connesse alla topbar live in `ui/components.py`.
- Rimossi helper marquee non più usati in `ui/live_components.py`.
- Mantenuto lo stato mercato esplicito nella pagina Live (`MERCATO APERTO`/`MERCATO CHIUSO`).

### Trade-offs
- Si perde il richiamo visivo persistente in alto, ma si guadagna una UI più pulita e meno distraente.

### Operational Steps
- Verificare regressioni su tutte le pagine dopo la rimozione della UI globale.
- Mantenere eventuali future animazioni solo su aree opzionali/non invasive.

## 2026-05-14: Live Page Visual Refresh

### Context
- Richiesta di rendere la pagina Live più accattivante senza cambiare la logica dati.

### Decisions
- Introdotto styling tema-aware per card KPI e blocchi informativi della Live.
- Stato mercato reso più visibile con badge e metadati in unico pannello (update time + numero titoli monitorati).
- Aggiunta sezione "Top Movers" e "Peggiori Oggi" per lettura rapida dei titoli più attivi.
- Tabella principale mantenuta ma con formattazione segni espliciti su variazioni (prefisso +/−).

### Trade-offs
- Più componenti visivi migliorano la scansione, ma aumentano la densità della pagina.
- Lo styling custom CSS richiede manutenzione se Streamlit cambia classi/struttura rendering.

### Operational Steps
- Verificare resa su schermi piccoli e valutare eventuale riduzione top movers da 5 a 3 righe.
- Monitorare feedback utente su leggibilità colori in tema chiaro/scuro.
