# consent.py
"""
Consent gate, suppression list, and consent logging for BalancedBora.

Follows the pattern set by Safaricom's Zuri:
  - First-time users must reply AGREE before the bot will help them.
  - STOP unsubscribes; START or AGREE re-subscribes.
  - Every consent is timestamped and stored for audit purposes.
"""

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

CONSENT_DB_PATH = os.getenv(
    "BALANCE_BORA_CONSENT_DB",
    str(Path(__file__).with_name("consent.db"))
)

CONSENT_VERSION = "1.0"

STOP_WORDS = {"stop", "unsubscribe", "cancel", "end", "quit"}
START_WORDS = {"start", "unstop", "subscribe", "agree", "i agree", "yes"}


def _connect():
    con = sqlite3.connect(CONSENT_DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def init_db():
    con = _connect()
    try:
        con.executescript("""
            CREATE TABLE IF NOT EXISTS consents (
                phone         TEXT PRIMARY KEY,
                consented_at  TEXT NOT NULL,
                version       TEXT NOT NULL,
                consent_text  TEXT NOT NULL,
                ip_address    TEXT,
                channel       TEXT DEFAULT 'whatsapp'
            );

            CREATE TABLE IF NOT EXISTS suppressions (
                phone           TEXT PRIMARY KEY,
                suppressed_at   TEXT NOT NULL,
                reason          TEXT,
                keyword         TEXT
            );
        """)
        con.commit()
    finally:
        con.close()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def has_consented(phone: str) -> bool:
    con = _connect()
    try:
        row = con.execute(
            "SELECT version FROM consents WHERE phone = ?", (phone,)
        ).fetchone()
        return bool(row) and row["version"] == CONSENT_VERSION
    finally:
        con.close()


def record_consent(phone: str, consent_text: str,
                   ip_address: Optional[str] = None) -> None:
    con = _connect()
    try:
        con.execute("""
            INSERT INTO consents (phone, consented_at, version,
                                  consent_text, ip_address, channel)
            VALUES (?, ?, ?, ?, ?, 'whatsapp')
            ON CONFLICT(phone) DO UPDATE SET
                consented_at = excluded.consented_at,
                version      = excluded.version,
                consent_text = excluded.consent_text
        """, (phone, _now(), CONSENT_VERSION, consent_text, ip_address))
        con.commit()
    finally:
        con.close()


def is_suppressed(phone: str) -> bool:
    con = _connect()
    try:
        return bool(con.execute(
            "SELECT 1 FROM suppressions WHERE phone = ?", (phone,)
        ).fetchone())
    finally:
        con.close()


def suppress(phone: str, keyword: str) -> None:
    con = _connect()
    try:
        con.execute("""
            INSERT INTO suppressions (phone, suppressed_at, reason, keyword)
            VALUES (?, ?, 'user_request', ?)
            ON CONFLICT(phone) DO UPDATE SET
                suppressed_at = excluded.suppressed_at,
                keyword       = excluded.keyword
        """, (phone, _now(), keyword))
        con.commit()
    finally:
        con.close()


def unsuppress(phone: str) -> None:
    con = _connect()
    try:
        con.execute("DELETE FROM suppressions WHERE phone = ?", (phone,))
        con.commit()
    finally:
        con.close()


def get_consent_record(phone: str) -> Optional[dict]:
    con = _connect()
    try:
        row = con.execute(
            "SELECT * FROM consents WHERE phone = ?", (phone,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        con.close()


def count_consents() -> int:
    con = _connect()
    try:
        return con.execute("SELECT COUNT(*) FROM consents").fetchone()[0]
    finally:
        con.close()


init_db()