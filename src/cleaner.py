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

        # prix/surface minimums requis
        if price is None or surface in (None, 0, "", "0"):
            continue

        try:
            price = float(str(price).replace(" ", "").replace(",", ".").replace("€", ""))
            surface = float(str(surface).replace(",", "."))
            if surface <= 0:
                continue
        except Exception:
            continue

        # --- ZIP: ne garder que les chiffres, forcer 5 caractères ---
        zip_raw = str(d.get("zipcode") or "")
        zip_digits = re.sub(r"\D", "", zip_raw)  # enlève virgules, espaces, etc.
        zipcode = zip_digits[:5] if len(zip_digits) >= 5 else None  # string propre

        # coordonnées présentes et dans l'IDF ?
        ok_geo = lat not in (None, "") and lon not in (None, "") and in_idf(lat, lon)

        rows.append({
            "title": d.get("title"),
            "price_eur": round(price, 2),
            "surface_m2": round(surface, 2),
            "price_per_m2": round(price / surface, 2) if surface else None,
            "rooms": d.get("rooms"),
            "city": d.get("city"),
            "zipcode": zipcode,  # string sans virgule/point
            "latitude": float(lat) if ok_geo else None,
            "longitude": float(lon) if ok_geo else None,
            "url": d.get("url"),
        })

    df = pd.DataFrame(rows)

    # Normalisation des types
    if not df.empty:
        # zipcode en string
        df["zipcode"] = df["zipcode"].astype("string")
        # prix/surface/€/m² numériques
        for col in ["price_eur", "surface_m2", "price_per_m2"]:
            if col in df:
                df[col] = pd.to_numeric(df[col], errors="coerce")

    # -------------------------------
    # Géocodage via pgeocode (France)
    # -------------------------------
    if not df.empty:
        try:
            import pgeocode
            # On ne géocode que les lignes sans coords
            need_geo = df["latitude"].isna() | df["longitude"].isna()
            if need_geo.any():
                nomi = pgeocode.Nominatim("fr")
                z = df.loc[need_geo, "zipcode"].fillna("").astype(str)
                if len(z):
                    geo = nomi.query_postal_code(z)
                    # Convertir colonnes lat/lon en numérique
                    df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
                    df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")
                    # Remplir les NA par le géocodage
                    df.loc[need_geo, "latitude"] = df.loc[need_geo, "latitude"].fillna(geo["latitude"].values)
                    df.loc[need_geo, "longitude"] = df.loc[need_geo, "longitude"].fillna(geo["longitude"].values)
        except Exception as e:
            print("Géocodage pgeocode ignoré (erreur):", e)

    # Filtrer les coordonnées hors IDF (on les met à NaN)
    if not df.empty and "latitude" in df and "longitude" in df:
        mask_idf = df.apply(lambda r: in_idf(r["latitude"], r["longitude"]), axis=1)
        df.loc[~mask_idf, ["latitude", "longitude"]] = pd.NA

    # Drop/tri final
    df = df.drop_duplicates(subset=["url", "title"])

    # Export CSV
    df.to_csv(OUT, index=False, encoding="utf-8")
    print(f"Wrote {OUT} with {len(df)} rows.")


if __name__ == "__main__":
    main()