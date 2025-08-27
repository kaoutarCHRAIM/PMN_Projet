# -*- coding: utf-8 -*-
import os
import math
import numpy as np
import pandas as pd
import streamlit as st
import pydeck as pdk
import pgeocode  # pgeocode==0.4.1 conseillé

st.set_page_config(page_title="Île-de-France • appartements (SeLoger)", layout="wide")
st.title("🏙️ Île-de-France • appartements (SeLoger)")

DATA_PATH = "data/cleaned_data.csv"
if not os.path.exists(DATA_PATH):
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
    z = z.str.replace(r"\D", "", regex=True).str[:5]
    z = z.where(z.str.len() == 5, np.nan)
    df["zipcode"] = pd.to_numeric(z, errors="coerce")
    df["zipcode_str"] = z
else:
    df["zipcode"] = np.nan
    df["zipcode_str"] = np.nan

# ------------------ Compléter lat/lon par code postal ------------------
# BBox Île-de-France (simple)
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

mask_missing = df["latitude"].isna() | df["longitude"].isna()
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
                # on ne garde que si ça tombe en IDF
                if pd.notna(lat) and pd.notna(lon) and in_idf(lat, lon):
                    row["latitude"]  = float(lat)
                    row["longitude"] = float(lon)
        return row

    df = df.apply(fill_row, axis=1)

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

# garde uniquement les points avec coordonnées et en IDF
gdf = (
    fdf.dropna(subset=["latitude", "longitude"])
       .loc[lambda d: d.apply(lambda r: in_idf(r["latitude"], r["longitude"]), axis=1)]
       .copy()
)

# libellé prix pour TextLayer
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

    text_layer = pdk.Layer(
        "TextLayer",
        data=gdf,
        get_position="[longitude, latitude]",
        get_text="price_label",
        get_color=[255, 255, 255, 220],
        get_size=16,
        get_alignment_baseline="'middle'",
        get_text_anchor="'left'",
        get_pixel_offset="[8, 0]",   # décale le texte à droite du point
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

# réordonne + numérote 1..n
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
        "price_eur":     st.column_config.NumberColumn("prix (€)",    format="%.0f"),
        "surface_m2":    st.column_config.NumberColumn("surface (m²)",format="%.0f"),
        "price_per_m2":  st.column_config.NumberColumn("€/m²",        format="%.0f"),
        "rooms":         st.column_config.NumberColumn("pièces",      format="%.0f"),
        "zipcode":       st.column_config.NumberColumn("zipcode",     format="%.0f", step=1),
        "latitude":      st.column_config.NumberColumn("latitude",    format="%.5f"),
        "longitude":     st.column_config.NumberColumn("longitude",   format="%.5f"),
    },
)

# ------------------ Liens ------------------
with st.expander("🔗 Ouvrir les annonces sélectionnées"):
    for _, r in fdf.iterrows():
        url = r.get("url")
        if isinstance(url, str) and url.strip():
            st.write(f"- [{r.get('title','Annonce')}]({url})")
