# Île-de-France – Annonces immobilières (SeLoger)

[![CI – Scrape & Clean](https://github.com/kaoutarCHRAIM/PMN_Projet/actions/workflows/main.yml/badge.svg)](https://github.com/kaoutarCHRAIM/PMN_Projet/actions)

**App en ligne :** https://pmnprojet-aqcouv52qt3k9bamgwkxgz.streamlit.app/  
**Historique CI/CD :** https://github.com/kaoutarCHRAIM/PMN_Projet/actions  
**Données à jour :** https://github.com/kaoutarCHRAIM/PMN_Projet/blob/master/data/cleaned_data.csv

## Résumé du projet
Ce projet met en place un pipeline complet pour :
- Collecter des annonces immobilières (pages HTML sauvegardées ou spider Scrapy).
- Nettoyer et normaliser les données (prix, surface, €/m², pièces, code postal, coordonnées).
- Explorer les résultats dans un tableau de bord Streamlit (carte + tableau).
- Automatiser la mise à jour via GitHub Actions (CI/CD).

---

## 1. Dépôt GitHub structuré
Le dépôt est organisé de manière claire :

| Chemin                       | Rôle                                               |
|------------------------------|----------------------------------------------------|
| `src/spider.py`              | Spider/Parser — extraction depuis HTML (titre, prix, surface, pièces, ville, CP, lat/lon, URL). |
| `src/parse_local_html.py`    | Variante pour parsing de fichiers HTML locaux.     |
| `src/cleaner.py`             | Nettoyage robuste (formats JSON variés) + normalisation, géocodage, filtre ÎDF, export CSV. |
| `src/app.py`                 | Application Streamlit (filtres, carte pydeck, tableau numéroté, liens). |
| `data/raw_data.json`         | Données brutes (sortie spider).                    |
| `data/cleaned_data.csv`      | Données nettoyées (entrée Streamlit).              |
| `.github/workflows/main.yml` | Pipeline CI/CD GitHub Actions.                     |
| `requirements.txt`           | Dépendances Python.                                |

---

## 2. Pipeline CI/CD fonctionnel
Le fichier `.github/workflows/main.yml` assure l’automatisation :
- **Déclencheurs** : manuel (`workflow_dispatch`) + quotidien (cron 06:15 UTC).
- **Étapes** : checkout → setup Python 3.11 → install deps → run spider → run cleaner → check CSV → commit conditionnel.
- **Robustesse** : `continue-on-error: true` pour éviter l’échec global.
- **Condition de commit** : push uniquement si `cleaned_data.csv` contient au moins 1 ligne.

---

## 3. Tableau de bord Streamlit déployé
L’application Streamlit permet :
- Des filtres (prix, surface, villes).
- Une carte pydeck avec points et labels k€.
- Un tableau interactif avec liens directs vers les annonces.

👉 **Lien URL** : https://pmnprojet-aqcouv52qt3k9bamgwkxgz.streamlit.app/

---

## 4. Rapport de projet (README.md)
### • Le problème abordé
Comparer les annonces en Île-de-France est chronophage. Ce projet centralise et standardise les infos clés pour une exploration rapide.

### • L’architecture du pipeline (Scrapy → Streamlit)
```
 ┌───────────────┐     ┌───────────────┐     ┌─────────────┐     ┌─────────────┐
 │ Pages HTML    │ --> │ Spider/Parser │ --> │ raw_data.json │ --> │ Cleaner     │
 └───────────────┘     └───────────────┘     └─────────────┘     └─────────────┘
                                                               │
                                                               v
                                                        cleaned_data.csv
                                                               │
                                                               v
                                                        ┌───────────────┐
                                                        │ Streamlit App │
                                                        └───────────────┘

CI/CD GitHub Actions : planification quotidienne + commit conditionnel
```

### • Comment lancer le projet en local
1. Créer un venv Python 3.11 et installer les dépendances : `pip install -r requirements.txt`.
2. Déposer des fichiers HTML dans `data/html/`.
3. Générer le brut : `python src/spider.py` ou `python src/parse_local_html.py`.
4. Nettoyer : `python src/cleaner.py` → produit `data/cleaned_data.csv`.
5. Lancer le dashboard : `streamlit run src/app.py`.

### • Défis techniques & solutions
- **Formats JSON hétérogènes** : fonction `load_raw` tolérante.
- **Nettoyage CP** : regex stricte sur 5 chiffres.
- **Coordonnées manquantes** : géocodage pgeocode.
- **Filtre ÎDF** : bbox (lat: 48.0–49.3, lon: 1.45–3.57).
- **Déduplication** : suppression doublons (url, title).
- **CI résiliente** : erreurs tolérées + commit conditionnel.

---

## 5. Dépendances (versions)
- beautifulsoup4==4.12.3  
- lxml==5.2.2  
- pandas==2.2.2  
- python-dotenv==1.0.1  
- requests==2.32.3  
- streamlit==1.37.1  
- pydeck==0.9.1  
- scrapy==2.11.2  
- pgeocode==0.5.0

---

## 6. Annexe — Workflow GitHub Actions
Résumé de `.github/workflows/main.yml` :
- Checkout
- Setup Python 3.11
- Install deps (requirements + scrapy)
- Run spider → `data/raw_data.json`
- Run cleaner → `data/cleaned_data.csv`
- Check CSV > 1 ligne
- Commit & push si OK

---

## Auteurs
Projet réalisé par :
- **Kaoutar Chraim**
- **Ouiddir Manel**

*Mastère 2 • Data Analyse (2024-2025)*
