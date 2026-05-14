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
