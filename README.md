# Fitness Tracker — Phase 1 MVP

Log workouts, optionally against a pre-built program template (Beginner Full
Body, PPL), and track progress over time. No onboarding/recommendation
engine yet — that's Phase 2.

## Setup

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Run the app

```bash
streamlit run app/streamlit_app.py
```

First run auto-creates `db.sqlite` in the project root, seeds the exercise
library and two starter templates (`data/exercises.json`,
`data/templates.json`), and creates a single default user. Everything
persists in `db.sqlite` between runs.

## Run tests

```bash
pytest tests/
```

## Project structure

```
fitness-app/
├── core/
│   ├── models.py     # SQLAlchemy models
│   └── seed.py        # loads data/*.json into the DB on first run
├── data/
│   ├── exercises.json
│   └── templates.json
├── app/
│   └── streamlit_app.py
├── tests/
│   └── test_models.py
└── db.sqlite           # created on first run
```

## What's next (Phase 2)

Add `core/recommendation.py` + an onboarding form: collect experience
level, age bracket, goals, equipment, and limitations, then map that to one
of the templates (or a new one) — plus an exercise substitution table for
injury/limitation flags. The data model already has room for this, with planned `OnboardingProfile` and `ExerciseSubstitution` tables.
