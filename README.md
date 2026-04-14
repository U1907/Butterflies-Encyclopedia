# 🦋 Lepidoptera Encyclopedia
### A DBMS Project — Butterfly & Moth Field Guide

A full-stack web encyclopedia built with **Flask + SQLite**, covering **968 species** across **21 families** with conservation data, morphology, and development time.

---

## Features

| Page | Description |
|------|-------------|
| **Home** | Hero, key stats, 6 random featured species |
| **Browse** | Paginated grid (24/page) with search, family filter, conservation status filter, and 5 sort options |
| **Species Detail** | Full data panel — wingspan bar, development timeline, family context, related species |
| **Statistics** | 5 interactive Chart.js charts + top-10 largest/smallest tables |
| **Live Search** | Instant autocomplete dropdown in the nav bar (JSON API) |

---

## Database Schema

```
families              conservation_status
─────────────────     ─────────────────────────
id   INTEGER PK       code        TEXT PK
name TEXT UNIQUE      description TEXT
                      severity    INTEGER

species
────────────────────────────────────────────
id               INTEGER PK AUTOINCREMENT
scientific_name  TEXT UNIQUE
common_name      TEXT
family_id        INTEGER → families(id)
status_code      TEXT    → conservation_status(code)
span_min_mm      REAL
span_max_mm      REAL
dry_mass_mg      REAL
months_to_adult  INTEGER
```

### Conservation Status Codes
| Code | Meaning |
|------|---------|
| LC | Least Concern |
| NT | Near Threatened |
| VU | Vulnerable |
| EN | Endangered |
| CR | Critically Endangered |
| CR (PE) | Critically Endangered (Possibly Extinct) |
| RE | Regionally Extinct |
| DD | Data Deficient |
| NE | Not Evaluated |

---

## Quick Start

### 1. Install dependencies
```bash
pip install flask pandas
```

### 2. Build the database (run once)
```bash
python setup_db.py
```
This creates `butterfly.db` from `data/species.csv`.

### 3. Start the server
```bash
python app.py
```
Open **http://127.0.0.1:5000** in your browser.

---

## Project Structure

```
butterfly_encyclopedia/
├── app.py               # Flask routes & API endpoints
├── setup_db.py          # One-time DB creation & seeding script
├── butterfly.db         # SQLite database (created by setup_db.py)
├── data/
│   └── species.csv      # Source dataset (968 species)
├── templates/
│   ├── base.html        # Shared layout, nav, footer
│   ├── index.html       # Home page
│   ├── browse.html      # Browse & filter page
│   ├── detail.html      # Individual species page
│   └── stats.html       # Charts & statistics page
├── static/
│   ├── style.css        # Dark botanical theme
│   └── script.js        # Live search autocomplete + scroll animations
└── README.md
```

---

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /` | Home page |
| `GET /browse?q=&family=&status=&sort=&page=` | Browse species |
| `GET /species/<id>` | Species detail page |
| `GET /stats` | Statistics & charts |
| `GET /api/search?q=<query>` | JSON autocomplete (min 2 chars) |
| `GET /api/family/<name>` | JSON species list for a family |

---

## Tech Stack

- **Backend**: Python 3 · Flask · SQLite (via `sqlite3`)
- **Frontend**: Jinja2 templates · Vanilla JS · Chart.js 4
- **Fonts**: Cinzel (display) · Cormorant Garamond (body) · DM Mono (data)
- **Data**: Combined Red List + ecological traits dataset (968 Lepidoptera)
