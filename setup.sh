#!/bin/bash

# Crea la cartella per i log di Playwright (misura di sicurezza per l'ambiente cloud)
mkdir -p /home/appuser/.cache/ms-playwright

# Installa solo Chromium. Streamlit Cloud si occupa già di 'pip install'.
playwright install chromium