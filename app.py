# -*- coding: utf-8 -*-
import os
import pandas as pd
import streamlit as st
import pydeck as pdk

st.set_page_config(page_title="Île-de-France • 20 annonces (SeLoger)", layout="wide")
st.title("🏙️ Île-de-France • 20 appartements (SeLoger)")

DATA_PATH = "data/cleaned_data.csv"
if not os.path.exists(DATA_PATH):
    st.warning("Pas encore de données. Lance le scraping puis src/cleaner.py.")
    st.stop()

# --- charge sans forcer zipcode en texte
df = pd.read_csv(DATA_PATH)

# 👉 garder zipcode numérique mais sans séparateur et sans décimales
if "zipcode" in df.columns:
    df["zipcode"] = pd.to_numeric(df["zipcode"], errors="coerce").round(0)
    # pour les tooltips de la carte (chaîne affichée proprement)
    df["zipcode_txt"] = df["zipcode"].apply(lambda x: "" if pd.isna(x) else f"{int(x):d}")

# sécurise quelques colonnes numériques
for col in ["price_eur", "surface_m2", "price_per_m2", "latitude", "longitude", "rooms"]:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")

# ----------------- Filtres -----------------
c1, c2, c3 = st.columns(3)

with c1:
    if "price_eur" in df:
        r = st.slider(
            "Prix (€)",
            float(df["price_eur"].min()),
            float(df["price_eur"].max()),
            (float(df["price_eur"].min()), float(df["price_eur"].max())),
        )
    else:
        r = (0.0, 1e9)

with c2:
    if "surface_m2" in df:
        s = st.slider(
            "Surface (m²)",
            float(df["surface_m2"].min()),
            float(df["surface_m2"].max()),
            (float(df["surface_m2"].min()), float(df["surface_m2"].max())),
        )
    else:
        s = (0.0, 1e9)

with c3:
    cities = sorted([c for c in df.get("city", pd.Series()).dropna().unique().tolist() if isinstance(c, str)])
    sel = st.multiselect("Villes", cities, default=cities[: min(5, len(cities))])

mask = (df["price_eur"].between(*r)) & (df["surface_m2"].between(*s))
if sel:
    mask &= df["city"].isin(sel)

fdf = df[mask].copy()

# ----------------- Carte -----------------
st.subheader("🗺️ Carte")
gdf = fdf.dropna(subset=["latitude", "longitude"])
if not gdf.empty:
    view = pdk.ViewState(
        latitude=gdf["latitude"].mean(),
        longitude=gdf["longitude"].mean(),
        zoom=9.5,
    )
    layer = pdk.Layer(
        "ScatterplotLayer",
        data=gdf,
        get_position="[longitude, latitude]",
        get_radius=60,
        pickable=True,
    )
    st.pydeck_chart(
        pdk.Deck(
            layers=[layer],
            initial_view_state=view,
            tooltip={"text": "{title}\n{price_eur} €  {surface_m2} m²\n{city} {zipcode_txt}"},
        )
    )
else:
    st.info("Aucun point avec coordonnées.")

# ----------------- Tableau -----------------
st.subheader("📋 Tableau")
st.dataframe(
    fdf,
    column_config={
        # affiche 78170 (pas 78,170), en gardant zipcode comme nombre
        "zipcode": st.column_config.NumberColumn("zipcode", format="%.0f", step=1),
    },
)

# ----------------- Liens -----------------
with st.expander("🔗 Ouvrir les annonces sélectionnées"):
    for _, r in fdf.iterrows():
        url = r.get("url")
        if isinstance(url, str) and url:
            st.write(f"- [{r.get('title','Annonce')}]( {url} )")