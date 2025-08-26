# -*- coding: utf-8 -*-
import os, pandas as pd, streamlit as st, pydeck as pdk

st.set_page_config(page_title="Île-de-France – 20 annonces (sans passerelle)", layout="wide")
st.title("🏠 Île-de-France – 20 appartements (SeLoger)")

DATA_PATH = "data/cleaned_data.csv"
if not os.path.exists(DATA_PATH):
    st.warning("Pas encore de data. Lance parse_local_html.py (Option A) ou fetch_ads.py (Option B), puis src/cleaner.py.")
    st.stop()

df = pd.read_csv(DATA_PATH)

c1,c2,c3 = st.columns(3)
with c1:
    if "price_eur" in df:
        r = st.slider("Prix (€)", float(df["price_eur"].min()), float(df["price_eur"].max()), (float(df["price_eur"].min()), float(df["price_eur"].max())))
    else:
        r = (0.0, 1e9)
with c2:
    s = st.slider("Surface (m²)", float(df["surface_m2"].min()), float(df["surface_m2"].max()), (float(df["surface_m2"].min()), float(df["surface_m2"].max())))
with c3:
    cities = sorted([c for c in df["city"].dropna().unique().tolist() if isinstance(c, str)])
    sel = st.multiselect("Villes", cities, default=cities[: min(5, len(cities))])

mask = (df["price_eur"].between(*r)) & (df["surface_m2"].between(*s))
if sel: mask &= df["city"].isin(sel)
fdf = df[mask].copy()

st.subheader("🗺️ Carte")
gdf = fdf.dropna(subset=["latitude","longitude"])
if not gdf.empty:
    view = pdk.ViewState(latitude=gdf["latitude"].mean(), longitude=gdf["longitude"].mean(), zoom=9.5)
    layer = pdk.Layer("ScatterplotLayer", data=gdf, get_position='[longitude, latitude]', get_radius=60, pickable=True)
    st.pydeck_chart(pdk.Deck(layers=[layer], initial_view_state=view, tooltip={"text":"{title}\n{price_eur}€ · {surface_m2}m²\n{city} {zipcode}"}))
else:
    st.info("Aucun point avec coordonnées.")

st.subheader("📋 Tableau")
st.dataframe(fdf)

with st.expander("🔗 Ouvrir les annonces sélectionnées"):
    for _, r in fdf.iterrows():
        if isinstance(r.get("url"), str):
            st.write(f"- [{r['title'] or 'Voir l’annonce'}]({r['url']})")
