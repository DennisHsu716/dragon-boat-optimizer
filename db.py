from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

import pandas as pd

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "app.db"
LEGACY_CSV_PATH = DATA_DIR / "best_scores.csv"

PBKDF2_ITERATIONS = 200_000

SCORE_COLUMNS = ["date", "name", "gender", "weight", "side_pref", "time_trial", "distance_1min", "adj"]


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


@contextmanager
def get_conn():
    conn = _connect()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS teams (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                team_name TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS scores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                team_id INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
                date TEXT DEFAULT '',
                name TEXT NOT NULL,
                gender TEXT,
                weight REAL,
                side_pref TEXT NOT NULL,
                time_trial REAL,
                distance_1min REAL,
                adj REAL NOT NULL,
                UNIQUE(team_id, name, side_pref)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS team_settings (
                team_id INTEGER PRIMARY KEY REFERENCES teams(id) ON DELETE CASCADE,
                formula_mode TEXT DEFAULT 'default',
                custom_test_type TEXT DEFAULT 'time',
                race_distance_m REAL DEFAULT 0,
                custom_formula TEXT DEFAULT '',
                lineup_config_json TEXT DEFAULT '{}'
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS issues (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                team_id INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
                issue_type TEXT,
                title TEXT,
                description TEXT,
                status TEXT DEFAULT 'open',
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)


# -----------------------------
# Auth
# -----------------------------
def _hash_password(password: str, salt: bytes) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS).hex()


def register_team(team_name: str, password: str) -> int:
    team_name = team_name.strip()
    if not team_name:
        raise ValueError("Team name is required.")
    if not password or len(password) < 4:
        raise ValueError("Password must be at least 4 characters.")

    salt = secrets.token_bytes(16)
    pw_hash = _hash_password(password, salt)

    with get_conn() as conn:
        try:
            cur = conn.execute(
                "INSERT INTO teams (team_name, password_hash, salt) VALUES (?, ?, ?)",
                (team_name, pw_hash, salt.hex()),
            )
        except sqlite3.IntegrityError:
            raise ValueError("Team name already exists. Please choose another one.")
        team_id = cur.lastrowid
        conn.execute("INSERT INTO team_settings (team_id) VALUES (?)", (team_id,))

    return team_id


def login_team(team_name: str, password: str) -> Optional[int]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id, password_hash, salt FROM teams WHERE team_name = ?",
            (team_name.strip(),),
        ).fetchone()

    if row is None:
        return None

    salt = bytes.fromhex(row["salt"])
    expected = _hash_password(password, salt)
    if hmac.compare_digest(expected, row["password_hash"]):
        return row["id"]
    return None


def team_exists(team_name: str) -> bool:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT 1 FROM teams WHERE team_name = ?",
            (team_name.strip(),),
        ).fetchone()
    return row is not None


def any_team_exists() -> bool:
    with get_conn() as conn:
        row = conn.execute("SELECT 1 FROM teams LIMIT 1").fetchone()
    return row is not None


# -----------------------------
# Scores (per-team "personal best" table)
# -----------------------------
def load_best_scores(team_id: int) -> pd.DataFrame:
    with get_conn() as conn:
        rows = conn.execute(
            f"SELECT {', '.join(SCORE_COLUMNS)} FROM scores WHERE team_id = ?",
            (team_id,),
        ).fetchall()
    return pd.DataFrame([dict(r) for r in rows], columns=SCORE_COLUMNS)


def upsert_scores(team_id: int, df: pd.DataFrame, lower_is_better: bool) -> pd.DataFrame:
    """
    Keep the best record per (team_id, name, side_pref).
    lower_is_better=True for time-based tests (smaller adj wins),
    False for distance-based tests (larger adj wins).
    """
    df = df.copy()
    df.columns = [str(c).strip().lower() for c in df.columns]

    required = {"name", "gender", "weight", "side_pref", "adj"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    for col in ["date", "time_trial", "distance_1min"]:
        if col not in df.columns:
            df[col] = None

    df["adj"] = pd.to_numeric(df["adj"], errors="coerce")
    df = df.dropna(subset=["name", "side_pref", "adj"])

    with get_conn() as conn:
        for _, row in df.iterrows():
            name = str(row["name"]).strip()
            side_pref = str(row["side_pref"]).strip().lower()
            new_adj = float(row["adj"])

            existing = conn.execute(
                "SELECT adj FROM scores WHERE team_id=? AND name=? AND side_pref=?",
                (team_id, name, side_pref),
            ).fetchone()

            should_write = True
            if existing is not None:
                old_adj = existing["adj"]
                should_write = (new_adj < old_adj) if lower_is_better else (new_adj > old_adj)

            if not should_write:
                continue

            weight = row.get("weight")
            time_trial = row.get("time_trial")
            distance_1min = row.get("distance_1min")

            conn.execute("""
                INSERT INTO scores (team_id, date, name, gender, weight, side_pref, time_trial, distance_1min, adj)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(team_id, name, side_pref) DO UPDATE SET
                    date=excluded.date,
                    gender=excluded.gender,
                    weight=excluded.weight,
                    time_trial=excluded.time_trial,
                    distance_1min=excluded.distance_1min,
                    adj=excluded.adj
            """, (
                team_id,
                str(row.get("date") or ""),
                name,
                str(row.get("gender") or "").strip(),
                float(weight) if pd.notna(weight) else None,
                side_pref,
                float(time_trial) if pd.notna(time_trial) else None,
                float(distance_1min) if pd.notna(distance_1min) else None,
                new_adj,
            ))

    return load_best_scores(team_id)


def delete_team_scores(team_id: int) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM scores WHERE team_id = ?", (team_id,))


def import_legacy_csv(team_id: int, lower_is_better: bool, csv_path: Path = LEGACY_CSV_PATH) -> int:
    if not csv_path.exists():
        return 0

    df = pd.read_csv(csv_path)
    df.columns = [str(c).strip().lower() for c in df.columns]

    required = {"name", "gender", "weight", "side_pref", "adj"}
    if not required.issubset(set(df.columns)):
        return 0

    upsert_scores(team_id, df, lower_is_better=lower_is_better)
    return len(df)


# -----------------------------
# Team settings
# -----------------------------
def load_team_settings(team_id: int) -> dict:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT formula_mode, custom_test_type, race_distance_m, custom_formula, lineup_config_json "
            "FROM team_settings WHERE team_id = ?",
            (team_id,),
        ).fetchone()

    if row is None:
        return {
            "formula_mode": "default",
            "custom_test_type": "time",
            "race_distance_m": 0,
            "custom_formula": "",
            "lineup_config": {},
        }

    return {
        "formula_mode": row["formula_mode"] or "default",
        "custom_test_type": row["custom_test_type"] or "time",
        "race_distance_m": row["race_distance_m"] or 0,
        "custom_formula": row["custom_formula"] or "",
        "lineup_config": json.loads(row["lineup_config_json"] or "{}"),
    }


def save_formula_settings(
    team_id: int,
    formula_mode: str,
    custom_test_type: str,
    race_distance_m: float,
    custom_formula: str,
) -> None:
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO team_settings (team_id, formula_mode, custom_test_type, race_distance_m, custom_formula)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(team_id) DO UPDATE SET
                formula_mode=excluded.formula_mode,
                custom_test_type=excluded.custom_test_type,
                race_distance_m=excluded.race_distance_m,
                custom_formula=excluded.custom_formula
        """, (team_id, formula_mode, custom_test_type, race_distance_m, custom_formula))


def save_lineup_config(team_id: int, config: dict) -> None:
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO team_settings (team_id, lineup_config_json)
            VALUES (?, ?)
            ON CONFLICT(team_id) DO UPDATE SET lineup_config_json=excluded.lineup_config_json
        """, (team_id, json.dumps(config)))


# -----------------------------
# Issues
# -----------------------------
def save_issue(team_id: int, issue_type: str, title: str, description: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO issues (team_id, issue_type, title, description) VALUES (?, ?, ?, ?)",
            (team_id, issue_type, title, description),
        )
