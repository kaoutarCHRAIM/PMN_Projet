# -*- coding: utf-8 -*-
import os
import re
import numpy as np
import pandas as pd
import streamlit as st
import pydeck as pdk

# géocodage par code postal
import pgeocode

st.set_page_config(page_title="Île-de-France • 20 appartements (SeLoger)", layout="wide")
st.title("🏙️ Île-de-France • 20 appartements (SeLoger)")

DATA_PATH = "data/cleaned_data.csv"
if not os.path.exists(DATA_PATH):
    st.warning("Pas encore de données. Lance le scraping puis src/cleaner.py.")
    st.stop()

# ---------- lecture + hygiène des colonnes ----------
df = pd.read_csv(DATA_PATH)

# colonnes numériques
for col in ["price_eur", "surface_m2", "price_per_m2", "latitude", "longitude", "rooms"]:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")

# zipcode propre (exactement 5 chiffres)
if "zipcode" in df.columns:
    z = df["zipcode"].astype(str).fillna("")
    z = z.str.replace(r"\D", "", regex=True).str[:5]
    z = z.where(z.str.len() == 5, np.nan)
    df["zipcode_str"] = z
else:
    df["zipcode_str"] = np.nan

# ---------- compléter lat/lon manquants par pgeocode ----------
mask_missing = df["latitude"].isna() | df["longitude"].isna()
cand = df.loc[mask_missing, "zipcode_str"].dropna().unique()

if cand.size > 0:
    # pgeocode 0.4.1 recommandé (plus stable)
    nomi = pgeocode.Nominatim("fr")
    geo = nomi.query_postal_code(list(cand))  # DataFrame
    # dictionnaire zip -> (lat, lon)
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
                if pd.notna(lat) and pd.notna(lon):
                    row["latitude"]  = float(lat)
                    row["longitude"] = float(lon)
        return row

    df = df.apply(fill_row, axis=1)

# ---------- filtres ----------
c1, c2, c3 = st.columns(3)

with c1:
    if "price_eur" in df and df["price_eur"].notna().any():
        r = st.slider(
            "Prix (€)",
            float(df["price_eur"].min()),
            float(df["price_eur"].max()),
            (float(df["price_eur"].min()), float(df["price_eur"].max())),
        )
    else:
        r = (0.0, 1e12)

with c2:
    if "surface_m2" in df and df["surface_m2"].notna().any():
        s = st.slider(
            "Surface (m²)",
            float(df["surface_m2"].min()),
            float(df["surface_m2"].max()),
            (float(df["surface_m2"].min()), float(df["surface_m2"].max())),
        )
    else:
        s = (0.0, 1e6)

with c3:
    cities = sorted([c for c in df.get("city", pd.Series()).dropna().unique().tolist() if isinstance(c, str)])
    sel = st.multiselect("Villes", cities, default=cities[: min(5, len(cities))])

mask = (df["price_eur"].between(*r)) & (df["surface_m2"].between(*s))
if sel:
    mask &= df["city"].isin(sel)

fdf = df[mask].copy()

# libellés pour la carte
if "price_eur" in fdf.columns:
    fdf["price_label"] = fdf["price_eur"].apply(lambda v: f"{int(v/1000)}k€" if pd.notna(v) else "")

# ---------- CARTE ----------
st.subheader("🗺️ Carte")

gdf = fdf.dropna(subset=["latitude", "longitude"]).copy()
st.caption(f"Annonces après filtres : {len(fdf)} • avec coordonnées : {len(gdf)}")

if not gdf.empty:
    # vue centrée
    view = pdk.ViewState(
        latitude=float(gdf["latitude"].mean()),
        longitude=float(gdf["longitude"].mean()),
        zoom=10.0,
    )
    # points
    point_layer = pdk.Layer(
        "ScatterplotLayer",
        data=gdf,
        get_position="[longitude, latitude]",
        get_radius=80,
        get_fill_color="[255, 99, 71, 160]",  # tomate translucent
        pickable=True,
    )
    # étiquette prix
    text_layer = pdk.Layer(
        "TextLayer",
        data=gdf,
        get_position="[longitude, latitude]",
        get_text="price_label",
        get_size=16,
        get_color=[255, 255, 255],
        get_alignment_baseline="bottom",
    )
    st.pydeck_chart(
        pdk.Deck(
            initial_view_state=view,
            layers=[point_layer, text_layer],
            tooltip={"text": "{title}\n{price_eur} €  {surface_m2} m²\n{city} {zipcode_str}"},
            map_style="mapbox://styles/mapbox/dark-v11",
        )
    )
else:
    st.info("Aucun point avec coordonnées (latitude/longitude).")

# ---------- TABLEAU ----------
st.subheader("📋 Tableau")
# on cache les colonnes techniques
show = fdf.drop(columns=[c for c in ["zipcode_str"] if c in fdf.columns], errors="ignore")
st.dataframe(
    show,
    use_container_width=True,
    hide_index=True,
)

# ---------- liens ----------
with st.expander("🔗 Ouvrir les annonces sélectionnées"):
    for _, r in fdf.iterrows():
        url = r.get("url")
        if isinstance(url, str) and url.strip():
            st.write(f"- [{r.get('title','Annonce')}]( {url} )")

