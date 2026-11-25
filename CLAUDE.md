# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Fitness Tracker — Phase 1 MVP. A single-user Streamlit app for logging workouts, optionally against a pre-built program template (Beginner Full Body 3x, Push Pull Legs), and viewing progress over time. There is no onboarding/recommendation engine yet; that's planned as Phase 2 (see the "Architecture" section below for what that entails).

## Commands

```bash
# Setup
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Run the app (from project root)
streamlit run app/streamlit_app.py

# Run tests
pytest tests/

# Run a single test
pytest tests/test_models.py::test_seed_data_loads
```

First run auto-creates `db.sqlite` in the project root, seeds the exercise library and starter templates from `data/exercises.json` and `data/templates.json`, and creates a single default user ("You"). Everything persists in `db.sqlite` between runs. Tests use an in-memory SQLite engine (`sqlite:///:memory:`), never `db.sqlite`.

## Architecture

**Data model (`core/models.py`, SQLAlchemy ORM):** `User` → `WorkoutSession` (one per logged workout, dated) → `SetLog` (one row per set: exercise, reps, weight, optional RPE). Separately, `ProgramTemplate` → `ProgramDay` → `ExercisePrescription` defines the *planned* structure (e.g. "PPL" → "Push" → 4x6-10 Bench Press) that a `WorkoutSession` can optionally reference via `program_day_id` (nullable — freeform, template-less logging is a first-class case, not an edge case). `Exercise` is shared between the prescription side (what's planned) and the log side (what was actually done).

**Seeding (`core/seed.py`):** `run_seed()` is idempotent and called on every app startup (see `streamlit_app.py`) — it loads `data/exercises.json` and `data/templates.json`, checking existing names before inserting so re-running never duplicates rows. When adding exercises to a template in `data/templates.json`, the exercise name must exactly match an entry in `data/exercises.json`, or `seed_templates` silently skips that prescription.

**UI (`app/streamlit_app.py`):** Single-file Streamlit app with two pages via sidebar radio: "Log Workout" (select a template+day to prefill prescribed exercises, or go freeform; edit sets in a `st.data_editor` grid; save writes one `WorkoutSession` + N `SetLog` rows) and "History" (per-exercise weight-over-time line chart, plus an expandable list of past sessions). `get_session_factory()` is wrapped in `@st.cache_resource` so the engine/sessionmaker is created once per Streamlit process.

**Phase 2 (not yet implemented):** an onboarding form collecting experience level, age bracket, goals, equipment, and limitations, mapped to a template recommendation, plus an `ExerciseSubstitution` table for injury/limitation-based swaps.
