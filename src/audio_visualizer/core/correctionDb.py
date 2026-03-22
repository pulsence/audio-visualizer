"""SQLite correction database for tracking subtitle edits, prompt terms,
and replacement rules.

The database stores corrections made to bundle-backed subtitle entries so
they can feed prompt suggestions, replacement dictionaries, and future
LoRA training exports.  It uses WAL mode for safe concurrent reads and a
single-writer pattern that only commits on explicit action boundaries.
"""
from __future__ import annotations

import logging
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from audio_visualizer.app_paths import get_data_dir

logger = logging.getLogger(__name__)

_DB_FILENAME = "corrections.db"

# Current schema version — bump when migrations are needed.
_SCHEMA_VERSION = 1


def _default_db_path() -> Path:
    """Return the default database path inside the app data directory."""
    return get_data_dir() / _DB_FILENAME


class CorrectionDatabase:
    """SQLite-backed store for corrections, prompt terms, and replacement rules.

    Thread-safety: a single writer lock serialises all mutating operations.
    Read-only queries are safe to call from any thread thanks to WAL mode.

    Parameters
    ----------
    db_path:
        Filesystem path for the SQLite file.  Defaults to
        ``<data_dir>/corrections.db``.
    """

    def __init__(self, db_path: Path | str | None = None) -> None:
        self._db_path = Path(db_path) if db_path else _default_db_path()
        self._write_lock = threading.Lock()
        self._ensure_schema()

    # ------------------------------------------------------------------
    # Schema management
    # ------------------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        """Open a new connection with WAL mode and foreign keys enabled."""
        conn = sqlite3.connect(str(self._db_path), timeout=10)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self) -> None:
        """Create tables if they do not exist."""
        with self._write_lock:
            conn = self._connect()
            try:
                conn.executescript(_SCHEMA_SQL)
                conn.execute(
                    "INSERT OR IGNORE INTO meta (key, value) VALUES (?, ?)",
                    ("schema_version", str(_SCHEMA_VERSION)),
                )
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()
        logger.info("Correction database ready at %s", self._db_path)

    # ------------------------------------------------------------------
    # Corrections
    # ------------------------------------------------------------------

    def record_correction(
        self,
        *,
        source_media_path: str,
        time_start_ms: int,
        time_end_ms: int,
        original_text: str,
        corrected_text: str,
        speaker_label: Optional[str] = None,
        model_name: Optional[str] = None,
        lora_name: Optional[str] = None,
        confidence: Optional[float] = None,
        bundle_entry_id: Optional[str] = None,
    ) -> int:
        """Write a single correction row.

        Returns the ``rowid`` of the inserted correction.

        This is intended to be called on committed action boundaries
        (e.g. when the user finishes editing a cell), **not** on every
        keystroke.
        """
        if original_text == corrected_text:
            return -1  # No actual change — skip silently.

        now = datetime.now(timezone.utc).isoformat()
        with self._write_lock:
            conn = self._connect()
            try:
                cur = conn.execute(
                    """
                    INSERT INTO corrections (
                        source_media_path, time_start_ms, time_end_ms,
                        original_text, corrected_text, speaker_label,
                        model_name, lora_name, confidence,
                        bundle_entry_id, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        source_media_path,
                        time_start_ms,
                        time_end_ms,
                        original_text,
                        corrected_text,
                        speaker_label,
                        model_name,
                        lora_name,
                        confidence,
                        bundle_entry_id,
                        now,
                    ),
                )
                conn.commit()
                rowid = cur.lastrowid
                logger.debug(
                    "Recorded correction #%d: '%s' -> '%s'",
                    rowid,
                    original_text[:40],
                    corrected_text[:40],
                )
                return rowid or -1
            except Exception:
                conn.rollback()
                logger.exception("Failed to record correction")
                raise
            finally:
                conn.close()

    def query_corrections(
        self,
        *,
        source_media_path: Optional[str] = None,
        speaker_label: Optional[str] = None,
        model_name: Optional[str] = None,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        """Query corrections with optional filters.

        Returns a list of dicts, each representing one correction row.
        """
        clauses: list[str] = []
        params: list[Any] = []

        if source_media_path is not None:
            clauses.append("source_media_path = ?")
            params.append(source_media_path)
        if speaker_label is not None:
            clauses.append("speaker_label = ?")
            params.append(speaker_label)
        if model_name is not None:
            clauses.append("model_name = ?")
            params.append(model_name)

        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        sql = f"SELECT * FROM corrections{where} ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        conn = self._connect()
        try:
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def distinct_speaker_labels(self) -> list[str]:
        """Return all distinct non-null speaker labels across corrections."""
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT DISTINCT speaker_label FROM corrections "
                "WHERE speaker_label IS NOT NULL ORDER BY speaker_label"
            ).fetchall()
            return [r["speaker_label"] for r in rows]
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Prompt terms
    # ------------------------------------------------------------------

    def add_prompt_term(
        self,
        term: str,
        *,
        category: Optional[str] = None,
        speaker_label: Optional[str] = None,
        source: str = "user",
    ) -> int:
        """Add a prompt term.  Returns the rowid.

        Duplicate (term, speaker_label) pairs are silently skipped.
        """
        now = datetime.now(timezone.utc).isoformat()
        with self._write_lock:
            conn = self._connect()
            try:
                cur = conn.execute(
                    """
                    INSERT OR IGNORE INTO prompt_terms
                        (term, category, speaker_label, source, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (term, category, speaker_label, source, now),
                )
                conn.commit()
                return cur.lastrowid or -1
            except Exception:
                conn.rollback()
                logger.exception("Failed to add prompt term")
                raise
            finally:
                conn.close()

    def update_prompt_term(
        self,
        term_id: int,
        *,
        term: Optional[str] = None,
        category: Optional[str] = ...,  # type: ignore[assignment]
        speaker_label: Optional[str] = ...,  # type: ignore[assignment]
    ) -> bool:
        """Update fields on an existing prompt term.  Returns True if a row was modified."""
        sets: list[str] = []
        params: list[Any] = []
        if term is not None:
            sets.append("term = ?")
            params.append(term)
        if category is not ...:
            sets.append("category = ?")
            params.append(category)
        if speaker_label is not ...:
            sets.append("speaker_label = ?")
            params.append(speaker_label)
        if not sets:
            return False
        params.append(term_id)
        sql = f"UPDATE prompt_terms SET {', '.join(sets)} WHERE id = ?"
        with self._write_lock:
            conn = self._connect()
            try:
                cur = conn.execute(sql, params)
                conn.commit()
                return cur.rowcount > 0
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()

    def list_prompt_terms(
        self,
        *,
        speaker_label: Optional[str] = ...,  # type: ignore[assignment]
        filter_text: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """List prompt terms with optional filtering.

        Parameters
        ----------
        speaker_label:
            Ellipsis (default) means no speaker filter.
            ``None`` filters to terms with no speaker.
            A string filters to that specific speaker.
        filter_text:
            Substring match against the term text.
        """
        clauses: list[str] = []
        params: list[Any] = []

        if speaker_label is not ...:
            if speaker_label is None:
                clauses.append("speaker_label IS NULL")
            else:
                clauses.append("speaker_label = ?")
                params.append(speaker_label)

        if filter_text:
            clauses.append("term LIKE ?")
            params.append(f"%{filter_text}%")

        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        sql = f"SELECT * FROM prompt_terms{where} ORDER BY term"
        conn = self._connect()
        try:
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def remove_prompt_term(self, term_id: int) -> bool:
        """Remove a prompt term by its id.  Returns True if a row was deleted."""
        with self._write_lock:
            conn = self._connect()
            try:
                cur = conn.execute("DELETE FROM prompt_terms WHERE id = ?", (term_id,))
                conn.commit()
                return cur.rowcount > 0
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()

    def export_prompt_text(
        self,
        *,
        speaker_label: Optional[str] = ...,  # type: ignore[assignment]
    ) -> str:
        """Export prompt terms as a comma-separated string for Whisper initial_prompt."""
        terms = self.list_prompt_terms(speaker_label=speaker_label)
        return ", ".join(t["term"] for t in terms)

    # ------------------------------------------------------------------
    # Replacement rules
    # ------------------------------------------------------------------

    def add_replacement_rule(
        self,
        pattern: str,
        replacement: str,
        *,
        is_regex: bool = False,
        speaker_label: Optional[str] = None,
        source: str = "user",
    ) -> int:
        """Add a replacement rule.  Returns the rowid."""
        now = datetime.now(timezone.utc).isoformat()
        with self._write_lock:
            conn = self._connect()
            try:
                cur = conn.execute(
                    """
                    INSERT INTO replacement_rules
                        (pattern, replacement, is_regex, speaker_label, source, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (pattern, replacement, int(is_regex), speaker_label, source, now),
                )
                conn.commit()
                return cur.lastrowid or -1
            except Exception:
                conn.rollback()
                logger.exception("Failed to add replacement rule")
                raise
            finally:
                conn.close()

    def update_replacement_rule(
        self,
        rule_id: int,
        *,
        pattern: Optional[str] = None,
        replacement: Optional[str] = None,
        is_regex: Optional[bool] = None,
        speaker_label: Optional[str] = ...,  # type: ignore[assignment]
    ) -> bool:
        """Update fields on an existing replacement rule.  Returns True if modified."""
        sets: list[str] = []
        params: list[Any] = []
        if pattern is not None:
            sets.append("pattern = ?")
            params.append(pattern)
        if replacement is not None:
            sets.append("replacement = ?")
            params.append(replacement)
        if is_regex is not None:
            sets.append("is_regex = ?")
            params.append(int(is_regex))
        if speaker_label is not ...:
            sets.append("speaker_label = ?")
            params.append(speaker_label)
        if not sets:
            return False
        params.append(rule_id)
        sql = f"UPDATE replacement_rules SET {', '.join(sets)} WHERE id = ?"
        with self._write_lock:
            conn = self._connect()
            try:
                cur = conn.execute(sql, params)
                conn.commit()
                return cur.rowcount > 0
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()

    def list_replacement_rules(
        self,
        *,
        speaker_label: Optional[str] = ...,  # type: ignore[assignment]
        filter_text: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """List replacement rules with optional filtering."""
        clauses: list[str] = []
        params: list[Any] = []

        if speaker_label is not ...:
            if speaker_label is None:
                clauses.append("speaker_label IS NULL")
            else:
                clauses.append("speaker_label = ?")
                params.append(speaker_label)

        if filter_text:
            clauses.append("(pattern LIKE ? OR replacement LIKE ?)")
            params.extend([f"%{filter_text}%", f"%{filter_text}%"])

        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        sql = f"SELECT * FROM replacement_rules{where} ORDER BY pattern"
        conn = self._connect()
        try:
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def remove_replacement_rule(self, rule_id: int) -> bool:
        """Remove a replacement rule by its id.  Returns True if deleted."""
        with self._write_lock:
            conn = self._connect()
            try:
                cur = conn.execute(
                    "DELETE FROM replacement_rules WHERE id = ?", (rule_id,)
                )
                conn.commit()
                return cur.rowcount > 0
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()

    def export_replacement_dict(
        self,
        *,
        speaker_label: Optional[str] = ...,  # type: ignore[assignment]
    ) -> list[dict[str, Any]]:
        """Export replacement rules as a list of dicts suitable for dictionary files."""
        return self.list_replacement_rules(speaker_label=speaker_label)

    # ------------------------------------------------------------------
    # Training export
    # ------------------------------------------------------------------

    def export_training_pairs(
        self,
        *,
        source_media_path: Optional[str] = None,
        speaker_label: Optional[str] = None,
        model_name: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """Export correction pairs formatted for LoRA training.

        Each returned dict contains ``audio_ref``, ``time_start_ms``,
        ``time_end_ms``, ``original_text``, ``corrected_text``,
        ``speaker_label``, and ``model_name``.
        """
        clauses: list[str] = []
        params: list[Any] = []
        if source_media_path is not None:
            clauses.append("source_media_path = ?")
            params.append(source_media_path)
        if speaker_label is not None:
            clauses.append("speaker_label = ?")
            params.append(speaker_label)
        if model_name is not None:
            clauses.append("model_name = ?")
            params.append(model_name)

        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        sql = (
            "SELECT source_media_path, time_start_ms, time_end_ms, "
            "original_text, corrected_text, speaker_label, model_name "
            f"FROM corrections{where} ORDER BY created_at"
        )
        conn = self._connect()
        try:
            rows = conn.execute(sql, params).fetchall()
            return [
                {
                    "audio_ref": r["source_media_path"],
                    "time_start_ms": r["time_start_ms"],
                    "time_end_ms": r["time_end_ms"],
                    "original_text": r["original_text"],
                    "corrected_text": r["corrected_text"],
                    "speaker_label": r["speaker_label"],
                    "model_name": r["model_name"],
                }
                for r in rows
            ]
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def correction_count(self) -> int:
        """Return the total number of correction rows."""
        conn = self._connect()
        try:
            row = conn.execute("SELECT COUNT(*) AS cnt FROM corrections").fetchone()
            return row["cnt"] if row else 0
        finally:
            conn.close()

    def prompt_term_count(self) -> int:
        """Return the total number of prompt terms."""
        conn = self._connect()
        try:
            row = conn.execute("SELECT COUNT(*) AS cnt FROM prompt_terms").fetchone()
            return row["cnt"] if row else 0
        finally:
            conn.close()

    def replacement_rule_count(self) -> int:
        """Return the total number of replacement rules."""
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT COUNT(*) AS cnt FROM replacement_rules"
            ).fetchone()
            return row["cnt"] if row else 0
        finally:
            conn.close()


# ------------------------------------------------------------------
# Schema DDL
# ------------------------------------------------------------------

_SCHEMA_SQL = """\
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS corrections (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    source_media_path TEXT    NOT NULL,
    time_start_ms     INTEGER NOT NULL,
    time_end_ms       INTEGER NOT NULL,
    original_text     TEXT    NOT NULL,
    corrected_text    TEXT    NOT NULL,
    speaker_label     TEXT,
    model_name        TEXT,
    lora_name         TEXT,
    confidence        REAL,
    bundle_entry_id   TEXT,
    created_at        TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_corrections_media
    ON corrections (source_media_path);
CREATE INDEX IF NOT EXISTS idx_corrections_speaker
    ON corrections (speaker_label);
CREATE INDEX IF NOT EXISTS idx_corrections_bundle_entry
    ON corrections (bundle_entry_id);

CREATE TABLE IF NOT EXISTS prompt_terms (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    term           TEXT    NOT NULL,
    category       TEXT,
    speaker_label  TEXT,
    source         TEXT    NOT NULL DEFAULT 'user',
    created_at     TEXT    NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_prompt_terms_unique
    ON prompt_terms (term, COALESCE(speaker_label, ''));

CREATE INDEX IF NOT EXISTS idx_prompt_terms_speaker
    ON prompt_terms (speaker_label);

CREATE TABLE IF NOT EXISTS replacement_rules (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    pattern        TEXT    NOT NULL,
    replacement    TEXT    NOT NULL,
    is_regex       INTEGER NOT NULL DEFAULT 0,
    speaker_label  TEXT,
    source         TEXT    NOT NULL DEFAULT 'user',
    created_at     TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_replacement_rules_speaker
    ON replacement_rules (speaker_label);
"""
