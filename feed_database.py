# feed_database.py
"""
SQLite-backed nutrient composition layer for BalancedBora.

The database (Balance_Bora_Feed.db) is the AUTHORITATIVE source for analysed
composition: CP, ME, Ca, P, DM, NDF, ADF, ADL, OM, IVDMD, minerals.
FEEDS_DB remains the source for formulation metadata: cost_kg, min_incl,
max_incl, category, notes, and nutrients not yet analysed (lysine,
methionine, fat, ash).

UNIT HANDLING (verified against sample data):
  - DM, CP, NDF, ADF, ADL, OM, IVDMD : already in %     -> use as-is
  - ME, NEm, NEg, NEl                : MJ/kg            -> divide by 4.184
  - Ca, P, Na, K, Mg                 : g/kg (= ‰)       -> divide by 10
  - Fe, Cu, Mn, Zn                   : mg/kg            -> divide by 10000
"""

import os
import sqlite3
from pathlib import Path

BALANCE_BORA_DB_PATH = os.getenv(
    "BALANCE_BORA_DB_PATH",
    str(Path(__file__).with_name("Balance_Bora_Feed.db"))
)

DB_COLUMNS = {
    "n":    "_n",
    "DM":   "dm",
    "CP":   "cp",
    "NDF":  "ndf",
    "ADF":  "adf",
    "ADL":  "adl",
    "OM":   "om",
    "IVDMD": "ivdmd",
    "ME":   "me",
    "NEm":  "nem",
    "NEg":  "neg",
    "NEl":  "nel",
    "Ca":   "ca",
    "P":    "p",
    "Na":   "na",
    "K":    "k",
    "Mg":   "mg",
    "Fe":   "fe",
    "Cu":   "cu",
    "Mn":   "mn",
    "Zn":   "zn",
}

UNIT_FACTORS = {
    "me":  1.0 / 4.184,   # MJ/kg  -> Mcal/kg
    "nem": 1.0 / 4.184,
    "neg": 1.0 / 4.184,
    "nel": 1.0 / 4.184,
    "ca":  1.0 / 10.0,    # g/kg   -> %
    "p":   1.0 / 10.0,
    "na":  1.0 / 10.0,
    "k":   1.0 / 10.0,
    "mg":  1.0 / 10.0,
    "fe":  1.0 / 10000.0, # mg/kg  -> %
    "cu":  1.0 / 10000.0,
    "mn":  1.0 / 10000.0,
    "zn":  1.0 / 10000.0,
}

# Exact string match: SQLite ingredient_name -> FEEDS_DB key.
# The DB name "Maize" must not be matched by "Maize husk", so exact only.
SQLITE_TO_FEEDS_DB = {
    "Maize":            "maize_grain",
    "Wheat bran":       "wheat_bran",
    "Rice bran":        "rice_bran",
    "Sorghum":          "sorghum",
    "Soybean meal":     "soybean_meal",
    "Sunflower Cake":   "sunflower_cake",
    "cotton seed cake": "cottonseed_cake",
    "Fish meal":        "fish_meal",
}


def _convert(value, key):
    if value is None:
        return None
    factor = UNIT_FACTORS.get(key, 1.0)
    return float(value) * factor


def load_ingredient_database(path: str = BALANCE_BORA_DB_PATH) -> dict:
    if not Path(path).exists():
        print(f"[DB] Not found at {path} — using hardcoded FEEDS_DB values only.")
        return {}

    try:
        con = sqlite3.connect(path)
        con.row_factory = sqlite3.Row
        cur = con.execute("""
            SELECT ingredient_name, n,
                   DM, ADF, NDF, ADL, CP, OM,
                   P, Ca, Na, Fe, K, Mg, Cu, Mn, Zn,
                   IVDMD, ME, NEm, NEg, NEl
            FROM ingredients
        """)
        rows = cur.fetchall()
        con.close()
    except Exception as e:
        print(f"[DB ERROR] {e} — using hardcoded FEEDS_DB values only.")
        return {}

    db = {}
    matched = 0
    for row in rows:
        raw_name = str(row["ingredient_name"])
        feeds_key = SQLITE_TO_FEEDS_DB.get(raw_name)
        if not feeds_key:
            continue
        matched += 1

        record = {}
        for db_col, internal_key in DB_COLUMNS.items():
            val = row[db_col]
            if val is None:
                continue
            if internal_key == "_n":
                record["_n"] = int(val)
            else:
                record[internal_key] = _convert(val, internal_key)
        db[feeds_key] = record

    print(f"[DB] Loaded composition for {matched}/{len(rows)} ingredients from {path}")
    return db


INGREDIENT_DB = load_ingredient_database()


def merge_composition(feeds_db: dict, ingredient_db: dict) -> dict:
    merged = {}
    for fid, meta in feeds_db.items():
        entry = dict(meta)
        db_record = ingredient_db.get(fid)
        if db_record:
            for key, val in db_record.items():
                entry[key] = val
            entry["_source"] = "sqlite"
        else:
            entry["_source"] = "hardcoded"
        merged[fid] = entry
    return merged