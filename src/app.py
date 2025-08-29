# -*- coding: utf-8 -*-
import math
import hashlib
import numpy as np
import pandas as pd
import streamlit as st
import pydeck as pdk
import pgeocode  # requis dans requirements
from pathlib import Path

st.set_page_config(page_title="Île-de-France • appartements (SeLoger)", layout="wide")
st.title("🏙️ Île-de-France • appartements (SeLoger)")

# ---------- chemin robuste vers data/cleaned_data.csv ----------
BASE_DIR = Path(__file__).resolve().parent.parent  # remonte de src/ vers la racine
DATA_PATH = BASE_DIR / "data" / "cleaned_data.csv"
if not DATA_PATH.exists():
    st.warning("Pas encore de données. Lance le scraping puis `python src/cleaner.py`.")
    st.stop()

# ------------------ Chargement & hygiène ------------------
df = pd.read_csv(DATA_PATH)

for col in ["price_eur", "surface_m2", "price_per_m2", "latitude", "longitude", "rooms"]:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")

# Zip code propre : 5 chiffres + une version str pour l'affichage
if "zipcode" in df.columns:
    z = df["zipcode"].astype(str).fillna("")
    z = z.replace(r"\D", "", regex=True).str[:5]
    z = z.where(z.str.len() == 5, np.nan)
    df["zipcode"] = pd.to_numeric(z, errors="coerce")
    df["zipcode_str"] = z
else:
    df["zipcode"] = np.nan
    df["zipcode_str"] = np.nan

# ------------------ Compléter lat/lon par code postal ------------------
LAT_MIN, LAT_MAX = 48.0, 49.3
LON_MIN, LON_MAX = 1.45, 3.57

def in_idf(lat, lon):
    try:
        return (
            (lat is not None)
            and (lon is not None)
            and (LAT_MIN <= float(lat) <= LAT_MAX)
            and (LON_MIN <= float(lon) <= LON_MAX)
        )
    except Exception:
        return False

# on marque les lignes sans coordonnées AVANT remplissage (pour savoir lesquelles viennent du CP)
mask_missing = df["latitude"].isna() | df["longitude"].isna()
df["_from_zip"] = mask_missing.copy()

cand = df.loc[mask_missing, "zipcode_str"].dropna().unique()
if cand.size > 0:
    nomi = pgeocode.Nominatim("fr")
    geo = nomi.query_postal_code(list(cand))
    mapping = {
        str(pc): (lat, lon)
        for pc, lat, lon in zip(
            geo["postal_code"].astype(str),
            geo["latitude"],
            geo["longitude"],
        )
        if pd.notna(lat) and pd.notna(lon)
    }

    def fill_row(row):
        if (pd.isna(row["latitude"]) or pd.isna(row["longitude"])) and pd.notna(row["zipcode_str"]):
            key = str(row["zipcode_str"])
            if key in mapping:
                lat, lon = mapping[key]
                if pd.notna(lat) and pd.notna(lon) and in_idf(lat, lon):
                    row["latitude"]  = float(lat)
                    row["longitude"] = float(lon)
        return row

    df = df.apply(fill_row, axis=1)

# ------------------ JITTER STABLE pour éviter les superpositions ------------------
def jitter_stable(lat, lon, key, meters=120):
    """
    Décale (lat, lon) d'un petit rayon <= meters de manière déterministe selon `key`.
    1° lat ≈ 111_111 m ; 1° lon ≈ 111_111 * cos(lat) m
    """
    try:
        h = int(hashlib.sha1(str(key).encode("utf-8")).hexdigest(), 16)
        angle = (h % 3600) / 3600.0 * 2 * math.pi
        # rayon en mètres : entre 0.3*meters et 1.0*meters (évite un vrai 0)
        radius = ((h // 3600) % 1000) / 1000.0
        r = 0.3 * meters + 0.7 * meters * radius
        dlat = r / 111_111.0 * math.cos(angle)
        dlon = r / (111_111.0 * math.cos(math.radians(lat))) * math.sin(angle)
        return lat + dlat, lon + dlon
    except Exception:
        return lat, lon

# ne jitter que si : (1) coordonnées issues du CP ET (2) il y a >1 annonce sur ce CP
if "_from_zip" in df.columns:
    counts = (
        df.loc[df["_from_zip"] & df["zipcode_str"].notna(), "zipcode_str"]
          .map(df["zipcode_str"].value_counts())
    )
    df["_jitter_me"] = df["_from_zip"] & df["zipcode_str"].notna() & (counts > 1)

    def add_jitter(row):
        if bool(row.get("_jitter_me")) and pd.notna(row["latitude"]) and pd.notna(row["longitude"]):
            key = row.get("url") or row.get("title") or row.name
            row["latitude"], row["longitude"] = jitter_stable(row["latitude"], row["longitude"], key)
        return row

    df = df.apply(add_jitter, axis=1)

# on nettoie les colonnes techniques
df = df.drop(columns=["_from_zip", "_jitter_me"], errors="ignore")

# ------------------ Filtres ------------------
c1, c2, c3 = st.columns(3)

with c1:
    if "price_eur" in df and df["price_eur"].notna().any():
        pmin, pmax = float(df["price_eur"].min()), float(df["price_eur"].max())
        r = st.slider("Prix (€)", pmin, pmax, (pmin, pmax))
    else:
        r = (0.0, 1e12)

with c2:
    if "surface_m2" in df and df["surface_m2"].notna().any():
        smin, smax = float(df["surface_m2"].min()), float(df["surface_m2"].max())
        s = st.slider("Surface (m²)", smin, smax, (smin, smax))
    else:
        s = (0.0, 1e6)

with c3:
    cities = sorted([c for c in df.get("city", pd.Series()).dropna().unique().tolist() if isinstance(c, str)])
    sel = st.multiselect("Villes", cities, default=cities[: min(5, len(cities))])

mask = df["price_eur"].between(*r) & df["surface_m2"].between(*s)
if sel:
    mask &= df["city"].isin(sel)

fdf = df[mask].copy()

# ------------------ Carte ------------------
st.subheader("🗺️ Carte")

gdf = (
    fdf.dropna(subset=["latitude", "longitude"])
       .loc[lambda d: d.apply(lambda r: in_idf(r["latitude"], r["longitude"]), axis=1)]
       .copy()
)

def fmt_k(v):
    try:
        return f"{int(round(float(v)/1000.0))}k€"
    except Exception:
        return ""

gdf["price_label"] = gdf["price_eur"].apply(fmt_k)

st.caption(f"Annonces après filtres : {len(fdf)} • avec coordonnées en IDF : {len(gdf)}")

if not gdf.empty:
    view = pdk.ViewState(
        latitude=float(gdf["latitude"].mean()),
        longitude=float(gdf["longitude"].mean()),
        zoom=10,
        pitch=0,
    )

    point_layer = pdk.Layer(
        "ScatterplotLayer",
        data=gdf,
        get_position="[longitude, latitude]",
        get_radius=70,
        radius_min_pixels=4,
        radius_max_pixels=8,
        get_fill_color=[255, 90, 60, 200],
        pickable=True,
    )

    # IMPORTANT: deck.gl attend des constantes sous forme de chaînes JSON
    text_layer = pdk.Layer(
        "TextLayer",
        data=gdf,
        get_position="[longitude, latitude]",
        get_text="price_label",
        get_color=[255, 255, 255, 220],
        get_size=16,
        get_text_anchor='"start"',          # au lieu de 'left'
        get_alignment_baseline='"center"',  # au lieu de 'middle'
        get_pixel_offset=[8, 0],
    )

    st.pydeck_chart(
        pdk.Deck(
            map_style="mapbox://styles/mapbox/dark-v11",
            initial_view_state=view,
            layers=[point_layer, text_layer],
            tooltip={"text": "{title}\n{price_eur} €  {surface_m2} m²\n{city} {zipcode_str}"},
        )
    )
else:
    st.info("Aucun point avec coordonnées (latitude/longitude) en Île-de-France.")

# ------------------ Tableau (numéroté à partir de 1) ------------------
st.subheader("📋 Tableau")

cols_order = [
    "title", "price_eur", "surface_m2", "price_per_m2",
    "rooms", "city", "zipcode", "latitude", "longitude", "url"
]
show = fdf[[c for c in cols_order if c in fdf.columns]].reset_index(drop=True).copy()
show.insert(0, "N°", range(1, len(show) + 1))

st.dataframe(
    show,
    use_container_width=True,
    hide_index=True,
    column_config={
        "price_eur":     st.column_config.NumberColumn("prix (€)",     format="%.0f"),
        "surface_m2":    st.column_config.NumberColumn("surface (m²)", format="%.2f"),
        "price_per_m2":  st.column_config.NumberColumn("€/m²",         format="%.0f"),
        "rooms":         st.column_config.NumberColumn("pièces",       format="%.0f"),
        "zipcode":       st.column_config.NumberColumn("zipcode",      format="%.0f", step=1),
        "latitude":      st.column_config.NumberColumn("latitude",     format="%.5f"),
        "longitude":     st.column_config.NumberColumn("longitude",    format="%.5f"),
    },
)

with st.expander("🔗 Ouvrir les annonces sélectionnées"):
    for _, r in fdf.iterrows():
        url = r.get("url")
        if isinstance(url, str) and url.strip():
            st.write(f"- [{r.get('title','Annonce')}]({url})")