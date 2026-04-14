"""
setup_db.py  —  Run once to create and populate butterfly.db
Usage: python setup_db.py
"""
import sqlite3
import pandas as pd
import os
DB_PATH = os.path.join(os.path.dirname(__file__), "butterfly.db")
CSV_PATH = os.path.join(os.path.dirname(__file__), "data", "species.csv")

RED_LIST_DESC = {
    "LC":      "Least Concern",
    "NT":      "Near Threatened",
    "VU":      "Vulnerable",
    "EN":      "Endangered",
    "CR":      "Critically Endangered",
    "CR (PE)": "Critically Endangered (Possibly Extinct)",
    "RE":      "Regionally Extinct",
    "EX":      "Extinct",
    "DD":      "Data Deficient",
    "NE":      "Not Evaluated",
}

def create_schema(conn):
    cur = conn.cursor()
    cur.executescript("""
        PRAGMA foreign_keys = ON;

        CREATE TABLE IF NOT EXISTS families (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT    NOT NULL UNIQUE
        );

        CREATE TABLE IF NOT EXISTS conservation_status (
            code        TEXT    PRIMARY KEY,
            description TEXT    NOT NULL,
            severity    INTEGER NOT NULL   -- 1=least concern … 9=extinct
        );

        CREATE TABLE IF NOT EXISTS species (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            scientific_name     TEXT    NOT NULL UNIQUE,
            common_name         TEXT,
            family_id           INTEGER NOT NULL REFERENCES families(id),
            status_code         TEXT    NOT NULL REFERENCES conservation_status(code),
            span_min_mm         REAL,
            span_max_mm         REAL,
            dry_mass_mg         REAL,
            months_to_adult     INTEGER
        );

        CREATE INDEX IF NOT EXISTS idx_species_family  ON species(family_id);
        CREATE INDEX IF NOT EXISTS idx_species_status  ON species(status_code);
        CREATE INDEX IF NOT EXISTS idx_species_name    ON species(scientific_name);
    """)
    conn.commit()
    print("Schema created.")

def seed_data(conn):
    cur = conn.cursor()

    # --- conservation_status ---
    severity = {
        "LC": 1, "NT": 2, "NE": 3, "DD": 4,
        "VU": 5, "EN": 6, "CR": 7, "CR (PE)": 8, "RE": 9,
    }
    for code, desc in RED_LIST_DESC.items():
        cur.execute(
            "INSERT OR IGNORE INTO conservation_status(code, description, severity) VALUES(?,?,?)",
            (code, desc, severity.get(code, 5))
        )

    df = pd.read_csv(CSV_PATH)
    df.columns = [c.strip() for c in df.columns]

    # --- families ---
    families = df["family"].dropna().unique()
    for fam in sorted(families):
        cur.execute("INSERT OR IGNORE INTO families(name) VALUES(?)", (fam,))

    fam_map = {row[1]: row[0] for row in cur.execute("SELECT id, name FROM families")}

    # --- species ---
    for _, row in df.iterrows():
        sci  = str(row["scientific_name"]).strip()
        com  = str(row.get("common_name", "")).strip() or None
        fam  = str(row["family"]).strip()
        stat = str(row["combined_red_list"]).strip()
        smin = float(row["combined_span_min"])  if pd.notna(row["combined_span_min"])  else None
        smax = float(row["combined_span_max"])  if pd.notna(row["combined_span_max"])  else None
        mass = float(row["estimated_dry_mass"]) if pd.notna(row["estimated_dry_mass"]) else None
        dev  = int(row["months_to_adult"])       if pd.notna(row["months_to_adult"])   else None

        # Ensure unknown statuses exist
        if stat not in RED_LIST_DESC:
            cur.execute(
                "INSERT OR IGNORE INTO conservation_status(code, description, severity) VALUES(?,?,?)",
                (stat, stat, 5)
            )

        cur.execute("""
            INSERT OR IGNORE INTO species
                (scientific_name, common_name, family_id, status_code,
                 span_min_mm, span_max_mm, dry_mass_mg, months_to_adult)
            VALUES (?,?,?,?,?,?,?,?)
        """, (sci, com, fam_map[fam], stat, smin, smax, mass, dev))

    conn.commit()
    print(f"Seeded {cur.execute('SELECT COUNT(*) FROM species').fetchone()[0]} species.")

if __name__ == "__main__":
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print("Old DB removed.")
    conn = sqlite3.connect(DB_PATH)
    create_schema(conn)
    seed_data(conn)
    conn.close()
    print("butterfly.db ready ✓")
