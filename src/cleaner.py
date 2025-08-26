# -*- coding: utf-8 -*-
import os, json, pandas as pd

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

def main():
    if not os.path.exists(RAW):
        raise SystemExit("Missing data/raw_data.json. Run parse_local_html.py or fetch_ads.py first.")
    with open(RAW, "r", encoding="utf-8") as f:
        data = json.load(f)

    rows = []
    for d in data:
        price = d.get("price")
        surface = d.get("surface_m2")
        lat = d.get("latitude"); lon = d.get("longitude")
        if price is None or surface in (None, 0):
            continue

        try:
            price = float(str(price).replace(" ", "").replace(",", ".").replace("€",""))
            surface = float(str(surface).replace(",", "."))
        except Exception:
            continue

        ok_geo = lat not in (None,"") and lon not in (None,"") and in_idf(lat, lon)
        rows.append({
            "title": d.get("title"),
            "price_eur": round(price, 2),
            "surface_m2": round(surface, 2),
            "price_per_m2": round(price/surface, 2) if surface else None,
            "rooms": d.get("rooms"),
            "city": d.get("city"),
            "zipcode": d.get("zipcode"),
            "latitude": float(lat) if ok_geo else None,
            "longitude": float(lon) if ok_geo else None,
            "url": d.get("url"),
        })

    df = pd.DataFrame(rows).drop_duplicates(subset=["url","title"])
    df.to_csv(OUT, index=False, encoding="utf-8")
    print(f"Wrote {OUT} with {len(df)} rows.")

if __name__ == "__main__":
    main()
