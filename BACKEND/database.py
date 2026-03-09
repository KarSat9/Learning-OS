"""
Database initialization and connection management.
Uses SQLite with WAL mode for better concurrent reads.
"""

import sqlite3
import os
from contextlib import contextmanager

DB_PATH = os.path.join(os.path.dirname(__file__), "learning_os.db")

SCHEMA = """
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

CREATE TABLE IF NOT EXISTS concepts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL UNIQUE,
    description TEXT    NOT NULL DEFAULT '',
    difficulty  INTEGER NOT NULL DEFAULT 1
                CHECK(difficulty BETWEEN 1 AND 5),
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS prerequisites (
    concept_id      INTEGER NOT NULL,
    prerequisite_id INTEGER NOT NULL,
    PRIMARY KEY (concept_id, prerequisite_id),
    FOREIGN KEY (concept_id)      REFERENCES concepts(id) ON DELETE CASCADE,
    FOREIGN KEY (prerequisite_id) REFERENCES concepts(id) ON DELETE CASCADE,
    CHECK (concept_id != prerequisite_id)
);

CREATE TABLE IF NOT EXISTS progress (
    concept_id    INTEGER PRIMARY KEY,
    mastery_level INTEGER NOT NULL DEFAULT 0
                  CHECK(mastery_level BETWEEN 0 AND 3),
    updated_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (concept_id) REFERENCES concepts(id) ON DELETE CASCADE
);

-- ── Knowledge Gap Detection tables ───────────────────────────────────────────

CREATE TABLE IF NOT EXISTS questions (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    concept_id     INTEGER NOT NULL,
    question_text  TEXT    NOT NULL,
    correct_answer TEXT    NOT NULL,
    difficulty     INTEGER NOT NULL DEFAULT 1
                   CHECK(difficulty BETWEEN 1 AND 5),
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (concept_id) REFERENCES concepts(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS user_answers (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     TEXT    NOT NULL DEFAULT 'default',
    question_id INTEGER NOT NULL,
    is_correct  INTEGER NOT NULL CHECK(is_correct IN (0,1)),
    answered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (question_id) REFERENCES questions(id) ON DELETE CASCADE
);
"""


def init_db() -> None:
    """Create tables if they don't exist."""
    with get_db() as conn:
        conn.executescript(SCHEMA)


@contextmanager
def get_db():
    """Context manager yielding a connected SQLite connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
