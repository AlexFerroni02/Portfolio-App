import pandas as pd
import hashlib
import requests
import yfinance as yf
import streamlit as st
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from database.connection import get_data, save_data
from services.portfolio_service import calculate_liquidity
import json
def parse_degiro_csv(file):
    df = pd.read_csv(file)
    cols = ['Quantità', 'Quotazione', 'Valore', 'Costi di transazione', 'Totale']
    for c in cols:
        if c in df.columns:
            df[c] = df[c].astype(str).str.replace(',', '.').apply(pd.to_numeric, errors='coerce').fillna(0)
    if 'Data' in df.columns:
        df['Data'] = pd.to_datetime(df['Data'], format='%d-%m-%Y', errors='coerce').dt.normalize()
    if 'Costi di transazione' in df.columns:
        df['Costi di transazione'] = df['Costi di transazione'].abs()
    return df

def generate_id(row, index):
    d_str = row['Data'].strftime('%Y-%m-%d') if pd.notna(row['Data']) else ""
    raw = f"{index}{d_str}{row.get('Ora','')}{row.get('ISIN','')}{row.get('Quantità','')}{row.get('Valore','')}"
    return hashlib.md5(raw.encode()).hexdigest()

def process_new_transactions(file: "UploadedFile", existing_transactions: pd.DataFrame) -> pd.DataFrame:
    """
    Elabora un file CSV di transazioni, lo confronta con quelle esistenti e restituisce solo le nuove.
    """
    ndf = parse_degiro_csv(file)
    rows_to_add = []
    existing_ids = set(existing_transactions['id']) if not existing_transactions.empty else set()
    
    for idx, r in ndf.iterrows():
        if pd.isna(r.get('ISIN')): continue
        tid = generate_id(r, idx)
        if tid not in existing_ids:
            val = r.get('Totale', 0) if r.get('Totale', 0) != 0 else r.get('Valore', 0)
            rows_to_add.append({
                'id': tid, 
                'date': r['Data'], 
                'product': r.get('Prodotto',''), 
                'isin': r.get('ISIN',''), 
                'quantity': r.get('Quantità',0), 
                'local_value': val, 
                'fees': r.get('Costi di transazione',0), 
                'currency': 'EUR'
            })
            existing_ids.add(tid)
            
    return pd.DataFrame(rows_to_add)

def calculate_net_worth_snapshot(snapshot_date: pd.Timestamp, df_trans: pd.DataFrame, df_map: pd.DataFrame, df_prices: pd.DataFrame, df_budget: pd.DataFrame) -> tuple[float, float, float]:
    """
    Calcola il valore degli asset, la liquidità e il patrimonio netto totale a una data specifica.
    Replica la logica complessa della pagina Gestione Dati.
    """
    # Normalizza le date per confronti sicuri
    if not df_trans.empty: df_trans['date'] = pd.to_datetime(df_trans['date']).dt.normalize()
    if not df_prices.empty: df_prices['date'] = pd.to_datetime(df_prices['date']).dt.normalize()
    if not df_budget.empty: df_budget['date'] = pd.to_datetime(df_budget['date']).dt.normalize()

    net_worth_at_date, total_assets_value, final_liquidity = 0, 0, 0

    # Filtra tutti i dati fino alla data dello snapshot
    trans_at_date = df_trans[df_trans['date'] <= snapshot_date] if not df_trans.empty else pd.DataFrame()
    prices_at_date = df_prices[df_prices['date'] <= snapshot_date] if not df_prices.empty else pd.DataFrame()
    budget_at_date = df_budget[df_budget['date'] <= snapshot_date] if not df_budget.empty else pd.DataFrame()

    # 1. Calcolo Valore Asset alla data
    if not trans_at_date.empty and not df_map.empty and not prices_at_date.empty:
        df_full_nw = trans_at_date.merge(df_map, on='isin', how='left')
        if 'mapping_id' not in df_full_nw.columns and 'id' in df_full_nw.columns:
            df_full_nw = df_full_nw.rename(columns={'id': 'mapping_id'})
        last_prices_at_date = prices_at_date.sort_values('date').groupby('mapping_id').tail(1).set_index('mapping_id')['close_price']
        view_nw = df_full_nw.groupby('mapping_id')['quantity'].sum().reset_index()
        view_nw['mkt_val'] = view_nw['quantity'] * view_nw['mapping_id'].map(last_prices_at_date).fillna(0)
        total_assets_value = view_nw['mkt_val'].sum()

    # 2. Calcolo Liquidità alla data (usando la funzione di servizio già esistente)
    final_liquidity, _ = calculate_liquidity(budget_at_date, trans_at_date)

    # 3. Calcolo Patrimonio Netto
    net_worth_at_date = total_assets_value + final_liquidity
    
    return net_worth_at_date, total_assets_value, final_liquidity

def fetch_justetf_allocation_robust(isin):
    """
    Scarica da JustETF con fallback intelligente:
    1. Prova API JSON (se esiste)
    2. Scraping BeautifulSoup avanzato con AJAX Wicket
    3. Fallback Playwright (browser automation) se gli altri metodi falliscono
    """
    
    # METODO 1: Prova a trovare endpoint API o dati JSON nell'HTML
    geo_api, sec_api = _try_fetch_justetf_api(isin)

    # METODO 2: Fallback a BeautifulSoup / AJAX per ottenere dati completi
    geo_bs, sec_bs = _fetch_justetf_beautifulsoup(isin)

    # Unisci risultati: preferisci dettagli da BeautifulSoup/AJAX quando presenti
    geo_dict = {}
    sec_dict = {}
    if geo_api:
        geo_dict.update(geo_api)
    if geo_bs:
        geo_dict.update(geo_bs)
    if sec_api:
        sec_dict.update(sec_api)
    if sec_bs:
        sec_dict.update(sec_bs)

    # METODO 3: Se i risultati sono incompleti (<=5 paesi/settori), prova Playwright
    if (len(geo_dict) <= 5 or len(sec_dict) <= 5):
        st.info("🔄 Dati limitati, provo con Playwright per espandere le tabelle...")
        geo_pw, sec_pw = _fetch_justetf_playwright(isin)
        if geo_pw:
            geo_dict.update(geo_pw)
        if sec_pw:
            sec_dict.update(sec_pw)

    return geo_dict, sec_dict


def _try_fetch_justetf_api(isin):
    """
    Prova a estrarre dati da JSON embedded o API nascosta
    """
    url = f"https://www.justetf.com/it/etf-profile.html?isin={isin}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json, text/html, */*",
        "Accept-Language": "it-IT,it;q=0.9,en;q=0.8"
    }
    
    geo_dict, sec_dict = {}, {}
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        # Cerca script JSON nell'HTML
        soup = BeautifulSoup(response.text, 'lxml')
        
        # Cerca dati JSON embedded (tipo application/json o window.dataLayer)
        scripts = soup.find_all('script', type='application/json')
        for script in scripts:
            try:
                import json
                data = json.loads(script.string)
                # Cerca chiavi tipo "countries", "sectors", "allocation"
                if isinstance(data, dict):
                    # Adatta in base alla struttura reale
                    if 'countries' in data:
                        geo_dict = data['countries']
                    if 'sectors' in data:
                        sec_dict = data['sectors']
            except:
                pass
        
        # Cerca anche in window.__ variables
        for script in soup.find_all('script'):
            if script.string and 'countries' in str(script.string):
                # Qui potresti parsare JavaScript inline se necessario
                pass
                
    except Exception as e:
        pass  # Silenzioso, proveremo BeautifulSoup
    
    return geo_dict, sec_dict


def _fetch_justetf_beautifulsoup(isin):
    """
    Metodo BeautifulSoup migliorato che cerca anche nelle righe nascoste
    e tenta di caricare dati extra via link "load more".
    """
    url = f"https://www.justetf.com/it/etf-profile.html?isin={isin}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept-Language": "it-IT,it;q=0.9,en;q=0.8",
        "X-Requested-With": "XMLHttpRequest"
    }

    geo_dict, sec_dict = {}, {}
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'lxml')

        # helper: perform wicket ajax request (uses session, sets Wicket-Ajax-BaseURL)
        def _request_wicket_ajax(isin_local, ajax_url, headers_local):
            import re
            session = requests.Session()
            base_page = f"https://www.justetf.com/it/etf-profile.html?isin={isin_local}"
            try:
                r0 = session.get(base_page, headers={'User-Agent': headers_local.get('User-Agent','Mozilla/5.0')}, timeout=10)
                # try to extract wicket.ajax.baseurl
                m = re.search(r'wicket\.ajax\.baseurl\s*=\s*"([^"]+)"', r0.text)
                baseval = m.group(1) if m else f"it/etf-profile.html?isin={isin_local}"
            except Exception:
                baseval = f"it/etf-profile.html?isin={isin_local}"

            headers_ajax = headers_local.copy()
            headers_ajax.update({
                'X-Requested-With': 'XMLHttpRequest',
                'Wicket-Ajax': 'true',
                'Wicket-Ajax-BaseURL': baseval,
                'Accept': '*/*'
            })
            try:
                # use POST as Wicket often expects POST
                r = session.post(ajax_url, headers=headers_ajax, timeout=15)
                return r
            except Exception:
                try:
                    return session.get(ajax_url, headers=headers_ajax, timeout=15)
                except Exception:
                    return None


        # --- GEOGRAFIA ---
        h3_geo = soup.find('h3', string=lambda text: text and 'Paesi' in text)
        if h3_geo:
            load_more_link = soup.find('a', class_='etf-holdings_countries_load-more_link')

            if load_more_link:
                extra_href = load_more_link.get('href')
                extra_url = None
                if extra_href and extra_href not in ['#', 'javascript:void(0)', '']:
                    extra_url = extra_href
                # if href is '#' or empty, try extract AJAX URL from scripts
                if not extra_url or extra_url in ['#', 'javascript:void(0)', '']:
                    import re
                    scripts_text = ' '.join([s.string or '' for s in soup.find_all('script')])
                    m = re.search(r'Wicket\.Ajax\.ajax\(\{[^}]*u\"?:\s*\"([^\"]*holdingsSection-countries-loadMoreCountries[^\"]*)\"', scripts_text)
                    if not m:
                        m = re.search(r'Wicket\.Ajax\.ajax\(\{[^}]*u\'?:\s*\'([^\']*holdingsSection-countries-loadMoreCountries[^\']*)\'', scripts_text)
                    if m:
                        extra_url = m.group(1)
                if extra_url:
                    if not extra_url.startswith('http'):
                        extra_url = f"https://www.justetf.com{extra_url}"

                try:
                    st.info(f"🔄 Caricamento dati extra da: {extra_url}")
                    # se è un endpoint Wicket AJAX usiamo la chiamata emulata
                    extra_response = None
                    if '_wicket=1' in extra_url or 'loadMore' in extra_url or 'holdingsSection' in extra_url:
                        extra_response = _request_wicket_ajax(isin, extra_url, headers)
                    if extra_response is None:
                        extra_response = requests.get(extra_url, headers=headers, timeout=10)
                    extra_response.raise_for_status()

                    try:
                        extra_data = extra_response.json()
                        if isinstance(extra_data, dict) and 'countries' in extra_data:
                            geo_dict.update(extra_data['countries'])
                    except Exception:
                        txt = extra_response.text
                        # Gestisci risposta AJAX XML (Wicket) contenente CDATA con HTML
                        if txt.strip().startswith('<?xml') or '<ajax-response' in txt:
                            import re
                            cdata_blocks = re.findall(r'<!\[CDATA\[(.*?)\]\]>', txt, flags=re.S)
                            for block in cdata_blocks:
                                inner = BeautifulSoup(block, 'lxml')
                                for row in inner.find_all('tr'):
                                    cols = row.find_all('td')
                                    if len(cols) >= 2:
                                        key = cols[0].get_text(strip=True)
                                        val_str = cols[1].get_text(strip=True).replace('%', '').replace(',', '.')
                                        try:
                                            val = float(val_str)
                                            if val < 101:
                                                geo_dict[key] = val
                                        except Exception:
                                            pass
                        else:
                            extra_soup = BeautifulSoup(txt, 'lxml')
                            for row in extra_soup.find_all('tr'):
                                cols = row.find_all('td')
                                if len(cols) >= 2:
                                    key = cols[0].text.strip()
                                    val_str = cols[1].text.strip().replace('%', '').replace(',', '.')
                                    try:
                                        val = float(val_str)
                                        if val < 101:
                                            geo_dict[key] = val
                                    except Exception:
                                        pass
                except Exception as e:
                    st.warning(f"⚠️ Impossibile caricare dati extra: {e}")

            table = h3_geo.find_next('table')
            if table:
                for row in table.find_all('tr'):
                    cols = row.find_all('td')
                    if len(cols) >= 2:
                        key = cols[0].text.strip()
                        val_str = cols[1].text.strip().replace('%', '').replace(',', '.')
                        try:
                            val = float(val_str)
                            if val < 101:
                                geo_dict[key] = val
                        except (ValueError, TypeError):
                            pass

        # --- SETTORI ---
        h3_sec = soup.find('h3', string=lambda text: text and 'Settori' in text)
        if h3_sec:
            load_more_link = soup.find('a', class_='etf-holdings_sectors_load-more_link')

            if load_more_link:
                extra_href = load_more_link.get('href')
                extra_url = None
                if extra_href and extra_href not in ['#', 'javascript:void(0)', '']:
                    extra_url = extra_href
                if not extra_url or extra_url in ['#', 'javascript:void(0)', '']:
                    import re
                    scripts_text = ' '.join([s.string or '' for s in soup.find_all('script')])
                    m = re.search(r'Wicket\.Ajax\.ajax\(\{[^}]*u\"?:\s*\"([^\"]*holdingsSection-sectors-loadMoreSectors[^\"]*)\"', scripts_text)
                    if not m:
                        m = re.search(r'Wicket\.Ajax\.ajax\(\{[^}]*u\'?:\s*\'([^\']*holdingsSection-sectors-loadMoreSectors[^\']*)\'', scripts_text)
                    if m:
                        extra_url = m.group(1)
                if extra_url:
                    if not extra_url.startswith('http'):
                        extra_url = f"https://www.justetf.com{extra_url}"

                try:
                    extra_response = None
                    if '_wicket=1' in extra_url or 'loadMore' in extra_url or 'holdingsSection' in extra_url:
                        extra_response = _request_wicket_ajax(isin, extra_url, headers)
                    if extra_response is None:
                        extra_response = requests.get(extra_url, headers=headers, timeout=10)
                    extra_response.raise_for_status()

                    try:
                        extra_data = extra_response.json()
                        if isinstance(extra_data, dict) and 'sectors' in extra_data:
                            sec_dict.update(extra_data['sectors'])
                    except Exception:
                        txt = extra_response.text
                        if txt.strip().startswith('<?xml') or '<ajax-response' in txt:
                            import re
                            cdata_blocks = re.findall(r'<!\[CDATA\[(.*?)\]\]>', txt, flags=re.S)
                            for block in cdata_blocks:
                                inner = BeautifulSoup(block, 'lxml')
                                for row in inner.find_all('tr'):
                                    cols = row.find_all('td')
                                    if len(cols) >= 2:
                                        key = cols[0].get_text(strip=True)
                                        val_str = cols[1].get_text(strip=True).replace('%', '').replace(',', '.')
                                        try:
                                            val = float(val_str)
                                            if val < 101:
                                                sec_dict[key] = val
                                        except Exception:
                                            pass
                        else:
                            extra_soup = BeautifulSoup(txt, 'lxml')
                            for row in extra_soup.find_all('tr'):
                                cols = row.find_all('td')
                                if len(cols) >= 2:
                                    key = cols[0].text.strip()
                                    val_str = cols[1].text.strip().replace('%', '').replace(',', '.')
                                    try:
                                        val = float(val_str)
                                        if val < 101:
                                            sec_dict[key] = val
                                    except Exception:
                                        pass
                except Exception as e:
                    st.warning(f"⚠️ Impossibile caricare dati settori extra: {e}")

            table = h3_sec.find_next('table')
            if table:
                for row in table.find_all('tr'):
                    cols = row.find_all('td')
                    if len(cols) >= 2:
                        key = cols[0].text.strip()
                        val_str = cols[1].text.strip().replace('%', '').replace(',', '.')
                        try:
                            val = float(val_str)
                            if val < 101:
                                sec_dict[key] = val
                        except (ValueError, TypeError):
                            pass

        return geo_dict, sec_dict

    except Exception as e:
        st.error(f"Scraping fallito per {isin}: {e}")
        return {}, {}
    

def _fetch_justetf_playwright(isin):
    """
    Usa Playwright - più leggero e auto-gestito di Selenium.
    Gestisce cookie banner e click su "Mostra di più" che espande la tabella principale.
    """
    try:
        from playwright.sync_api import sync_playwright
        geo_dict, sec_dict = {}, {}

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            url = f"https://www.justetf.com/it/etf-profile.html?isin={isin}"
            page.goto(url, wait_until='networkidle')
            
            # Chiudi cookie banner se presente (blocca i click)
            try:
                cookie_btn = page.locator('#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll')
                if cookie_btn.is_visible(timeout=3000):
                    cookie_btn.click()
                    page.wait_for_timeout(500)
            except Exception:
                pass  # Cookie già accettati o banner non presente

            # --- PAESI ---
            try:
                countries_link = page.locator('[data-testid="etf-holdings_countries_load-more_link"]')
                if countries_link.is_visible(timeout=2000):
                    countries_link.click()
                    page.wait_for_timeout(1500)  # Aspetta espansione tabella
            except Exception:
                pass

            # Estrai dati dalla tabella principale (ora espansa)
            rows = page.locator('h3:text-is("Paesi") ~ table tr').all()
            for row in rows:
                cols = row.locator('td').all()
                if len(cols) >= 2:
                    try:
                        key = cols[0].inner_text().strip()
                        val_str = cols[1].inner_text().strip().replace('%', '').replace(',', '.')
                        val = float(val_str)
                        if 0 < val < 101:
                            geo_dict[key] = val
                    except Exception:
                        pass

            # --- SETTORI ---
            try:
                sectors_link = page.locator('[data-testid="etf-holdings_sectors_load-more_link"]')
                if sectors_link.is_visible(timeout=2000):
                    sectors_link.click()
                    page.wait_for_timeout(1500)
            except Exception:
                pass

            rows = page.locator('h3:text-is("Settori") ~ table tr').all()
            for row in rows:
                cols = row.locator('td').all()
                if len(cols) >= 2:
                    try:
                        key = cols[0].inner_text().strip()
                        val_str = cols[1].inner_text().strip().replace('%', '').replace(',', '.')
                        val = float(val_str)
                        if 0 < val < 101:
                            sec_dict[key] = val
                    except Exception:
                        pass

            browser.close()

        return geo_dict, sec_dict

    except ImportError:
        st.error("⚠️ Installa Playwright: pip install playwright && playwright install chromium")
        return {}, {}
    except Exception as e:
        st.error(f"❌ Playwright fallito: {e}")
        return {}, {}

def sync_prices(df_trans, df_map):
    if df_trans.empty or df_map.empty: return 0
    df_full = df_trans.merge(df_map, on='isin', how='left', suffixes=('_trans', '_map'))
    if 'mapping_id' not in df_full.columns and 'id_map' in df_full.columns:
        df_full = df_full.rename(columns={'id_map': 'mapping_id'})
    
    # Usa TUTTI i mapping_id mappati, non solo quelli posseduti
    all_mapping_ids = df_map['mapping_id'].tolist()
    if not all_mapping_ids: return 0

    df_prices_all = get_data("prices")
    if not df_prices_all.empty:
        df_prices_all['date'] = pd.to_datetime(df_prices_all['date'], errors='coerce').dt.tz_localize(None).dt.normalize()
    
    new_data = []
    errors = []
    bar = st.progress(0, text="Sincronizzazione prezzi...")
    
    today = datetime.now().date()

    for i, m_id in enumerate(all_mapping_ids):
        # Trova la data massima di possesso per questo mapping_id
        max_date = df_full[df_full['mapping_id'] == m_id]['date'].max()
        print(f"DEBUG sync_prices: m_id {m_id}, max_date {max_date}")
        if pd.isna(max_date):
            print("Skipping, no possession")
            bar.progress((i + 1) / len(all_mapping_ids))
            continue
        
        # End date = max_date + 1 giorno (per includere l'ultimo giorno di possesso)
        end_date = (max_date + timedelta(days=1)).date()
        if end_date > today:
            end_date = today
        print(f"end_date {end_date}")
        
        # Ottieni il ticker per il download
        ticker_row = df_map[df_map['mapping_id'] == m_id]
        if ticker_row.empty:
            bar.progress((i + 1) / len(all_mapping_ids))
            continue
        t = ticker_row['ticker'].iloc[0]
        
        start_date = "2020-01-01"
        needs_update = True
        
        if not df_prices_all.empty:
            existing_prices = df_prices_all[df_prices_all['ticker'] == t]
            if not existing_prices.empty:
                last_date = existing_prices['date'].max().date()
                print(f"last_date in DB {last_date}")
                if last_date >= end_date:
                    print("Already updated")
                    needs_update = False
        
        if needs_update:
            try:
                hist = yf.download(t, start=start_date, end=end_date + timedelta(days=1), progress=False)
                if not hist.empty:
                    hist = hist[['Close']].reset_index()
                    hist.columns = ['date', 'close_price']
                    hist['date'] = pd.to_datetime(hist['date']).dt.normalize()
                    hist['mapping_id'] = m_id  # Salva con mapping_id corretto
                    new_data.extend(hist.to_dict('records'))
                    print(f"Downloaded {len(hist)} prices for {t}")
            except Exception as e:
                errors.append(t)
                print(f"Error for {t}: {e}")
        bar.progress((i + 1) / len(all_mapping_ids))
    
    bar.empty()
    if errors:
        st.warning(f"Problemi con alcuni ticker: {', '.join(errors)}")

    if new_data:
        df_new = pd.DataFrame(new_data)
        df_new['date'] = pd.to_datetime(df_new['date']).dt.normalize()
        
        # Unisci e rimuovi duplicati
        before = len(df_prices_all)
        df_combined = pd.concat([df_prices_all, df_new], ignore_index=True)
        df_combined.drop_duplicates(subset=['date', 'mapping_id'], keep='last', inplace=True)
        after = len(df_combined)
        added = after - before

        if added > 0:
            save_data(df_combined, "prices", method='replace')
            st.success(f"✅ Aggiunti {added} nuovi prezzi.")
        else:
            st.info("✅ Prezzi già aggiornati, nessun nuovo dato aggiunto.")
        return added
    
    st.info("✅ Prezzi già aggiornati, nessun nuovo dato aggiunto.")
    return 0