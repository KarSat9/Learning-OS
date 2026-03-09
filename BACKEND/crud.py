"""
CRUD operations — all raw SQL, no ORM overhead.
Each function receives an open sqlite3.Connection.
"""

import sqlite3
from typing import Optional
from models import ConceptOut


# ── Internal helpers ──────────────────────────────────────────────────────────

def _fetch_prerequisites(conn: sqlite3.Connection, concept_id: int) -> list[int]:
    rows = conn.execute(
        "SELECT prerequisite_id FROM prerequisites WHERE concept_id = ?",
        (concept_id,),
    ).fetchall()
    return [r["prerequisite_id"] for r in rows]


def _fetch_mastery(conn: sqlite3.Connection, concept_id: int) -> int:
    row = conn.execute(
        "SELECT mastery_level FROM progress WHERE concept_id = ?",
        (concept_id,),
    ).fetchone()
    return row["mastery_level"] if row else 0


def _row_to_concept(conn: sqlite3.Connection, row: sqlite3.Row) -> ConceptOut:
    return ConceptOut(
        id=row["id"],
        name=row["name"],
        description=row["description"],
        difficulty=row["difficulty"],
        mastery_level=_fetch_mastery(conn, row["id"]),
        prerequisites=_fetch_prerequisites(conn, row["id"]),
    )


# ── Concepts ──────────────────────────────────────────────────────────────────

def create_concept(
    conn: sqlite3.Connection,
    name: str,
    description: str,
    difficulty: int,
) -> ConceptOut:
    cur = conn.execute(
        "INSERT INTO concepts (name, description, difficulty) VALUES (?, ?, ?)",
        (name, description, difficulty),
    )
    concept_id = cur.lastrowid
    # Ensure a progress row exists
    conn.execute(
        "INSERT OR IGNORE INTO progress (concept_id, mastery_level) VALUES (?, 0)",
        (concept_id,),
    )
    return get_concept(conn, concept_id)


def get_concept(conn: sqlite3.Connection, concept_id: int) -> Optional[ConceptOut]:
    row = conn.execute(
        "SELECT * FROM concepts WHERE id = ?", (concept_id,)
    ).fetchone()
    if not row:
        return None
    return _row_to_concept(conn, row)


def get_all_concepts(conn: sqlite3.Connection) -> list[ConceptOut]:
    rows = conn.execute(
        "SELECT * FROM concepts ORDER BY created_at ASC"
    ).fetchall()
    return [_row_to_concept(conn, r) for r in rows]


def update_concept(
    conn: sqlite3.Connection,
    concept_id: int,
    name: Optional[str],
    description: Optional[str],
    difficulty: Optional[int],
) -> Optional[ConceptOut]:
    fields, values = [], []
    if name is not None:
        fields.append("name = ?");       values.append(name)
    if description is not None:
        fields.append("description = ?"); values.append(description)
    if difficulty is not None:
        fields.append("difficulty = ?");  values.append(difficulty)
    if not fields:
        return get_concept(conn, concept_id)
    values.append(concept_id)
    conn.execute(
        f"UPDATE concepts SET {', '.join(fields)} WHERE id = ?", values
    )
    return get_concept(conn, concept_id)


def delete_concept(conn: sqlite3.Connection, concept_id: int) -> bool:
    cur = conn.execute("DELETE FROM concepts WHERE id = ?", (concept_id,))
    return cur.rowcount > 0


# ── Prerequisites ─────────────────────────────────────────────────────────────

def add_prerequisite(
    conn: sqlite3.Connection, concept_id: int, prerequisite_id: int
) -> bool:
    """Returns False if the link already exists."""
    existing = conn.execute(
        "SELECT 1 FROM prerequisites WHERE concept_id=? AND prerequisite_id=?",
        (concept_id, prerequisite_id),
    ).fetchone()
    if existing:
        return False
    conn.execute(
        "INSERT INTO prerequisites (concept_id, prerequisite_id) VALUES (?, ?)",
        (concept_id, prerequisite_id),
    )
    return True


def remove_prerequisite(
    conn: sqlite3.Connection, concept_id: int, prerequisite_id: int
) -> bool:
    cur = conn.execute(
        "DELETE FROM prerequisites WHERE concept_id=? AND prerequisite_id=?",
        (concept_id, prerequisite_id),
    )
    return cur.rowcount > 0


# ── Progress ──────────────────────────────────────────────────────────────────

def set_mastery(
    conn: sqlite3.Connection, concept_id: int, mastery_level: int
) -> bool:
    conn.execute(
        """
        INSERT INTO progress (concept_id, mastery_level, updated_at)
        VALUES (?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(concept_id) DO UPDATE
          SET mastery_level = excluded.mastery_level,
              updated_at    = excluded.updated_at
        """,
        (concept_id, mastery_level),
    )
    return True


def get_all_progress(conn: sqlite3.Connection) -> dict[int, int]:
    """Returns {concept_id: mastery_level} for every tracked concept."""
    rows = conn.execute("SELECT concept_id, mastery_level FROM progress").fetchall()
    return {r["concept_id"]: r["mastery_level"] for r in rows}
