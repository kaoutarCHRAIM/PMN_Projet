# -*- coding: utf-8 -*-
"""
Option A — Parsing **LOCAL** de fichiers HTML SeLoger (enregistrés manuellement).
- Dépose tes fichiers dans data/html/ (pages résultats et/ou pages d'annonces).
- On extrait un sous-ensemble: titre, prix, surface, pièces, ville, CP, lat/lon, URL.
- Résultat: data/raw_data.json puis data/cleaned_data.csv (via cleaner).
"""
import os, re, json
from bs4 import BeautifulSoup as BS

HTML_DIR = "data/html"
OUT_JSON = "data/raw_data.json"

def pick_num(txt):
    if not txt: return None
    m = re.search(r"[\d\s]+(?:[\.,]\d+)?", txt)
    if not m: return None
    return m.group(0).replace(" ", "").replace(",", ".")

def parse_listing_card(card):
    # Heuristique générique (le DOM peut changer)
    title = card.get_text(" ", strip=True)[:140]
    price = None
    surface = None
    rooms = None
    url = None

    a = card.find("a", href=True)
    if a:
        url = a["href"]

    # Essais sur quelques libellés fréquents
    for tag in card.find_all(True):
        t = tag.get_text(" ", strip=True).lower()
        if any(k in t for k in ["€", "prix"]):
            price = pick_num(t)
        if any(k in t for k in ["m²", "surface"]):
            surface = pick_num(t)
        if "pièce" in t or "pieces" in t or "pièces" in t:
            rooms = pick_num(t)

    return {"title": title or None, "price": price, "surface_m2": surface, "rooms": rooms, "url": url}

def parse_file(path):
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        html = f.read()
    soup = BS(html, "lxml")

    items = []

    # 1) Essayer des blocs d'annonces (cards)
    cards = soup.select("[data-test]") or soup.select("article,div,li")
    for c in cards[:200]:  # garde une limite
        it = parse_listing_card(c)
        if any([it.get("price"), it.get("surface_m2"), it.get("url")]):
            items.append(it)

    # 2) Si page détail: essayer de capturer des infos plus précises
    # (heuristiques simples)
    h1 = soup.find("h1")
    if h1:
        t = h1.get_text(" ", strip=True)
        if t and len(t) > 5:
            # injecte un enregistrement "detail" minimal
            items.append({"title": t})

    return items

def main():
    all_items = []
    for name in os.listdir(HTML_DIR):
        if not name.lower().endswith((".html", ".htm")):
            continue
        path = os.path.join(HTML_DIR, name)
        try:
            items = parse_file(path)
            all_items.extend(items)
            print(f"Parsed {name}: +{len(items)} items")
        except Exception as e:
            print("Skip", name, e)

    # dédoublonner grossièrement par URL + titre
    seen = set()
    dedup = []
    for it in all_items:
        key = (it.get("url"), it.get("title"))
        if key in seen: 
            continue
        seen.add(key)
        dedup.append(it)

    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(dedup[:200], f, ensure_ascii=False, indent=2)
    print(f"Wrote {OUT_JSON} with {len(dedup[:200])} items")

if __name__ == "__main__":
    main()
