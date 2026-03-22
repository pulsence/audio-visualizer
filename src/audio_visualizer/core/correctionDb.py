"""SQLite correction database for tracking subtitle edits, prompt terms,
and replacement rules.

The database stores corrections made to bundle-backed subtitle entries so
they can feed prompt suggestions, replacement dictionaries, and future
LoRA training exports.  It uses WAL mode for safe concurrent reads and a
single-writer pattern that only commits on explicit action boundaries.
"""
from __future__ import annotations

import csv
import logging
import os
import sqlite3
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, List, Optional, Tuple

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

        duplicate_id = self._find_duplicate_correction(
            source_media_path=source_media_path,
            time_start_ms=time_start_ms,
            time_end_ms=time_end_ms,
            original_text=original_text,
            corrected_text=corrected_text,
            speaker_label=speaker_label,
            model_name=model_name,
            lora_name=lora_name,
            confidence=confidence,
            bundle_entry_id=bundle_entry_id,
        )
        if duplicate_id is not None:
            logger.debug("Skipping duplicate correction row #%d", duplicate_id)
            return -1

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

    def _find_duplicate_correction(
        self,
        *,
        source_media_path: str,
        time_start_ms: int,
        time_end_ms: int,
        original_text: str,
        corrected_text: str,
        speaker_label: Optional[str],
        model_name: Optional[str],
        lora_name: Optional[str],
        confidence: Optional[float],
        bundle_entry_id: Optional[str],
    ) -> int | None:
        """Return an existing correction id when the new row would be identical."""
        conn = self._connect()
        try:
            row = conn.execute(
                """
                SELECT id
                FROM corrections
                WHERE source_media_path = ?
                  AND time_start_ms = ?
                  AND time_end_ms = ?
                  AND original_text = ?
                  AND corrected_text = ?
                  AND speaker_label IS ?
                  AND model_name IS ?
                  AND lora_name IS ?
                  AND confidence IS ?
                  AND bundle_entry_id IS ?
                LIMIT 1
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
                ),
            ).fetchone()
            return int(row["id"]) if row else None
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
        """Return all distinct non-null speaker labels across correction data.

        Speaker-aware prompt terms and replacement rules may exist before any
        correction row is recorded for that speaker, so the Advanced tab needs
        the union across all three relevant tables instead of just
        ``corrections``.
        """
        conn = self._connect()
        try:
            rows = conn.execute(
                """
                SELECT speaker_label FROM corrections WHERE speaker_label IS NOT NULL
                UNION
                SELECT speaker_label FROM prompt_terms WHERE speaker_label IS NOT NULL
                UNION
                SELECT speaker_label FROM replacement_rules WHERE speaker_label IS NOT NULL
                ORDER BY speaker_label
                """
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

    def export_training_dataset(
        self,
        output_dir: Path,
        *,
        source_media_path: Optional[str] = None,
        speaker_label: Optional[str] = None,
        model_name: Optional[str] = None,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> Tuple[int, int, List[str]]:
        """Export correction pairs as audio clips + metadata.csv for training.

        Each correction pair that references an existing source media file
        gets its audio segment extracted using PyAV and written as a 16kHz
        mono WAV clip.  A ``metadata.csv`` is written with columns:
        ``file_name``, ``text``, ``original_text``, ``speaker_label``.

        Parameters
        ----------
        output_dir:
            Directory to write clips and metadata.csv into.
        source_media_path, speaker_label, model_name:
            Passed through to :meth:`export_training_pairs` for filtering.
        progress_callback:
            Optional ``(current, total, message)`` callback for UI progress.

        Returns
        -------
        tuple of (exported_count, skipped_count, warnings)
            *exported_count* is the number of clips written.
            *skipped_count* is the number of pairs skipped (missing file, etc.).
            *warnings* is a list of human-readable warning strings.
        """
        pairs = self.export_training_pairs(
            source_media_path=source_media_path,
            speaker_label=speaker_label,
            model_name=model_name,
        )

        if not pairs:
            return 0, 0, ["No correction pairs found matching the filters."]

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        exported = 0
        skipped = 0
        warnings: List[str] = []
        metadata_rows: List[dict[str, str]] = []

        total = len(pairs)
        for idx, pair in enumerate(pairs):
            audio_ref = pair["audio_ref"]
            if progress_callback:
                progress_callback(idx, total, f"Processing {Path(audio_ref).name}")

            if not os.path.isfile(audio_ref):
                warnings.append(f"Skipped: source file not found: {audio_ref}")
                skipped += 1
                continue

            start_ms = pair["time_start_ms"]
            end_ms = pair["time_end_ms"]
            if end_ms <= start_ms:
                warnings.append(
                    f"Skipped: invalid time range {start_ms}-{end_ms}ms in {audio_ref}"
                )
                skipped += 1
                continue

            clip_name = f"clip_{exported:05d}.wav"
            clip_path = output_dir / clip_name

            try:
                _extract_audio_segment(
                    source_path=audio_ref,
                    output_path=clip_path,
                    start_ms=start_ms,
                    end_ms=end_ms,
                )
            except Exception as exc:
                warnings.append(f"Skipped: extraction failed for {audio_ref}: {exc}")
                skipped += 1
                continue

            metadata_rows.append({
                "file_name": clip_name,
                "text": pair["corrected_text"],
                "original_text": pair["original_text"],
                "speaker_label": pair.get("speaker_label") or "",
            })
            exported += 1

        # Write metadata.csv
        csv_path = output_dir / "metadata.csv"
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f, fieldnames=["file_name", "text", "original_text", "speaker_label"]
            )
            writer.writeheader()
            writer.writerows(metadata_rows)

        if progress_callback:
            progress_callback(total, total, "Export complete")

        logger.info(
            "Training dataset exported: %d clips, %d skipped, to %s",
            exported,
            skipped,
            output_dir,
        )
        return exported, skipped, warnings

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
# Audio extraction helper
# ------------------------------------------------------------------


def _extract_audio_segment(
    source_path: str,
    output_path: Path,
    start_ms: int,
    end_ms: int,
    sample_rate: int = 16000,
) -> None:
    """Extract an audio segment from *source_path* and write a 16kHz mono WAV.

    Uses PyAV for decoding.  The output is always 16kHz mono signed-16-bit PCM,
    which is the format expected by Whisper-based training pipelines.
    """
    import array
    import struct
    import av

    start_sec = start_ms / 1000.0
    end_sec = end_ms / 1000.0

    container = av.open(source_path)
    try:
        audio_stream = container.streams.audio[0]
        # Seek to just before the desired start
        seek_ts = int(start_sec / audio_stream.time_base)
        container.seek(max(0, seek_ts - 1), stream=audio_stream)

        resampler = av.AudioResampler(
            format="s16",
            layout="mono",
            rate=sample_rate,
        )

        samples: list[bytes] = []
        collecting = False

        for frame in container.decode(audio=0):
            frame_start = float(frame.pts * audio_stream.time_base)
            frame_end = frame_start + (frame.samples / frame.sample_rate)

            if frame_end < start_sec:
                continue
            if frame_start > end_sec:
                break

            collecting = True
            resampled = resampler.resample(frame)
            for r_frame in resampled:
                raw = bytes(r_frame.planes[0])
                # Trim to the desired time range
                frame_sr = r_frame.sample_rate
                r_start = float(r_frame.pts * audio_stream.time_base) if r_frame.pts is not None else frame_start
                r_end = r_start + (r_frame.samples / frame_sr)

                if r_start < start_sec:
                    skip_samples = int((start_sec - r_start) * frame_sr)
                    raw = raw[skip_samples * 2:]
                if r_end > end_sec:
                    keep_samples = int((end_sec - max(r_start, start_sec)) * frame_sr)
                    raw = raw[:keep_samples * 2]
                if raw:
                    samples.append(raw)

        if not collecting:
            # Flush resampler
            resampled = resampler.resample(None)
            for r_frame in resampled:
                raw = bytes(r_frame.planes[0])
                if raw:
                    samples.append(raw)
    finally:
        container.close()

    # Write WAV file (PCM s16le mono)
    pcm_data = b"".join(samples)
    _write_wav(output_path, pcm_data, sample_rate=sample_rate, channels=1, sample_width=2)


def _write_wav(
    path: Path,
    pcm_data: bytes,
    sample_rate: int,
    channels: int,
    sample_width: int,
) -> None:
    """Write raw PCM data as a WAV file."""
    import struct

    data_size = len(pcm_data)
    # RIFF header
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        36 + data_size,
        b"WAVE",
        b"fmt ",
        16,                            # chunk size
        1,                             # PCM format
        channels,
        sample_rate,
        sample_rate * channels * sample_width,  # byte rate
        channels * sample_width,       # block align
        sample_width * 8,              # bits per sample
        b"data",
        data_size,
    )
    with open(path, "wb") as f:
        f.write(header)
        f.write(pcm_data)


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
