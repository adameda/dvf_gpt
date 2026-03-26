"""
DVF Database Builder
====================
Downloads and processes official DVF data into a DuckDB analytical database.

Usage:
    python scripts/build_dvf_database.py [--years 2023 2024 2025] [--departments 75 69 13]

Data source: https://files.data.gouv.fr/geo-dvf/latest/csv/
"""

import os
import sys
import argparse
import requests
import tempfile
import duckdb
import pandas as pd
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_URL = "https://files.data.gouv.fr/geo-dvf/latest/csv"
YEARS = [2023, 2024, 2025]
DB_PATH = os.path.join(os.path.dirname(__file__), "../data/dvf.duckdb")

# Columns we need from raw DVF
NEEDED_COLUMNS = [
    "id_mutation", "date_mutation", "nature_mutation",
    "valeur_fonciere", "surface_reelle_bati", "nombre_pieces_principales",
    "type_local", "code_departement", "code_commune", "nom_commune",
    "latitude", "longitude",
]

# Business filters
VALID_NATURE = {"Vente"}
VALID_TYPES = {"Appartement", "Maison"}

# Outlier removal: keep [5th, 95th] percentile on prix_m2
QUANTILE_LOW = 0.05
QUANTILE_HIGH = 0.95


# ---------------------------------------------------------------------------
# Download helpers
# ---------------------------------------------------------------------------

def build_url(year: int, department: str) -> str:
    return f"{BASE_URL}/{year}/departements/{department}.csv.gz"


def download_file(url: str, dest: str) -> bool:
    """Download a file with progress, return True on success."""
    try:
        r = requests.get(url, stream=True, timeout=60)
        if r.status_code == 404:
            return False
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
        return True
    except Exception as e:
        print(f"  ⚠ Download error: {e}")
        return False


# ---------------------------------------------------------------------------
# Processing
# ---------------------------------------------------------------------------

def load_raw(filepath: str) -> pd.DataFrame:
    """Load raw DVF CSV, keep only needed columns."""
    try:
        df = pd.read_csv(
            filepath,
            compression="gzip",
            sep=",",
            low_memory=False,
            dtype={"code_departement": str, "code_commune": str},
        )
    except Exception:
        df = pd.read_csv(
            filepath,
            compression="gzip",
            sep="|",
            low_memory=False,
            dtype={"code_departement": str, "code_commune": str},
        )

    # Keep only available needed columns
    available = [c for c in NEEDED_COLUMNS if c in df.columns]
    return df[available].copy()


def aggregate_mutations(df: pd.DataFrame) -> pd.DataFrame:
    """
    DVF can have multiple rows per mutation (multi-local).
    Aggregate per id_mutation:
      - surface_reelle_bati → sum
      - valeur_fonciere    → first
      - latitude, longitude → first
      - others             → first
    """
    agg_rules = {
        "date_mutation": "first",
        "nature_mutation": "first",
        "valeur_fonciere": "first",
        "surface_reelle_bati": "sum",
        "nombre_pieces_principales": "sum",
        "type_local": "first",
        "code_departement": "first",
        "code_commune": "first",
        "nom_commune": "first",
        "latitude": "first",
        "longitude": "first",
    }
    # Only aggregate columns that exist
    agg_rules = {k: v for k, v in agg_rules.items() if k in df.columns}
    return df.groupby("id_mutation").agg(agg_rules).reset_index()


def clean_and_filter(df: pd.DataFrame) -> pd.DataFrame:
    """Apply business filters and enrich."""
    # Business filters
    df = df[df["nature_mutation"].isin(VALID_NATURE)]
    df = df[df["type_local"].isin(VALID_TYPES)]
    df = df[df["surface_reelle_bati"] > 0]
    df = df[df["valeur_fonciere"] > 0]
    df = df[df["latitude"].notna() & df["longitude"].notna()]

    # Enrichment
    df["prix_m2"] = df["valeur_fonciere"] / df["surface_reelle_bati"]
    df["date_mutation"] = pd.to_datetime(df["date_mutation"], errors="coerce")
    df["annee_mutation"] = df["date_mutation"].dt.year

    # Remove outliers per type_local
    clean_frames = []
    for type_local in VALID_TYPES:
        sub = df[df["type_local"] == type_local].copy()
        if sub.empty:
            continue
        q_low = sub["prix_m2"].quantile(QUANTILE_LOW)
        q_high = sub["prix_m2"].quantile(QUANTILE_HIGH)
        sub = sub[(sub["prix_m2"] >= q_low) & (sub["prix_m2"] <= q_high)]
        clean_frames.append(sub)

    return pd.concat(clean_frames, ignore_index=True) if clean_frames else df


def to_final_schema(df: pd.DataFrame) -> pd.DataFrame:
    """Select and cast final columns."""
    cols = {
        "id_mutation": str,
        "date_mutation": str,
        "valeur_fonciere": float,
        "surface_reelle_bati": float,
        "nombre_pieces_principales": "Int64",
        "code_departement": str,
        "code_commune": str,
        "nom_commune": str,
        "type_local": str,
        "latitude": float,
        "longitude": float,
        "prix_m2": float,
        "annee_mutation": "Int64",
    }

    # Keep only available
    available_cols = {k: v for k, v in cols.items() if k in df.columns}
    df = df[list(available_cols.keys())].copy()

    for col, dtype in available_cols.items():
        try:
            df[col] = df[col].astype(dtype)
        except Exception:
            pass

    return df


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Build DVF DuckDB database")
    parser.add_argument("--years", nargs="+", type=int, default=YEARS)
    parser.add_argument("--departments", nargs="+", default=None,
                        help="Department codes (e.g. 75 69 13). Default: all.")
    args = parser.parse_args()

    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

    # Build department list (01–95 + DOM-TOM)
    if args.departments:
        departments = [str(d).zfill(2) for d in args.departments]
    else:
        departments = [str(i).zfill(2) for i in range(1, 96)] + ["2A", "2B"]

    all_frames = []

    with tempfile.TemporaryDirectory() as tmpdir:
        for year in args.years:
            print(f"\n📅 Processing year {year}...")
            for dept in departments:
                url = build_url(year, dept)
                dest = os.path.join(tmpdir, f"{year}_{dept}.csv.gz")

                print(f"  ↓ Department {dept}...", end=" ", flush=True)
                ok = download_file(url, dest)
                if not ok:
                    print("not found, skipping.")
                    continue

                try:
                    df_raw = load_raw(dest)
                    df_agg = aggregate_mutations(df_raw)
                    df_clean = clean_and_filter(df_agg)
                    df_final = to_final_schema(df_clean)
                    all_frames.append(df_final)
                    print(f"✓ {len(df_final):,} transactions")
                except Exception as e:
                    print(f"error: {e}")

    if not all_frames:
        print("\n❌ No data collected. Check connectivity and department list.")
        sys.exit(1)

    print("\n🔧 Building DuckDB database...")
    full_df = pd.concat(all_frames, ignore_index=True)
    print(f"  Total rows before dedup: {len(full_df):,}")
    full_df = full_df.drop_duplicates(subset=["id_mutation"])
    print(f"  Total rows after dedup:  {len(full_df):,}")

    # Write to DuckDB
    con = duckdb.connect(DB_PATH)
    con.execute("DROP TABLE IF EXISTS transactions_clean")
    con.execute("""
        CREATE TABLE transactions_clean AS
        SELECT * FROM full_df
    """)

    # Create indexes for query performance
    con.execute("CREATE INDEX IF NOT EXISTS idx_commune ON transactions_clean (nom_commune)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_dept ON transactions_clean (code_departement)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_annee ON transactions_clean (annee_mutation)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_type ON transactions_clean (type_local)")

    row_count = con.execute("SELECT COUNT(*) FROM transactions_clean").fetchone()[0]
    con.close()

    print(f"\n✅ Database built: {DB_PATH}")
    print(f"   {row_count:,} transactions in transactions_clean")
    print("\nSample data:")

    con_ro = duckdb.connect(DB_PATH, read_only=True)
    sample = con_ro.execute("""
        SELECT nom_commune, type_local,
               ROUND(MEDIAN(prix_m2), 0) AS prix_median_m2,
               COUNT(*) AS nb
        FROM transactions_clean
        GROUP BY nom_commune, type_local
        ORDER BY nb DESC
        LIMIT 10
    """).fetchdf()
    con_ro.close()
    print(sample.to_string(index=False))


if __name__ == "__main__":
    main()
