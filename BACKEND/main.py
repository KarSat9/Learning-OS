"""
Learning OS — FastAPI backend
Run:  uvicorn main:app --reload
"""

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

from database import init_db, get_db
from models import (
    ConceptCreate, ConceptUpdate, ConceptOut,
    PrerequisiteLink, MasteryUpdate,
    StudyPlan,
    QuestionCreate, QuestionOut,
    AnswerSubmit, AnswerResult,
    DiagnosisOut,
)
import crud
from algorithm import generate_study_plan, find_available_concepts, topological_sort
from knowledge_gap_service import diagnose_all_gaps, get_mastery_score

# ── App setup ──────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Learning OS",
    description="Dependency-aware study planner powered by a concept graph.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")


@app.on_event("startup")
def on_startup():
    init_db()


# ── Frontend ───────────────────────────────────────────────────────────────────

@app.get("/", include_in_schema=False)
def serve_ui():
    index = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index):
        return FileResponse(index)
    return {"message": "Learning OS API — see /docs"}


# ── Concepts ───────────────────────────────────────────────────────────────────

@app.get("/concepts", response_model=list[ConceptOut], tags=["Concepts"])
def list_concepts():
    """Return all concepts with their mastery levels and prerequisite IDs."""
    with get_db() as conn:
        return crud.get_all_concepts(conn)


@app.get("/concepts/{concept_id}", response_model=ConceptOut, tags=["Concepts"])
def get_concept(concept_id: int):
    with get_db() as conn:
        concept = crud.get_concept(conn, concept_id)
    if not concept:
        raise HTTPException(status_code=404, detail="Concept not found")
    return concept


@app.post("/concepts", response_model=ConceptOut, status_code=status.HTTP_201_CREATED, tags=["Concepts"])
def create_concept(body: ConceptCreate):
    """Create a new concept node."""
    with get_db() as conn:
        try:
            return crud.create_concept(conn, body.name, body.description, body.difficulty)
        except Exception as e:
            if "UNIQUE" in str(e):
                raise HTTPException(status_code=409, detail=f"Concept '{body.name}' already exists")
            raise


@app.put("/concepts/{concept_id}", response_model=ConceptOut, tags=["Concepts"])
def update_concept(concept_id: int, body: ConceptUpdate):
    with get_db() as conn:
        concept = crud.update_concept(conn, concept_id, body.name, body.description, body.difficulty)
    if not concept:
        raise HTTPException(status_code=404, detail="Concept not found")
    return concept


@app.delete("/concepts/{concept_id}", tags=["Concepts"])
def delete_concept(concept_id: int):
    with get_db() as conn:
        deleted = crud.delete_concept(conn, concept_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Concept not found")
    return {"deleted": concept_id}


# ── Prerequisites ──────────────────────────────────────────────────────────────

@app.post("/prerequisites", status_code=status.HTTP_201_CREATED, tags=["Prerequisites"])
def add_prerequisite(body: PrerequisiteLink):
    """
    Link concept_id → prerequisite_id.
    Meaning: concept_id REQUIRES prerequisite_id to be mastered first.
    """
    with get_db() as conn:
        # Validate both concepts exist
        if not crud.get_concept(conn, body.concept_id):
            raise HTTPException(status_code=404, detail=f"Concept {body.concept_id} not found")
        if not crud.get_concept(conn, body.prerequisite_id):
            raise HTTPException(status_code=404, detail=f"Concept {body.prerequisite_id} not found")
        added = crud.add_prerequisite(conn, body.concept_id, body.prerequisite_id)
    if not added:
        raise HTTPException(status_code=409, detail="Prerequisite link already exists")
    return {"linked": body.dict()}


@app.delete("/prerequisites/{concept_id}/{prerequisite_id}", tags=["Prerequisites"])
def remove_prerequisite(concept_id: int, prerequisite_id: int):
    with get_db() as conn:
        removed = crud.remove_prerequisite(conn, concept_id, prerequisite_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Prerequisite link not found")
    return {"removed": {"concept_id": concept_id, "prerequisite_id": prerequisite_id}}


# ── Progress ───────────────────────────────────────────────────────────────────

@app.put("/progress/{concept_id}", tags=["Progress"])
def update_mastery(concept_id: int, body: MasteryUpdate):
    """Set mastery level: 0=Not Started, 1=Learning, 2=Practicing, 3=Mastered."""
    with get_db() as conn:
        if not crud.get_concept(conn, concept_id):
            raise HTTPException(status_code=404, detail="Concept not found")
        crud.set_mastery(conn, concept_id, body.mastery_level)
    return {"concept_id": concept_id, "mastery_level": body.mastery_level}


# ── Algorithm endpoints ────────────────────────────────────────────────────────

@app.get("/study-plan", response_model=StudyPlan, tags=["Algorithm"])
def get_study_plan(max_tasks: int = 3, user_id: str = "default", gap_priority: bool = True):
    """
    Generate today's study plan.
    When gap_priority=true (default), detected root-gap concepts are surfaced first.
    """
    with get_db() as conn:
        concepts = crud.get_all_concepts(conn)
        progress = crud.get_all_progress(conn)
        gap_ids: list[int] = []
        if gap_priority:
            diagnosis = diagnose_all_gaps(conn, user_id)
            gap_ids = list({g.root_gap_id for g in diagnosis.gaps})
    return generate_study_plan(concepts, progress, max_tasks=max_tasks, gap_ids=gap_ids)


@app.get("/available-concepts", response_model=list[ConceptOut], tags=["Algorithm"])
def get_available_concepts():
    """Return concepts whose prerequisites are all mastered."""
    with get_db() as conn:
        concepts = crud.get_all_concepts(conn)
        progress = crud.get_all_progress(conn)
    return find_available_concepts(concepts, progress)


@app.get("/study-order", response_model=list[int], tags=["Algorithm"])
def get_study_order():
    """Return concept IDs in valid topological order (prerequisite-safe sequence)."""
    with get_db() as conn:
        concepts = crud.get_all_concepts(conn)
    return topological_sort(concepts)


# ── Questions ──────────────────────────────────────────────────────────────────

@app.get("/questions", response_model=list[QuestionOut], tags=["Questions"])
def list_questions(concept_id: int | None = None):
    """List all questions, optionally filtered by concept."""
    with get_db() as conn:
        if concept_id:
            rows = conn.execute(
                "SELECT * FROM questions WHERE concept_id = ? ORDER BY id",
                (concept_id,),
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM questions ORDER BY id").fetchall()
    return [QuestionOut(**dict(r)) for r in rows]


@app.post("/questions", response_model=QuestionOut, status_code=status.HTTP_201_CREATED, tags=["Questions"])
def create_question(body: QuestionCreate):
    """Add a practice question for a concept."""
    with get_db() as conn:
        if not crud.get_concept(conn, body.concept_id):
            raise HTTPException(status_code=404, detail="Concept not found")
        cur = conn.execute(
            "INSERT INTO questions (concept_id, question_text, correct_answer, difficulty) VALUES (?,?,?,?)",
            (body.concept_id, body.question_text, body.correct_answer, body.difficulty),
        )
        row = conn.execute("SELECT * FROM questions WHERE id=?", (cur.lastrowid,)).fetchone()
    return QuestionOut(**dict(row))


@app.delete("/questions/{question_id}", tags=["Questions"])
def delete_question(question_id: int):
    with get_db() as conn:
        cur = conn.execute("DELETE FROM questions WHERE id=?", (question_id,))
    if cur.rowcount == 0:
        raise HTTPException(status_code=404, detail="Question not found")
    return {"deleted": question_id}


# ── Answers ────────────────────────────────────────────────────────────────────

@app.post("/answers", response_model=AnswerResult, tags=["Answers"])
def submit_answer(body: AnswerSubmit):
    """
    Record a learner's answer and return the updated mastery score for the concept.
    The mastery score is recomputed from all answers so the progress table stays
    consistent with quiz performance.
    """
    with get_db() as conn:
        q_row = conn.execute("SELECT * FROM questions WHERE id=?", (body.question_id,)).fetchone()
        if not q_row:
            raise HTTPException(status_code=404, detail="Question not found")

        conn.execute(
            "INSERT INTO user_answers (user_id, question_id, is_correct) VALUES (?,?,?)",
            (body.user_id, body.question_id, int(body.is_correct)),
        )

        concept_id = q_row["concept_id"]
        score      = get_mastery_score(conn, concept_id, body.user_id)

        # Sync the integer mastery_level in progress table (0–3 buckets)
        level = 0
        if score >= 1.0:          level = 3
        elif score >= 0.75:       level = 2
        elif score > 0.0:         level = 1
        crud.set_mastery(conn, concept_id, level)

    return AnswerResult(
        question_id   = body.question_id,
        is_correct    = body.is_correct,
        mastery_score = score,
    )


@app.get("/answers/{concept_id}", tags=["Answers"])
def get_concept_answers(concept_id: int, user_id: str = "default"):
    """Return answer history and mastery score for a specific concept."""
    with get_db() as conn:
        if not crud.get_concept(conn, concept_id):
            raise HTTPException(status_code=404, detail="Concept not found")
        rows = conn.execute(
            """
            SELECT ua.id, ua.question_id, ua.is_correct, ua.answered_at,
                   q.question_text
            FROM user_answers ua
            JOIN questions q ON q.id = ua.question_id
            WHERE q.concept_id = ? AND ua.user_id = ?
            ORDER BY ua.answered_at DESC
            """,
            (concept_id, user_id),
        ).fetchall()
        score = get_mastery_score(conn, concept_id, user_id)
    return {
        "concept_id":    concept_id,
        "mastery_score": score,
        "total":         len(rows),
        "correct":       sum(1 for r in rows if r["is_correct"]),
        "history":       [dict(r) for r in rows],
    }


# ── Knowledge Gap Detection ────────────────────────────────────────────────────

@app.get("/diagnose-learning-gaps", response_model=DiagnosisOut, tags=["Gap Detection"])
def diagnose_gaps(user_id: str = "default"):
    """
    Analyse the prerequisite graph to identify root-cause knowledge gaps.

    For each weak concept (mastery score < 0.6) the algorithm walks its
    prerequisite chain recursively and returns the deepest weak node —
    the real concept that needs remediation.

    Response includes:
      gaps        — list of {weak_concept, root_gap, recommendation}
      all_scores  — mastery score 0.0–1.0 for every concept (used by the UI)
    """
    with get_db() as conn:
        return diagnose_all_gaps(conn, user_id)


# ── Seed ───────────────────────────────────────────────────────────────────────

@app.post("/seed", tags=["Dev"])
def seed_example_data():
    """Populate the database with an ML curriculum for demonstration."""
    from seed import seed
    seed()
    return {"message": "Database seeded with ML curriculum"}


# ── Stats ──────────────────────────────────────────────────────────────────────

@app.get("/stats", tags=["Stats"])
def get_stats():
    """Summary statistics for the dashboard."""
    with get_db() as conn:
        concepts = crud.get_all_concepts(conn)
        progress = crud.get_all_progress(conn)

    mastery_counts = {0: 0, 1: 0, 2: 0, 3: 0}
    for c in concepts:
        lvl = progress.get(c.id, 0)
        mastery_counts[lvl] += 1

    available = find_available_concepts(concepts, progress)

    return {
        "total_concepts":    len(concepts),
        "mastered":          mastery_counts[3],
        "practicing":        mastery_counts[2],
        "learning":          mastery_counts[1],
        "not_started":       mastery_counts[0],
        "available_to_study": len(available),
        "completion_pct":    round(mastery_counts[3] / len(concepts) * 100, 1) if concepts else 0,
    }
