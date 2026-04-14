"""
app.py  —  Butterfly Encyclopedia  (Flask backend)
Run:  python app.py   →   http://127.0.0.1:5000
"""
import sqlite3, os, math
from flask import (Flask, render_template, request, jsonify,
                   g, abort, redirect, url_for, flash)

app = Flask(__name__)
app.secret_key = "lepidoptera-dbms-2024"
app.jinja_env.globals['enumerate'] = enumerate
DB_PATH = os.path.join(os.path.dirname(__file__), "butterfly.db")

# ── DB helpers ────────────────────────────────────────────────────────────────

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db

@app.teardown_appcontext
def close_db(exc=None):
    db = g.pop("db", None)
    if db:
        db.close()

def _families():
    return get_db().execute("SELECT id, name FROM families ORDER BY name").fetchall()

def _statuses():
    return get_db().execute(
        "SELECT code, description FROM conservation_status ORDER BY severity"
    ).fetchall()

# ── Home ──────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    db = get_db()
    total      = db.execute("SELECT COUNT(*) FROM species").fetchone()[0]
    families   = db.execute("SELECT COUNT(*) FROM families").fetchone()[0]
    threatened = db.execute(
        "SELECT COUNT(*) FROM species WHERE status_code IN ('VU','EN','CR','CR (PE)','RE')"
    ).fetchone()[0]
    featured = db.execute("""
        SELECT s.id, s.scientific_name, s.common_name,
               f.name AS family, s.status_code, cs.description AS status_desc,
               s.span_min_mm, s.span_max_mm, s.dry_mass_mg, s.months_to_adult
        FROM   species s
        JOIN   families f  ON f.id = s.family_id
        JOIN   conservation_status cs ON cs.code = s.status_code
        ORDER  BY RANDOM() LIMIT 6
    """).fetchall()
    return render_template("index.html",
        total=total, families=families, threatened=threatened, featured=featured)

# ── Browse ────────────────────────────────────────────────────────────────────

@app.route("/browse")
def browse():
    db = get_db()
    q        = request.args.get("q", "").strip()
    family   = request.args.get("family", "")
    status   = request.args.get("status", "")
    sort     = request.args.get("sort", "name")
    page     = max(1, int(request.args.get("page", 1)))
    per_page = 24
    span_min = request.args.get("span_min", type=float)
    span_max = request.args.get("span_max", type=float)
    mass_min = request.args.get("mass_min", type=float)
    mass_max = request.args.get("mass_max", type=float)

    where, params = ["1=1"], []
    if q:
        where.append("(s.scientific_name LIKE ? OR s.common_name LIKE ?)")
        params += [f"%{q}%", f"%{q}%"]
    if family:
        where.append("f.name = ?");  params.append(family)
    if status:
        where.append("s.status_code = ?");  params.append(status)
    if span_min is not None:
        where.append("s.span_min_mm >= ?"); params.append(span_min)
    if span_max is not None:
        where.append("s.span_max_mm <= ?"); params.append(span_max)
    if mass_min is not None:
        where.append("s.dry_mass_mg >= ?"); params.append(mass_min)
    if mass_max is not None:
        where.append("s.dry_mass_mg <= ?"); params.append(mass_max)

    order_map = {
        "name": "s.common_name COLLATE NOCASE",
        "sci":  "s.scientific_name COLLATE NOCASE",
        "span": "s.span_max_mm DESC",
        "mass": "s.dry_mass_mg DESC",
        "dev":  "s.months_to_adult DESC",
    }
    order_clause = order_map.get(sort, "s.common_name COLLATE NOCASE")
    base_sql = f"""
        FROM species s
        JOIN families f ON f.id = s.family_id
        JOIN conservation_status cs ON cs.code = s.status_code
        WHERE {' AND '.join(where)}
    """
    total_rows  = db.execute("SELECT COUNT(*) " + base_sql, params).fetchone()[0]
    total_pages = max(1, math.ceil(total_rows / per_page))
    page        = min(page, total_pages)
    offset      = (page - 1) * per_page

    rows = db.execute(
        "SELECT s.id, s.scientific_name, s.common_name, f.name AS family, "
        "s.status_code, cs.description AS status_desc, "
        "s.span_min_mm, s.span_max_mm, s.dry_mass_mg, s.months_to_adult "
        + base_sql + f" ORDER BY {order_clause} LIMIT ? OFFSET ?",
        params + [per_page, offset]
    ).fetchall()

    return render_template("browse.html",
        species=rows, total=total_rows, page=page, total_pages=total_pages,
        per_page=per_page, q=q, family=family, status=status, sort=sort,
        span_min=span_min, span_max=span_max, mass_min=mass_min, mass_max=mass_max,
        families=_families(), statuses=_statuses())

# ── Detail ────────────────────────────────────────────────────────────────────

@app.route("/species/<int:sid>")
def detail(sid):
    db = get_db()
    sp = db.execute("""
        SELECT s.*, f.name AS family, cs.description AS status_desc
        FROM   species s
        JOIN   families f  ON f.id = s.family_id
        JOIN   conservation_status cs ON cs.code = s.status_code
        WHERE  s.id = ?
    """, (sid,)).fetchone()
    if sp is None:
        abort(404)
    siblings = db.execute("""
        SELECT s.id, s.scientific_name, s.common_name, s.status_code
        FROM   species s JOIN families f ON f.id = s.family_id
        WHERE  f.name = ? AND s.id != ?
        ORDER  BY RANDOM() LIMIT 5
    """, (sp["family"], sid)).fetchall()
    fam_stats = db.execute("""
        SELECT COUNT(*) as cnt,
               AVG(span_max_mm) as avg_span, AVG(dry_mass_mg) as avg_mass
        FROM   species s JOIN families f ON f.id = s.family_id
        WHERE  f.name = ?
    """, (sp["family"],)).fetchone()
    return render_template("detail.html", sp=sp, siblings=siblings, fam_stats=fam_stats)

# ── Stats ─────────────────────────────────────────────────────────────────────

@app.route("/stats")
def stats():
    db = get_db()
    by_family = db.execute("""
        SELECT f.name, COUNT(*) AS cnt
        FROM   species s JOIN families f ON f.id = s.family_id
        GROUP  BY f.name ORDER BY cnt DESC
    """).fetchall()
    by_status = db.execute("""
        SELECT cs.code, cs.description, COUNT(*) AS cnt
        FROM   species s JOIN conservation_status cs ON cs.code = s.status_code
        GROUP  BY cs.code ORDER BY cs.severity
    """).fetchall()
    span_dist = db.execute("""
        SELECT CASE
            WHEN span_max_mm < 20 THEN '< 20 mm'
            WHEN span_max_mm < 40 THEN '20–40 mm'
            WHEN span_max_mm < 60 THEN '40–60 mm'
            WHEN span_max_mm < 80 THEN '60–80 mm'
            ELSE '≥ 80 mm'
          END AS bucket, COUNT(*) AS cnt
        FROM species WHERE span_max_mm IS NOT NULL
        GROUP BY bucket ORDER BY MIN(span_max_mm)
    """).fetchall()
    mass_dist = db.execute("""
        SELECT CASE
            WHEN dry_mass_mg < 50  THEN '< 50 mg'
            WHEN dry_mass_mg < 200 THEN '50–200 mg'
            WHEN dry_mass_mg < 500 THEN '200–500 mg'
            ELSE '≥ 500 mg'
          END AS bucket, COUNT(*) AS cnt
        FROM species WHERE dry_mass_mg IS NOT NULL
        GROUP BY bucket ORDER BY MIN(dry_mass_mg)
    """).fetchall()
    dev_dist = db.execute("""
        SELECT months_to_adult AS months, COUNT(*) AS cnt
        FROM   species WHERE months_to_adult IS NOT NULL
        GROUP  BY months_to_adult ORDER BY months_to_adult
    """).fetchall()
    top_large = db.execute("""
        SELECT s.scientific_name, s.common_name, f.name AS family,
               s.span_max_mm, s.status_code
        FROM   species s JOIN families f ON f.id = s.family_id
        WHERE  s.span_max_mm IS NOT NULL
        ORDER  BY s.span_max_mm DESC LIMIT 10
    """).fetchall()
    top_small = db.execute("""
        SELECT s.scientific_name, s.common_name, f.name AS family,
               s.span_min_mm, s.status_code
        FROM   species s JOIN families f ON f.id = s.family_id
        WHERE  s.span_min_mm IS NOT NULL
        ORDER  BY s.span_min_mm ASC LIMIT 10
    """).fetchall()
    return render_template("stats.html",
        by_family=by_family, by_status=by_status,
        span_dist=span_dist, mass_dist=mass_dist, dev_dist=dev_dist,
        top_large=top_large, top_small=top_small)

# ── Compare ───────────────────────────────────────────────────────────────────

@app.route("/compare")
def compare():
    db  = get_db()
    id1 = request.args.get("a", type=int)
    id2 = request.args.get("b", type=int)
    sp1 = sp2 = None
    if id1:
        sp1 = db.execute("""
            SELECT s.*, f.name AS family, cs.description AS status_desc
            FROM species s JOIN families f ON f.id=s.family_id
            JOIN conservation_status cs ON cs.code=s.status_code WHERE s.id=?
        """, (id1,)).fetchone()
    if id2:
        sp2 = db.execute("""
            SELECT s.*, f.name AS family, cs.description AS status_desc
            FROM species s JOIN families f ON f.id=s.family_id
            JOIN conservation_status cs ON cs.code=s.status_code WHERE s.id=?
        """, (id2,)).fetchone()
    all_species = db.execute(
        "SELECT id, common_name, scientific_name FROM species ORDER BY common_name COLLATE NOCASE"
    ).fetchall()
    return render_template("compare.html", sp1=sp1, sp2=sp2, all_species=all_species)

# ── SQL Showcase ──────────────────────────────────────────────────────────────

SHOWCASE_QUERIES = [
    {
        "id": 1,
        "title": "Widest Wingspan Range",
        "description": "Species with the greatest spread between min and max wingspan — sorted by range descending.",
        "concept": "Arithmetic expression in SELECT, ORDER BY computed column",
        "sql": """SELECT scientific_name, common_name,
       span_min_mm, span_max_mm,
       (span_max_mm - span_min_mm) AS range_mm
FROM   species
WHERE  span_min_mm IS NOT NULL AND span_max_mm IS NOT NULL
ORDER  BY range_mm DESC
LIMIT  10;""",
    },
    {
        "id": 2,
        "title": "Family Averages (JOIN + GROUP BY)",
        "description": "Average wingspan and dry mass per family, ordered by average wingspan.",
        "concept": "INNER JOIN · GROUP BY · AVG aggregate · ORDER BY aggregate",
        "sql": """SELECT f.name            AS family,
       COUNT(*)           AS species_count,
       ROUND(AVG(s.span_max_mm), 1) AS avg_wingspan_mm,
       ROUND(AVG(s.dry_mass_mg), 1) AS avg_mass_mg
FROM   species  s
JOIN   families f ON f.id = s.family_id
GROUP  BY f.name
ORDER  BY avg_wingspan_mm DESC;""",
    },
    {
        "id": 3,
        "title": "Most Threatened Family",
        "description": "Which families have the highest proportion of threatened species?",
        "concept": "CASE WHEN inside AVG (boolean trick) · percentage calculation",
        "sql": """SELECT f.name AS family,
       COUNT(*) AS total,
       SUM(CASE WHEN s.status_code IN ('VU','EN','CR','CR (PE)','RE') THEN 1 ELSE 0 END)
           AS threatened_count,
       ROUND(
         100.0 * SUM(CASE WHEN s.status_code IN ('VU','EN','CR','CR (PE)','RE') THEN 1 ELSE 0 END)
               / COUNT(*), 1
       ) AS pct_threatened
FROM   species  s
JOIN   families f ON f.id = s.family_id
GROUP  BY f.name
ORDER  BY pct_threatened DESC
LIMIT  10;""",
    },
    {
        "id": 4,
        "title": "Heavier Than Their Family Average (Subquery)",
        "description": "Species whose dry mass exceeds the average for their family.",
        "concept": "Correlated subquery in WHERE clause",
        "sql": """SELECT s.scientific_name, s.common_name,
       f.name           AS family,
       s.dry_mass_mg,
       ROUND((SELECT AVG(s2.dry_mass_mg)
              FROM   species s2
              WHERE  s2.family_id = s.family_id), 1) AS family_avg_mg
FROM   species  s
JOIN   families f ON f.id = s.family_id
WHERE  s.dry_mass_mg > (
    SELECT AVG(s2.dry_mass_mg)
    FROM   species s2
    WHERE  s2.family_id = s.family_id
)
ORDER  BY s.dry_mass_mg DESC
LIMIT  15;""",
    },
    {
        "id": 5,
        "title": "Conservation Status × Family Cross-Tab",
        "description": "How many species per family are LC, NT, or threatened?",
        "concept": "Conditional aggregation (pivot-style) with CASE WHEN + SUM",
        "sql": """SELECT f.name AS family,
       SUM(CASE WHEN s.status_code = 'LC'            THEN 1 ELSE 0 END) AS LC,
       SUM(CASE WHEN s.status_code = 'NT'            THEN 1 ELSE 0 END) AS NT,
       SUM(CASE WHEN s.status_code = 'VU'            THEN 1 ELSE 0 END) AS VU,
       SUM(CASE WHEN s.status_code = 'EN'            THEN 1 ELSE 0 END) AS EN,
       SUM(CASE WHEN s.status_code IN ('CR','CR (PE)') THEN 1 ELSE 0 END) AS CR,
       SUM(CASE WHEN s.status_code = 'RE'            THEN 1 ELSE 0 END) AS RE
FROM   species  s
JOIN   families f ON f.id = s.family_id
GROUP  BY f.name
ORDER  BY f.name;""",
    },
    {
        "id": 6,
        "title": "Rarest Families (< 5 Species)",
        "description": "Families with very few species in the dataset.",
        "concept": "GROUP BY + HAVING to filter aggregated groups",
        "sql": """SELECT f.name AS family, COUNT(*) AS species_count
FROM   species  s
JOIN   families f ON f.id = s.family_id
GROUP  BY f.name
HAVING COUNT(*) < 5
ORDER  BY species_count ASC;""",
    },
    {
        "id": 7,
        "title": "Wingspan Rank Within Family (Window Function)",
        "description": "Rank each species by wingspan within its own family using a window function.",
        "concept": "RANK() OVER (PARTITION BY … ORDER BY …)",
        "sql": """SELECT scientific_name, common_name,
       f.name AS family,
       span_max_mm,
       RANK() OVER (
           PARTITION BY s.family_id
           ORDER BY span_max_mm DESC
       ) AS rank_in_family
FROM   species s
JOIN   families f ON f.id = s.family_id
WHERE  span_max_mm IS NOT NULL
ORDER  BY family, rank_in_family
LIMIT  20;""",
    },
    {
        "id": 8,
        "title": "Cumulative Species Count (Running Total)",
        "description": "Running total of species as we add each family, sorted by family size.",
        "concept": "SUM() OVER (ORDER BY …) — cumulative window function",
        "sql": """WITH family_counts AS (
    SELECT f.name AS family, COUNT(*) AS cnt
    FROM   species s JOIN families f ON f.id = s.family_id
    GROUP  BY f.name
)
SELECT family, cnt AS species_in_family,
       SUM(cnt) OVER (ORDER BY cnt DESC
                      ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
           AS running_total
FROM   family_counts
ORDER  BY cnt DESC;""",
    },
    {
        "id": 9,
        "title": "Development Time vs. Size (CTE)",
        "description": "Average wingspan grouped by development time — do larger moths take longer to mature?",
        "concept": "Common Table Expression (WITH) + GROUP BY + ROUND",
        "sql": """WITH dev_size AS (
    SELECT months_to_adult,
           span_max_mm,
           dry_mass_mg
    FROM   species
    WHERE  months_to_adult IS NOT NULL
      AND  span_max_mm     IS NOT NULL
)
SELECT months_to_adult,
       COUNT(*)                        AS species_count,
       ROUND(AVG(span_max_mm), 1)      AS avg_wingspan_mm,
       ROUND(AVG(dry_mass_mg), 1)      AS avg_mass_mg
FROM   dev_size
GROUP  BY months_to_adult
ORDER  BY months_to_adult;""",
    },
    {
        "id": 10,
        "title": "Three-Table JOIN — Full Profile",
        "description": "One query pulling together species, family name, and full status description.",
        "concept": "Multi-table JOIN · SELECT column aliasing · ORDER BY multiple columns",
        "sql": """SELECT s.scientific_name,
       s.common_name,
       f.name              AS family,
       cs.code             AS status_code,
       cs.description      AS status_full,
       cs.severity         AS threat_level,
       s.span_max_mm       AS wingspan_mm,
       s.dry_mass_mg       AS mass_mg,
       s.months_to_adult   AS dev_months
FROM   species             s
JOIN   families            f  ON f.id      = s.family_id
JOIN   conservation_status cs ON cs.code   = s.status_code
ORDER  BY cs.severity DESC, s.span_max_mm DESC
LIMIT  15;""",
    },
]

@app.route("/queries")
def queries():
    db = get_db()
    active = request.args.get("q", type=int, default=1)
    query  = next((q for q in SHOWCASE_QUERIES if q["id"] == active), SHOWCASE_QUERIES[0])
    try:
        cur  = db.execute(query["sql"])
        cols = [d[0] for d in cur.description]
        rows = [dict(zip(cols, row)) for row in cur.fetchall()]
        error = None
    except Exception as e:
        cols, rows, error = [], [], str(e)
    return render_template("queries.html",
        queries=SHOWCASE_QUERIES, active=query,
        cols=cols, rows=rows, error=error)

# ── Admin CRUD ────────────────────────────────────────────────────────────────

@app.route("/admin")
def admin():
    db   = get_db()
    page = max(1, int(request.args.get("page", 1)))
    q    = request.args.get("q", "").strip()
    per  = 20
    where = "1=1"
    params = []
    if q:
        where = "(s.scientific_name LIKE ? OR s.common_name LIKE ?)"
        params = [f"%{q}%", f"%{q}%"]
    total = db.execute(f"SELECT COUNT(*) FROM species s WHERE {where}", params).fetchone()[0]
    total_pages = max(1, math.ceil(total / per))
    page  = min(page, total_pages)
    rows  = db.execute(
        f"SELECT s.id, s.scientific_name, s.common_name, f.name AS family, "
        f"s.status_code, s.span_max_mm, s.dry_mass_mg, s.months_to_adult "
        f"FROM species s JOIN families f ON f.id=s.family_id WHERE {where} "
        f"ORDER BY s.id DESC LIMIT ? OFFSET ?",
        params + [per, (page-1)*per]
    ).fetchall()
    return render_template("admin.html",
        species=rows, total=total, page=page, total_pages=total_pages, q=q,
        families=_families(), statuses=_statuses())

@app.route("/admin/new", methods=["GET", "POST"])
def admin_new():
    if request.method == "POST":
        return _save_species(None)
    return render_template("admin_form.html",
        sp=None, families=_families(), statuses=_statuses(), mode="new")

@app.route("/admin/edit/<int:sid>", methods=["GET", "POST"])
def admin_edit(sid):
    db = get_db()
    sp = db.execute("SELECT * FROM species WHERE id=?", (sid,)).fetchone()
    if sp is None:
        abort(404)
    if request.method == "POST":
        return _save_species(sid)
    return render_template("admin_form.html",
        sp=sp, families=_families(), statuses=_statuses(), mode="edit")

@app.route("/admin/delete/<int:sid>", methods=["POST"])
def admin_delete(sid):
    db = get_db()
    row = db.execute("SELECT scientific_name FROM species WHERE id=?", (sid,)).fetchone()
    if row is None:
        abort(404)
    db.execute("DELETE FROM species WHERE id=?", (sid,))
    db.commit()
    flash(f"Deleted: {row['scientific_name']}", "success")
    return redirect(url_for("admin"))

def _save_species(sid):
    """Shared logic for INSERT and UPDATE."""
    db  = get_db()
    f   = request.form
    errors = []

    sci   = f.get("scientific_name", "").strip()
    com   = f.get("common_name", "").strip() or None
    fam   = f.get("family_id", "")
    stat  = f.get("status_code", "")

    if not sci:   errors.append("Scientific name is required.")
    if not fam:   errors.append("Family is required.")
    if not stat:  errors.append("Conservation status is required.")

    def _float(k):
        v = f.get(k, "").strip()
        try: return float(v) if v else None
        except ValueError: errors.append(f"{k} must be a number."); return None

    def _int(k):
        v = f.get(k, "").strip()
        try: return int(v) if v else None
        except ValueError: errors.append(f"{k} must be an integer."); return None

    smin = _float("span_min_mm")
    smax = _float("span_max_mm")
    mass = _float("dry_mass_mg")
    dev  = _int("months_to_adult")

    if errors:
        for e in errors:
            flash(e, "error")
        return render_template("admin_form.html",
            sp=dict(f), families=_families(), statuses=_statuses(),
            mode="edit" if sid else "new")

    if sid:
        db.execute("""
            UPDATE species SET scientific_name=?, common_name=?, family_id=?,
            status_code=?, span_min_mm=?, span_max_mm=?, dry_mass_mg=?, months_to_adult=?
            WHERE id=?
        """, (sci, com, fam, stat, smin, smax, mass, dev, sid))
        db.commit()
        flash(f"Updated: {sci}", "success")
        return redirect(url_for("admin"))
    else:
        # Check duplicate
        if db.execute("SELECT 1 FROM species WHERE scientific_name=?", (sci,)).fetchone():
            flash(f"'{sci}' already exists in the database.", "error")
            return render_template("admin_form.html",
                sp=dict(f), families=_families(), statuses=_statuses(), mode="new")
        db.execute("""
            INSERT INTO species (scientific_name, common_name, family_id, status_code,
                                 span_min_mm, span_max_mm, dry_mass_mg, months_to_adult)
            VALUES (?,?,?,?,?,?,?,?)
        """, (sci, com, fam, stat, smin, smax, mass, dev))
        db.commit()
        flash(f"Added: {sci}", "success")
        return redirect(url_for("admin"))

# ── JSON search ───────────────────────────────────────────────────────────────

@app.route("/api/search")
def api_search():
    q = request.args.get("q", "").strip()
    if len(q) < 2:
        return jsonify([])
    rows = get_db().execute("""
        SELECT id, scientific_name, common_name, status_code
        FROM   species
        WHERE  scientific_name LIKE ? OR common_name LIKE ?
        LIMIT  10
    """, (f"%{q}%", f"%{q}%")).fetchall()
    return jsonify([dict(r) for r in rows])

@app.route("/api/family/<n>")
def api_family(n):
    rows = get_db().execute("""
        SELECT s.scientific_name, s.common_name, s.span_max_mm,
               s.dry_mass_mg, s.months_to_adult, s.status_code
        FROM   species s JOIN families f ON f.id = s.family_id
        WHERE  f.name = ? ORDER BY s.span_max_mm DESC
    """, (n,)).fetchall()
    return jsonify([dict(r) for r in rows])

# Wikipedia image

import requests as _req, time as _time

def _fetch_wiki_image(title):
    """Hit Wikipedia pageimages API for a given title."""
    try:
        r = _req.get(
            "https://en.wikipedia.org/w/api.php",
            params={"action":"query","format":"json","prop":"pageimages",
                    "titles":title,"pithumbsize":600},
            headers={"User-Agent":"LepidopteraEncyclopedia/1.0"},
            timeout=8
        )
        pages = r.json().get("query",{}).get("pages",{})
        for pid, page in pages.items():
            if pid != "-1" and "thumbnail" in page:
                return page["thumbnail"]["source"]
    except Exception:
        pass
    return None

def _get_wiki_image_recursive(name):
    """Strip trailing words until an image is found (buter2 logic)."""
    words = name.split()
    if not words:
        return None
    url = _fetch_wiki_image(" ".join(words))
    if url:
        return url
    if len(words) > 1:
        _time.sleep(0.15)
        return _get_wiki_image_recursive(" ".join(words[:-1]))
    return None

@app.route("/api/wiki_image/<int:sid>")
def api_wiki_image(sid):
    """
    Returns {"url": "..."} or {"url": null}.
    Checks DB cache first; fetches from Wikipedia on miss and stores result.
    """
    db = get_db()

    # Ensure cache column exists (safe no-op if already there)
    db.execute(
        "ALTER TABLE species ADD COLUMN wiki_image_url TEXT"
        if not _col_exists(db, "species", "wiki_image_url") else "SELECT 1"
    )

    row = db.execute(
        "SELECT wiki_image_url, scientific_name FROM species WHERE id=?", (sid,)
    ).fetchone()
    if row is None:
        return jsonify({"url": None}), 404

    # Cache hit — value already fetched before (even if it's the sentinel "NONE")
    if row["wiki_image_url"] is not None:
        url = None if row["wiki_image_url"] == "NONE" else row["wiki_image_url"]
        return jsonify({"url": url})

    # Cache miss — go fetch
    img_url = _get_wiki_image_recursive(row["scientific_name"])
    sentinel = img_url if img_url else "NONE"   # store "NONE" so we don't re-fetch
    db.execute("UPDATE species SET wiki_image_url=? WHERE id=?", (sentinel, sid))
    db.commit()
    return jsonify({"url": img_url})

def _col_exists(db, table, col):
    cols = [r["name"] for r in db.execute(f"PRAGMA table_info({table})").fetchall()]
    return col in cols

# ── Run ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if not os.path.exists(DB_PATH):
        print("butterfly.db not found — run setup_db.py first.")
    else:
        app.run(debug=True, port=5000)


# ── Family detail page ────────────────────────────────────────────────────────

@app.route("/family/<family_name>")
def family_detail(family_name):
    db = get_db()
    fam = db.execute("SELECT id, name FROM families WHERE name = ?", (family_name,)).fetchone()
    if fam is None:
        abort(404)

    stats = db.execute("""
        SELECT COUNT(*)                       AS total,
               ROUND(MIN(span_min_mm), 1)     AS min_span,
               ROUND(MAX(span_max_mm), 1)     AS max_span,
               ROUND(AVG(span_max_mm), 1)     AS avg_span,
               ROUND(MIN(dry_mass_mg), 1)     AS min_mass,
               ROUND(MAX(dry_mass_mg), 1)     AS max_mass,
               ROUND(AVG(dry_mass_mg), 1)     AS avg_mass,
               ROUND(AVG(months_to_adult), 1) AS avg_dev
        FROM   species WHERE family_id = ?
    """, (fam["id"],)).fetchone()

    status_breakdown = db.execute("""
        SELECT cs.code, cs.description, COUNT(*) AS cnt
        FROM   species s
        JOIN   conservation_status cs ON cs.code = s.status_code
        WHERE  s.family_id = ?
        GROUP  BY cs.code ORDER BY cs.severity
    """, (fam["id"],)).fetchall()

    species_list = db.execute("""
        SELECT s.id, s.scientific_name, s.common_name, s.status_code,
               s.span_min_mm, s.span_max_mm, s.dry_mass_mg, s.months_to_adult
        FROM   species s
        WHERE  s.family_id = ?
        ORDER  BY s.span_max_mm DESC NULLS LAST
    """, (fam["id"],)).fetchall()

    # top 5 largest / smallest for quick lists
    top5_large = species_list[:5]
    top5_small = sorted(
        [s for s in species_list if s["span_min_mm"]],
        key=lambda s: s["span_min_mm"]
    )[:5]

    return render_template("family.html",
        fam=fam, stats=stats,
        status_breakdown=status_breakdown,
        species_list=species_list,
        top5_large=top5_large,
        top5_small=top5_small)


# ── CSV export ────────────────────────────────────────────────────────────────

import csv, io
from flask import Response

@app.route("/export/csv")
def export_csv():
    db   = get_db()
    q      = request.args.get("q", "").strip()
    family = request.args.get("family", "")
    status = request.args.get("status", "")
    span_min = request.args.get("span_min", type=float)
    span_max = request.args.get("span_max", type=float)
    mass_min = request.args.get("mass_min", type=float)
    mass_max = request.args.get("mass_max", type=float)

    where, params = ["1=1"], []
    if q:
        where.append("(s.scientific_name LIKE ? OR s.common_name LIKE ?)")
        params += [f"%{q}%", f"%{q}%"]
    if family:
        where.append("f.name = ?");  params.append(family)
    if status:
        where.append("s.status_code = ?");  params.append(status)
    if span_min is not None:
        where.append("s.span_min_mm >= ?"); params.append(span_min)
    if span_max is not None:
        where.append("s.span_max_mm <= ?"); params.append(span_max)
    if mass_min is not None:
        where.append("s.dry_mass_mg >= ?"); params.append(mass_min)
    if mass_max is not None:
        where.append("s.dry_mass_mg <= ?"); params.append(mass_max)

    rows = db.execute(f"""
        SELECT s.scientific_name, s.common_name, f.name AS family,
               s.status_code, cs.description AS status_desc,
               s.span_min_mm, s.span_max_mm, s.dry_mass_mg, s.months_to_adult
        FROM   species s
        JOIN   families f  ON f.id = s.family_id
        JOIN   conservation_status cs ON cs.code = s.status_code
        WHERE  {' AND '.join(where)}
        ORDER  BY s.scientific_name
    """, params).fetchall()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["scientific_name","common_name","family","status_code",
                     "status_description","span_min_mm","span_max_mm",
                     "dry_mass_mg","months_to_adult"])
    for r in rows:
        writer.writerow(list(r))

    buf.seek(0)
    return Response(
        buf.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=lepidoptera_export.csv"}
    )


# ── Schema diagram page ───────────────────────────────────────────────────────

@app.route("/schema")
def schema():
    db = get_db()
    # Gather live table info from sqlite_master + PRAGMA
    tables = {}
    for tbl in ["families", "conservation_status", "species"]:
        cols = db.execute(f"PRAGMA table_info({tbl})").fetchall()
        fks  = db.execute(f"PRAGMA foreign_key_list({tbl})").fetchall()
        idx  = db.execute(f"PRAGMA index_list({tbl})").fetchall()
        tables[tbl] = {
            "columns": [dict(c) for c in cols],
            "foreign_keys": [dict(f) for f in fks],
            "indexes": [dict(i) for i in idx],
        }

    row_counts = {
        "families":            db.execute("SELECT COUNT(*) FROM families").fetchone()[0],
        "conservation_status": db.execute("SELECT COUNT(*) FROM conservation_status").fetchone()[0],
        "species":             db.execute("SELECT COUNT(*) FROM species").fetchone()[0],
    }
    return render_template("schema.html", tables=tables, row_counts=row_counts)


# ── Error handlers ────────────────────────────────────────────────────────────

@app.errorhandler(404)
def not_found(e):
    return render_template("404.html"), 404

@app.errorhandler(500)
def server_error(e):
    return render_template("500.html"), 500
