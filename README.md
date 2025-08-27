# Île-de-France – 20 annonces (SeLoger sans Piloterr)

Deux options **conformes et à faible volume** (pas d’anti-bot) :

**Option A — Local (recommandé)**  
1) Ouvre SeLoger dans ton navigateur, réalise ta recherche (Île-de-France, Achat Appartement).  
2) **Enregistre la/les pages HTML** (Ctrl+S) dans `data/html/`. Tu peux aussi ouvrir quelques annonces et enregistrer la page détail.  
3) Installe les dépendances :  
   ```bash
   python -m venv venv
   venv\Scripts\activate
   pip install -r requirements.txt
   ```
4) Parse :  
   ```bash
   python src/parse_local_html.py
   python src/cleaner.py
   streamlit run app.py
   ```

**Option B — URLs d’annonces (≤20, cadence lente)**  
1) Mets **jusqu'à 20** liens d'annonces dans `data/urls.txt` (une par ligne).  
2) Configure `.env` si besoin (`REQUEST_DELAY=2.5`).  
3) Lance :  
   ```bash
   python src/spider.py
   python src/cleaner.py
   streamlit run app.py
   ```

> ⚠️ Respect des CGU / robots : pas de contournement, pas de proxies ou techniques d'évasion. Usage éducatif, volume très faible.
