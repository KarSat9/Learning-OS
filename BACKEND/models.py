"""
Pydantic models for API request validation and response serialization.
"""

from pydantic import BaseModel, Field
from typing import Optional


# ── Concepts ──────────────────────────────────────────────────────────────────

class ConceptCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    description: str = Field("", max_length=1000)
    difficulty: int = Field(1, ge=1, le=5)


class ConceptUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=120)
    description: Optional[str] = Field(None, max_length=1000)
    difficulty: Optional[int] = Field(None, ge=1, le=5)


class ConceptOut(BaseModel):
    id: int
    name: str
    description: str
    difficulty: int
    mastery_level: int          # joined from progress table
    prerequisites: list[int]    # list of prerequisite concept IDs


# ── Prerequisites ─────────────────────────────────────────────────────────────

class PrerequisiteLink(BaseModel):
    concept_id: int
    prerequisite_id: int


# ── Progress ──────────────────────────────────────────────────────────────────

class MasteryUpdate(BaseModel):
    mastery_level: int = Field(..., ge=0, le=3)


# ── Study Plan ────────────────────────────────────────────────────────────────

MASTERY_LABELS = {
    0: "Not Started",
    1: "Learning",
    2: "Practicing",
    3: "Mastered",
}

MASTERY_ACTIONS = {
    0: "Read introduction",
    1: "Study theory",
    2: "Practice exercises",
    3: "Review & reinforce",
}


class StudyTask(BaseModel):
    concept_id: int
    name: str
    description: str
    difficulty: int
    mastery_level: int
    mastery_label: str
    action: str
    duration_minutes: int


class StudyPlan(BaseModel):
    tasks: list[StudyTask]
    total_minutes: int


# ── Questions ─────────────────────────────────────────────────────────────────

class QuestionCreate(BaseModel):
    concept_id:     int
    question_text:  str  = Field(..., min_length=5, max_length=500)
    correct_answer: str  = Field(..., min_length=1, max_length=500)
    difficulty:     int  = Field(1, ge=1, le=5)


class QuestionOut(BaseModel):
    id:             int
    concept_id:     int
    question_text:  str
    correct_answer: str
    difficulty:     int


# ── Answers ───────────────────────────────────────────────────────────────────

class AnswerSubmit(BaseModel):
    user_id:     str = Field("default", max_length=80)
    question_id: int
    is_correct:  bool


class AnswerResult(BaseModel):
    question_id:   int
    is_correct:    bool
    mastery_score: float          # updated concept mastery score after this answer


# ── Knowledge Gap Detection ───────────────────────────────────────────────────

WEAK_THRESHOLD = 0.6              # concepts below this score are considered weak

class GapItem(BaseModel):
    weak_concept_id:   int
    weak_concept_name: str
    weak_score:        float      # 0.0 – 1.0
    root_gap_id:       int
    root_gap_name:     str
    root_gap_score:    float
    recommendation:    str        # human-readable message


class DiagnosisOut(BaseModel):
    gaps:            list[GapItem]
    all_scores:      dict[int, float]   # concept_id → mastery score for every concept
    weak_threshold:  float

