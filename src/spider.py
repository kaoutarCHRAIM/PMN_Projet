# -*- coding: utf-8 -*-
"""
Seloger 20 URLs -> JSON (Scrapy)
- Lit data/urls.txt (≤20 uniques)
- Requêtes lentes (REQUEST_DELAY) pour rester prudent
- Parse via JSON intégré aux pages (JSON-LD / __NEXT_DATA__), sans BeautifulSoup
- Fallback HTML (meta/regex) + ville depuis l'URL si nécessaire
- À lancer avec:
    scrapy runspider src/spider.py -O data/raw_data.json -s FEED_EXPORT_ENCODING=utf-8
"""

import os
import re
import json
import time
from html import unescape

import scrapy
from scrapy.http import Request
from dotenv import load_dotenv


# ---------- Config ----------
load_dotenv()
REQUEST_DELAY = float(os.getenv("REQUEST_DELAY", "3.0"))
URLS_PATH = "data/urls.txt"

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

NBSP = u"\xa0"
THIN = u"\u202f"
IDF_ZIP_PREFIXES = ("75", "77", "78", "91", "92", "93", "94", "95")


# ---------- Helpers ----------
def norm_text(t: str) -> str:
    if not t:
        return ""
    t = unescape(t).replace(NBSP, " ").replace(THIN, " ")
    return " ".join(t.split())


def num_from_text(t: str):
    if not t:
        return None
    t = norm_text(t)
    m = re.search(r"(\d[\d\s.,]*)", t)
    if not m:
        return None
    val = m.group(1).replace(" ", "").replace(NBSP, "").replace(THIN, "").replace(",", ".")
    try:
        return float(val)
    except Exception:
        return None


def first(*vals):
    for v in vals:
        if v not in (None, "", [], {}):
            return v
    return None


def deep_get(obj, *paths):
    """Essaye plusieurs chemins 'dot' dans des dicts/listes imbriqués."""
    for path in paths:
        cur = obj
        try:
            for key in path.split("."):
                if isinstance(cur, list):
                    nxt = None
                    for it in cur:
                        if isinstance(it, dict) and key in it:
                            nxt = it[key]
                            break
                    cur = nxt if nxt is not None else (cur[0] if cur else None)
                else:
                    cur = cur[key]
            if cur not in (None, "", [], {}):
                return cur
        except Exception:
            continue
    return None


def walk_json(obj):
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from walk_json(v)
    elif isinstance(obj, list):
        for it in obj:
            yield from walk_json(it)


def parse_json_blocks(response):
    """Récupère des objets JSON depuis <script> (JSON-LD, __NEXT_DATA__, etc.)."""
    objs = []

    # 1) JSON "purs"
    for txt in response.css('script[type="application/ld+json"]::text, script[type="application/json"]::text').getall():
        txt = (txt or "").strip()
        if not txt:
            continue
        try:
            data = json.loads(txt)
            objs.append(data)
        except Exception:
            pass

    # 2) Balises <script> génériques : __NEXT_DATA__ = {...}
    for raw in response.css("script::text").getall():
        t = (raw or "").strip()
        if not t:
            continue
        # Next.js __NEXT_DATA__
        m = re.search(r"__NEXT_DATA__\s*=\s*({.*?});", t, flags=re.S)
        if m:
            try:
                data = json.loads(m.group(1))
                objs.append(data)
            except Exception:
                pass
            continue
        # sinon, tenter 1 gros objet JSON s'il semble pertinent
        if "price" in t or "offers" in t or "address" in t or "geo" in t:
            m2 = re.search(r"({.*})", t, flags=re.S)
            if m2:
                try:
                    data = json.loads(m2.group(1))
                    objs.append(data)
                except Exception:
                    pass

    return objs


def extract_from_jsonobjs(jsonobjs):
    """Essaye de sortir les champs clés depuis tous les objets JSON trouvés."""
    price = surface = rooms = city = zipcode = lat = lon = None
    url = None
    title = None

    for obj in jsonobjs:
        for d in walk_json(obj):
            # URL / titre
            url   = first(url, d.get("url"), deep_get(d, "mainEntityOfPage.@id"))
            title = first(title, d.get("name"), d.get("headline"), d.get("title"))

            # prix
            price = first(
                price,
                d.get("price"),
                deep_get(d, "offers.price"),
                deep_get(d, "offers.0.price"),
                deep_get(d, "price.value"),
                deep_get(d, "pricing.price"),
                deep_get(d, "ad.price.value"),
            )

            # surface
            surface = first(
                surface,
                d.get("floorSize"), d.get("area"), d.get("livingArea"),
                deep_get(d, "floorSize.value"),
                deep_get(d, "surface.value"),
                deep_get(d, "property.surface"),
                deep_get(d, "habitableSurface"),
            )

            # pièces
            rooms = first(
                rooms,
                d.get("numberOfRooms"), d.get("rooms"),
                deep_get(d, "ad.rooms"), deep_get(d, "property.rooms"),
            )

            # adresse
            city = first(
                city,
                deep_get(d, "address.addressLocality"),
                deep_get(d, "address.locality"),
                deep_get(d, "location.city"),
                d.get("city"),
            )
            zipcode = first(
                zipcode,
                deep_get(d, "address.postalCode"),
                deep_get(d, "address.zipCode"),
                d.get("postalCode"),
            )

            # géo
            lat = first(lat, deep_get(d, "geo.latitude"), d.get("latitude"))
            lon = first(lon, deep_get(d, "geo.longitude"), d.get("longitude"))

    # Normalisation types
    if isinstance(price, str):   price   = num_from_text(price)
    if isinstance(surface, str): surface = num_from_text(surface)
    if isinstance(rooms, str):   rooms   = num_from_text(rooms)

    return {
        "title": norm_text(title) if title else None,
        "price": price,
        "surface_m2": surface,
        "rooms": rooms,
        "city": norm_text(city) if city else None,
        "zipcode": zipcode,
        "latitude": lat,
        "longitude": lon,
        "url": url,
    }


# ------- Heuristiques ville/CP depuis HTML/URL -------
def extract_zip(text: str):
    if not text:
        return None
    zips = re.findall(r"\b\d{5}\b", text)
    for z in reversed(zips):
        if z[:2] in IDF_ZIP_PREFIXES:
            return z
    return None


def city_from_zip_context(text: str, zipcode: str):
    if not text or not zipcode:
        return None
    m = re.search(r"([A-Za-zÀ-ÖØ-öø-ÿ' \-]{2,})\s*\(\s*" + re.escape(zipcode) + r"\s*\)", text)
    return norm_text(m.group(1)) if m else None


def city_from_url(url: str):
    # ex: .../annonces/achat/appartement/la-celle-saint-cloud-78/...
    if not url:
        return None
    m = re.search(r"/annonces/achat/appartement/([^/]+)/", url)
    if not m:
        return None
    slug = m.group(1)
    # retire le suffixe -78/-92 etc.
    slug = re.sub(r"-\d{2}$", "", slug)
    parts = [p for p in slug.split("-") if p]
    return " ".join(w.capitalize() for w in parts) if parts else None


def fallback_from_html(response):
    # Titre depuis meta/h1/title
    title = first(
        response.css('meta[property="og:title"]::attr(content)').get(),
        response.css('meta[name="twitter:title"]::attr(content)').get(),
        response.css("h1::text").get(),
        response.css("title::text").get(),
    )
    title = norm_text(title)

    text = norm_text(response.text)

    # Prix / surface / pièces (regex)
    price = None
    m = re.search(r"(\d[\d\s.,]*)\s*€", text)
    if m:
        price = num_from_text(m.group(1))

    surface = None
    m = re.search(r"(\d[\d\s.,]*)\s*m[²2]", text, flags=re.I)
    if m:
        surface = num_from_text(m.group(1))

    rooms = None
    m = re.search(r"(\d+)\s*pi[eè]ce", text, flags=re.I)
    if m:
        rooms = num_from_text(m.group(1))

    # Code postal + ville
    zipcode = extract_zip(text)
    city = city_from_zip_context(text, zipcode)
    if not city:
        city = city_from_url(response.url)

    return {
        "title": title or None,
        "price": price,
        "surface_m2": surface,
        "rooms": rooms,
        "city": city,
        "zipcode": zipcode,
        "latitude": None,
        "longitude": None,
        "url": response.url,
    }


# ---------- Spider ----------
class SelogerSpider(scrapy.Spider):
    name = "seloger_20"
    custom_settings = {
        "DOWNLOAD_DELAY": REQUEST_DELAY,
        "CONCURRENT_REQUESTS": 2,
        "DEFAULT_REQUEST_HEADERS": {
            "User-Agent": UA,
            "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
        "LOG_LEVEL": "INFO",
    }

    def start_requests(self):
        if not os.path.exists(URLS_PATH):
            raise RuntimeError("Ajoute jusqu'à 20 URLs dans data/urls.txt")
        with open(URLS_PATH, "r", encoding="utf-8") as f:
            urls = [u.strip() for u in f if u.strip()]

        # uniques + limite 20
        seen, uniq = set(), []
        for u in urls:
            if u not in seen:
                seen.add(u)
                uniq.append(u)
            if len(uniq) >= 20:
                break

        for i, url in enumerate(uniq, 1):
            yield Request(url, callback=self.parse_detail, cb_kwargs={"idx": i, "total": len(uniq)})

    def parse_detail(self, response, idx, total):
        jsonobjs = parse_json_blocks(response)
        item = extract_from_jsonobjs(jsonobjs)

        # Forcer l'URL de la page courante
        item["url"] = response.url

        # Si le "title" est générique, on le force à None pour déclencher le fallback
        if item.get("title") and norm_text(item["title"]).lower() in ("seloger", "seloger.com", "www.seloger.com"):
            item["title"] = None

        # Fallback si les champs essentiels sont absents
        if not any([item.get("price"), item.get("surface_m2"), item.get("rooms"), item.get("city"), item.get("zipcode")]):
            fb = fallback_from_html(response)
            for k, v in fb.items():
                if item.get(k) in (None, "", [], {}):
                    item[k] = v

        # Dernière chance : si pas de ville mais on peut la déduire de l'URL
        if not item.get("city"):
            item["city"] = city_from_url(response.url)

        self.logger.info(
            f"[{idx}/{total}] price={item.get('price')} surface={item.get('surface_m2')} "
            f"rooms={item.get('rooms')} city={item.get('city')} zipcode={item.get('zipcode')}"
        )

        yield item
        time.sleep(REQUEST_DELAY)  # petite pause supplémentaire
