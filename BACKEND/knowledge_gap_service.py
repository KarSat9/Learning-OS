"""
Knowledge Gap Detection Service
================================
Identifies the *root prerequisite* responsible for a learner's difficulty
with a given concept.

Public API
──────────
  get_mastery_score(conn, concept_id, user_id)  → float  0.0–1.0
  find_root_gap(conn, concept_id, user_id)       → (gap_id, gap_score)
  diagnose_all_gaps(conn, user_id)               → DiagnosisOut

Design decisions
──────────────────
• Mastery score is computed from user_answers:
    score = correct_answers / total_attempts   (0.0 if no attempts)
  If a concept has *no answer data at all*, we fall back gracefully to
    score = mastery_level / 3.0
  so the existing slider-based progress still drives diagnostics before
  any quiz data exists.

• find_root_gap walks the prerequisite graph depth-first.
  At each node it picks the weakest prerequisite and recurses into it.
  Recursion stops when:
    - the node has no prerequisites, OR
    - none of the prerequisites are weaker than the current node, OR
    - the node has already been visited (cycle guard).
  This always returns the *deepest* weak ancestor — the true root cause.

• diagnose_all_gaps only reports on concepts that are themselves weak
  AND have at least one prerequisite (no point diagnosing leaf nodes).
"""

from __future__ import annotations

import sqlite3
from models import WEAK_THRESHOLD, GapItem, DiagnosisOut


# ── Mastery score ──────────────────────────────────────────────────────────────

def get_mastery_score(
    conn: sqlite3.Connection,
    concept_id: int,
    user_id: str = "default",
) -> float:
    """
    Return a 0.0–1.0 mastery score for a concept.

    Priority:
      1. answer-based score  (correct / total from user_answers)
      2. slider-based score  (mastery_level / 3.0 from progress table)
      3. 0.0 if the concept has never been touched
    """
    row = conn.execute(
        """
        SELECT
            COUNT(*)                                   AS total,
            SUM(CASE WHEN ua.is_correct = 1 THEN 1 ELSE 0 END) AS correct
        FROM user_answers ua
        JOIN questions q ON q.id = ua.question_id
        WHERE q.concept_id = ? AND ua.user_id = ?
        """,
        (concept_id, user_id),
    ).fetchone()

    if row and row["total"] and row["total"] > 0:
        return round(row["correct"] / row["total"], 4)

    # Fall back to slider-based mastery
    prog = conn.execute(
        "SELECT mastery_level FROM progress WHERE concept_id = ?",
        (concept_id,),
    ).fetchone()
    if prog:
        return round(prog["mastery_level"] / 3.0, 4)

    return 0.0


def get_all_mastery_scores(
    conn: sqlite3.Connection,
    user_id: str = "default",
) -> dict[int, float]:
    """Return {concept_id: score} for every concept in the database."""
    concept_ids = [
        r["id"] for r in conn.execute("SELECT id FROM concepts").fetchall()
    ]
    return {cid: get_mastery_score(conn, cid, user_id) for cid in concept_ids}


# ── Prerequisite helpers ───────────────────────────────────────────────────────

def _get_prerequisites(conn: sqlite3.Connection, concept_id: int) -> list[int]:
    rows = conn.execute(
        "SELECT prerequisite_id FROM prerequisites WHERE concept_id = ?",
        (concept_id,),
    ).fetchall()
    return [r["prerequisite_id"] for r in rows]


# ── Root gap algorithm ─────────────────────────────────────────────────────────

def find_root_gap(
    conn: sqlite3.Connection,
    concept_id: int,
    user_id: str = "default",
    _visited: set[int] | None = None,
) -> tuple[int, float]:
    """
    Recursively walk the prerequisite graph to find the deepest weak node.

    Returns
    -------
    (gap_concept_id, gap_score)
        The concept that is the root cause of the difficulty,
        and its mastery score.

    Algorithm
    ---------
    1. Get all prerequisites of concept_id.
    2. Among those that are weak (score < WEAK_THRESHOLD), pick the weakest.
    3. Recurse into that prerequisite.
    4. If no prerequisite is weak, this concept IS the root gap — return it.
    5. Cycle guard via _visited set.
    """
    if _visited is None:
        _visited = set()
    _visited.add(concept_id)

    prereqs = _get_prerequisites(conn, concept_id)

    # Score every prerequisite
    scored = [
        (pid, get_mastery_score(conn, pid, user_id))
        for pid in prereqs
        if pid not in _visited
    ]

    # Filter to only weak prerequisites
    weak_prereqs = [(pid, score) for pid, score in scored if score < WEAK_THRESHOLD]

    if not weak_prereqs:
        # No weak prerequisites — this concept itself is the root gap
        return concept_id, get_mastery_score(conn, concept_id, user_id)

    # Pick the weakest prerequisite to recurse into
    weakest_id, weakest_score = min(weak_prereqs, key=lambda x: x[1])

    return find_root_gap(conn, weakest_id, user_id, _visited)


# ── Full diagnosis ─────────────────────────────────────────────────────────────

def diagnose_all_gaps(
    conn: sqlite3.Connection,
    user_id: str = "default",
) -> DiagnosisOut:
    """
    Scan every concept. For each weak concept that has prerequisites,
    find its root gap and build a human-readable recommendation.

    Returns a DiagnosisOut with:
      gaps        — list of GapItem (one per weak concept that has a root gap)
      all_scores  — mastery score for every concept (used by UI to color nodes)
    """
    # Fetch all concepts with their prerequisite lists
    rows = conn.execute(
        "SELECT id, name FROM concepts ORDER BY id"
    ).fetchall()
    concepts = [{"id": r["id"], "name": r["name"]} for r in rows]

    concept_names: dict[int, str] = {c["id"]: c["name"] for c in concepts}
    all_scores = get_all_mastery_scores(conn, user_id)
    prereq_map: dict[int, list[int]] = {
        c["id"]: _get_prerequisites(conn, c["id"]) for c in concepts
    }

    gaps: list[GapItem] = []
    seen_gaps: set[tuple[int, int]] = set()   # (weak_id, root_id) — avoid duplicate rows

    for concept in concepts:
        cid   = concept["id"]
        score = all_scores.get(cid, 0.0)

        # Only report on concepts that are weak AND have prerequisites
        if score >= WEAK_THRESHOLD:
            continue
        if not prereq_map[cid]:
            continue

        root_id, root_score = find_root_gap(conn, cid, user_id)
        pair = (cid, root_id)
        if pair in seen_gaps:
            continue
        seen_gaps.add(pair)

        cname    = concept_names[cid]
        rname    = concept_names.get(root_id, f"Concept #{root_id}")

        if root_id == cid:
            recommendation = (
                f"'{cname}' itself needs direct practice — "
                f"no weaker prerequisite was found."
            )
        else:
            recommendation = (
                f"Difficulty with '{cname}' may be caused by a weakness in "
                f"'{rname}'. Review '{rname}' before continuing."
            )

        gaps.append(GapItem(
            weak_concept_id   = cid,
            weak_concept_name = cname,
            weak_score        = score,
            root_gap_id       = root_id,
            root_gap_name     = rname,
            root_gap_score    = root_score,
            recommendation    = recommendation,
        ))

    # Sort: most urgent (lowest score) first
    gaps.sort(key=lambda g: g.weak_score)

    return DiagnosisOut(
        gaps           = gaps,
        all_scores     = all_scores,
        weak_threshold = WEAK_THRESHOLD,
    )
