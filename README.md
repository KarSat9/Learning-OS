# Learning OS

A minimal but fully functional **Learning Operating System** — a dependency-aware study planner powered by a concept graph.

```
┌────────────────────────────────────────────┐
│              Learning OS                    │
│                                            │
│  Concept Graph  →  Algorithm  →  Study Plan │
│  (SQLite)          (Python)     (React UI)  │
└────────────────────────────────────────────┘
```

---

## Quick Start

### 1. Install dependencies
```bash
cd learning_os
pip install -r requirements.txt
```

### 2. Start the backend
```bash
cd backend
uvicorn main:app --reload --port 8000
```

### 3. Open the UI
Open `frontend/index.html` in your browser, **or** visit:
```
http://localhost:8000
```
(The FastAPI server serves the HTML directly.)

### 4. Load example data (optional)
Click **"Load ML Example"** in the sidebar, or:
```bash
cd backend && python seed.py
```

### 5. Explore the API docs
```
http://localhost:8000/docs
```

---

## Project Structure

```
learning_os/
├── backend/
│   ├── main.py          # FastAPI app — all HTTP routes
│   ├── database.py      # SQLite setup, schema, connection manager
│   ├── models.py        # Pydantic request/response models
│   ├── crud.py          # Database operations (no ORM)
│   ├── algorithm.py     # Core next-concept algorithm
│   └── seed.py          # ML curriculum example data
├── frontend/
│   └── index.html       # Single-file React UI (no build step)
├── requirements.txt
└── README.md
```

---

## Database Schema

```sql
-- Concept nodes
CREATE TABLE concepts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL UNIQUE,
    description TEXT    NOT NULL DEFAULT '',
    difficulty  INTEGER NOT NULL DEFAULT 1  -- 1 (easy) to 5 (hard)
);

-- Directed prerequisite edges
-- concept_id REQUIRES prerequisite_id to be mastered first
CREATE TABLE prerequisites (
    concept_id      INTEGER NOT NULL,
    prerequisite_id INTEGER NOT NULL,
    PRIMARY KEY (concept_id, prerequisite_id)
);

-- Learner's progress
CREATE TABLE progress (
    concept_id    INTEGER PRIMARY KEY,
    mastery_level INTEGER NOT NULL DEFAULT 0,  -- 0,1,2,3
    updated_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Mastery levels:**

| Level | Label       | Meaning                        |
|-------|-------------|--------------------------------|
| 0     | Not Started | Haven't begun                  |
| 1     | Learning    | Reading theory                 |
| 2     | Practicing  | Doing exercises                |
| 3     | Mastered    | Unlocks dependent concepts     |

---

## Core Algorithm

Located in `backend/algorithm.py`.

### Step 1 — Find Available Concepts
```
for each concept C:
    if all prerequisites of C have mastery_level == 3:
        C is available
    if C has no prerequisites:
        C is always available
    if C.mastery_level == 3:
        skip (already mastered)
```

### Step 2 — Rank Available Concepts
```
sort available_concepts by:
    (mastery_level ASC, difficulty ASC)

→ Study least-progressed, easiest concepts first
→ Quick wins build momentum before tackling hard topics
```

### Step 3 — Estimate Study Duration
```
remaining_stages = 3 - mastery_level
base_duration    = remaining_stages × difficulty × 5  (minutes)
duration         = clamp(base_duration, min=10, max=45)
```

### Step 4 — Generate Study Plan
```
return top_3(ranked_available_concepts)
```

---

## API Endpoints

| Method | Path                              | Description                        |
|--------|-----------------------------------|------------------------------------|
| GET    | /concepts                         | List all concepts + mastery        |
| POST   | /concepts                         | Create a concept                   |
| PUT    | /concepts/{id}                    | Update a concept                   |
| DELETE | /concepts/{id}                    | Delete a concept                   |
| POST   | /prerequisites                    | Link a prerequisite                |
| DELETE | /prerequisites/{cid}/{pid}        | Remove a prerequisite link         |
| PUT    | /progress/{concept_id}            | Set mastery level                  |
| GET    | /study-plan?max_tasks=3           | Get today's study plan             |
| GET    | /available-concepts               | Get currently unlocked concepts    |
| GET    | /study-order                      | Topological sort of all concepts   |
| GET    | /stats                            | Dashboard summary statistics       |
| POST   | /seed                             | Load example ML curriculum         |

---

## Example ML Curriculum

The seed script loads a realistic machine learning learning path:

```
Linear Algebra ──────────────────────┐
Calculus ─────────────────────────────┤──► Partial Derivatives ──► Chain Rule ─┐
Probability & Stats ─────────────────┘                                          │
                                                                                 ▼
Matrix Multiplication ──────────────────────────────────────────────► Backpropagation
                                                                                 │
                                                                                 ▼
                                                                       Gradient Descent
                                                                                 │
                                                                                 ▼
                                                                    Neural Network Basics
                                                                         │         │
                                                                         ▼         ▼
                                                                  Loss Functions  CNNs
                                                                         │
                                                                         ▼
                                                              Training a Neural Network
                                                                    │          │
                                                                    ▼          ▼
                                                             Regularization  Optimizers
```

The simulated learner has mastered foundations and is mid-way through ML core,
so the study plan immediately surfaces the most relevant next concepts.

---

## Design Decisions

1. **No ORM** — Raw SQLite with parameterized queries. Simple, explicit, fast.
2. **Single-file frontend** — No build step. React + Babel via CDN. Just open the HTML.
3. **Pydantic for contracts** — All API inputs/outputs are typed and validated.
4. **Context manager for DB** — Auto-commit/rollback, no leaked connections.
5. **Algorithm is pure** — `algorithm.py` takes lists + dicts, returns results. No DB access, fully testable.
6. **Foreign key cascades** — Deleting a concept automatically removes its prerequisite links and progress.

---

## Extending

- **Multi-user support**: Add a `user_id` to the `progress` table; pass it via JWT header.
- **Spaced repetition**: Track `last_reviewed_at` and schedule reviews using SM-2 algorithm.
- **Resources**: Add a `resources` table (links, books) linked to concepts.
- **Time tracking**: Log actual study sessions with start/end timestamps.
