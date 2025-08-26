# -*- coding: utf-8 -*-
import os, json, pandas as pd, re

RAW = "data/raw_data.json"
OUT = "data/cleaned_data.csv"

LAT_MIN, LAT_MAX = 48.0, 49.3
LON_MIN, LON_MAX = 1.45, 3.57

def in_idf(lat, lon):
    try:
        lat = float(lat); lon = float(lon)
        return LAT_MIN <= lat <= LAT_MAX and LON_MIN <= lon <= LON_MAX
    except Exception:
        return False

def load_raw(path):
    """Charge raw_data en gérant:
       - JSON liste standard
       - JSON Lines (une annonce par ligne)
       - Plusieurs blocs JSON concaténés par erreur"""
    if not os.path.exists(path):
        return []
    txt = open(path, "r", encoding="utf-8", errors="ignore").read().strip()
    if not txt:
        return []
    # 1) Essayer JSON normal (liste)
    try:
        data = json.loads(txt)
        if isinstance(data, dict) and "items" in data:
            data = data["items"]
        if isinstance(data, list):
            return data
    except Exception:
        pass
    # 2) Essayer JSON Lines
    items = []
    for line in txt.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            if isinstance(obj, list):
                items.extend(obj)
            else:
                items.append(obj)
        except Exception:
            continue
    if items:
        return items
    # 3) “Réparer” un fichier concaténé: {..}{..} ou [..][..]
    fixed = txt.replace('}\n{', '},{').replace('}{', '},{').replace('][', ',')
    try:
        data = json.loads(f"[{fixed}]")
        if isinstance(data, list):
            return data
    except Exception:
        pass
    raise SystemExit("Impossible de parser data/raw_data.json (format corrompu). Supprime-le et relance le spider avec -O.")

def main():
    data = load_raw(RAW)

    rows = []
    for d in data:
        price = d.get("price")
        surface = d.get("surface_m2")
        lat = d.get("latitude"); lon = d.get("longitude")
        if price is None or surface in (None, 0, "", "0"):
            continue

        try:
            price = float(str(price).replace(" ", "").replace(",", ".").replace("€",""))
            surface = float(str(surface).replace(",", "."))
        except Exception:
            continue

        # --- ZIP: garder uniquement les chiffres, forcer 5 caractères ---
        zip_raw = str(d.get("zipcode") or "")
        zip_digits = re.sub(r"\D", "", zip_raw)   # enlève virgules, espaces, etc.
        zipcode = zip_digits[:5] if len(zip_digits) >= 5 else None

        ok_geo = lat not in (None,"") and lon not in (None,"") and in_idf(lat, lon)

        rows.append({
            "title": d.get("title"),
            "price_eur": round(price, 2),
            "surface_m2": round(surface, 2),
            "price_per_m2": round(price/surface, 2) if surface else None,
            "rooms": d.get("rooms"),
            "city": d.get("city"),
            "zipcode": zipcode,               # <-- string propre, sans virgule
            "latitude": float(lat) if ok_geo else None,
            "longitude": float(lon) if ok_geo else None,
            "url": d.get("url"),
        })

    df = pd.DataFrame(rows).drop_duplicates(subset=["url","title"])
    df.to_csv(OUT, index=False, encoding="utf-8")
    print(f"Wrote {OUT} with {len(df)} rows.")

if __name__ == "__main__":
    main()