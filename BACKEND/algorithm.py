"""
Core learning algorithm.

Two main responsibilities:
  1. find_available_concepts()  — which concepts can be studied right now?
  2. generate_study_plan()      — rank them and return today's queue

Design decisions
────────────────
• A concept is *available* when every prerequisite has mastery_level == 3 (Mastered)
  OR the concept has no prerequisites at all.
• Ranking uses a composite score:  score = mastery_level * 10 + difficulty
  Lower score → higher priority (we want low mastery, low difficulty first).
• Study duration is estimated from remaining work:
    base     = (3 - mastery_level) * difficulty * 5   minutes
    clamped  = max(10, min(45, base))
  A mastered concept gets 0 duration and is excluded from the plan.
"""

from __future__ import annotations
import sqlite3
from models import ConceptOut, StudyTask, StudyPlan, MASTERY_LABELS, MASTERY_ACTIONS


# ── Availability ──────────────────────────────────────────────────────────────

def find_available_concepts(
    concepts: list[ConceptOut],
    progress: dict[int, int],
) -> list[ConceptOut]:
    """
    Return concepts whose prerequisites are ALL mastered (level 3).
    Concepts with NO prerequisites are always available.
    Already-mastered concepts are excluded (nothing left to learn).
    """
    mastered_ids: set[int] = {cid for cid, lvl in progress.items() if lvl == 3}

    available = []
    for concept in concepts:
        # Skip already mastered
        if progress.get(concept.id, 0) == 3:
            continue
        # Available if all prerequisites are in the mastered set
        if all(prereq_id in mastered_ids for prereq_id in concept.prerequisites):
            available.append(concept)

    return available


# ── Ranking ───────────────────────────────────────────────────────────────────

def rank_concepts(
    concepts: list[ConceptOut],
    progress: dict[int, int],
) -> list[ConceptOut]:
    """
    Sort available concepts by (mastery_level ASC, difficulty ASC).
    This surfaces concepts that are:
      • least progressed first (most need),
      • easiest among equals (quick wins build momentum).
    """
    def score(c: ConceptOut) -> tuple[int, int]:
        mastery = progress.get(c.id, 0)
        return (mastery, c.difficulty)

    return sorted(concepts, key=score)


# ── Duration estimate ─────────────────────────────────────────────────────────

def estimate_duration(mastery_level: int, difficulty: int) -> int:
    """Estimate study time in minutes."""
    remaining_stages = 3 - mastery_level          # 0–3 stages left
    raw = remaining_stages * difficulty * 5        # 0–75 min raw
    return max(10, min(45, raw)) if remaining_stages > 0 else 0


# ── Study plan ────────────────────────────────────────────────────────────────

def generate_study_plan(
    concepts: list[ConceptOut],
    progress: dict[int, int],
    max_tasks: int = 3,
    gap_ids: list[int] | None = None,
) -> StudyPlan:
    """
    Build today's study plan:
      1. Find available concepts.
      2. If gap_ids are provided, put those first (they are root gaps that
         need remediation — bump them to the front regardless of normal rank).
      3. Fill remaining slots with the standard (mastery ASC, difficulty ASC) ranking.
      4. Return the top `max_tasks` as StudyTask objects.
    """
    available      = find_available_concepts(concepts, progress)
    available_ids  = {c.id for c in available}
    ranked         = rank_concepts(available, progress)

    if gap_ids:
        # Concepts that are both available AND identified as root gaps
        gap_first  = [c for c in ranked if c.id in set(gap_ids)]
        gap_rest   = [c for c in ranked if c.id not in set(gap_ids)]
        ranked     = gap_first + gap_rest

    top = ranked[:max_tasks]

    tasks = []
    for concept in top:
        mastery  = progress.get(concept.id, 0)
        duration = estimate_duration(mastery, concept.difficulty)
        tasks.append(
            StudyTask(
                concept_id     = concept.id,
                name           = concept.name,
                description    = concept.description,
                difficulty     = concept.difficulty,
                mastery_level  = mastery,
                mastery_label  = MASTERY_LABELS[mastery],
                action         = MASTERY_ACTIONS[mastery],
                duration_minutes = duration,
            )
        )

    return StudyPlan(
        tasks         = tasks,
        total_minutes = sum(t.duration_minutes for t in tasks),
    )


# ── Graph helpers ─────────────────────────────────────────────────────────────

def build_adjacency(concepts: list[ConceptOut]) -> dict[int, list[int]]:
    """
    Returns {concept_id: [prerequisite_id, ...]} adjacency map.
    Useful for graph rendering on the frontend.
    """
    return {c.id: c.prerequisites for c in concepts}


def topological_sort(concepts: list[ConceptOut]) -> list[int]:
    """
    Kahn's algorithm — returns concept IDs in a valid study order
    (prerequisites always before dependents).
    """
    from collections import deque

    in_degree: dict[int, int] = {c.id: 0 for c in concepts}
    dependents: dict[int, list[int]] = {c.id: [] for c in concepts}

    for c in concepts:
        for prereq_id in c.prerequisites:
            if prereq_id in in_degree:
                in_degree[c.id] += 1
                dependents[prereq_id].append(c.id)

    queue  = deque(cid for cid, deg in in_degree.items() if deg == 0)
    result = []

    while queue:
        cid = queue.popleft()
        result.append(cid)
        for dep in dependents[cid]:
            in_degree[dep] -= 1
            if in_degree[dep] == 0:
                queue.append(dep)

    return result
