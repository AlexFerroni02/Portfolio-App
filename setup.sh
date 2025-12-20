#!/bin/bash

Setup script per Portfolio-App
echo "📦 Installazione dipendenze Python..."
pip install -r requirements.txt
mkdir -p /home/appuser/.cache/ms-playwright
echo "🌐 Installazione Chromium per Playwright..."
playwright install chromium

echo "✅ Setup completato!"
echo ""
echo "Per avviare l'app:"
echo " streamlit run app.py"