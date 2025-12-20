#!/bin/bash

# Esporta la variabile d'ambiente che dice a Playwright dove trovare i browser.
# Questa è la riga chiave che risolve il problema su Streamlit Cloud.
export PLAYWRIGHT_BROWSERS_PATH=/home/appuser/.cache/ms-playwright

# Crea la cartella (con -p per non dare errore se esiste già)
mkdir -p $PLAYWRIGHT_BROWSERS_PATH

# Installa Chromium
playwright install chromium