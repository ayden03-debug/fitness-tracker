"""
Loads data/exercises.json and data/templates.json into the database if
they aren't already present. Safe to call every app startup — it checks
before inserting.
"""
from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy.orm import Session as SASession

from core.models import (
    Exercise,
    ExercisePrescription,
    Gym,
    GymClass,
    ProgramDay,
    ProgramTemplate,
)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def seed_exercises(session: SASession) -> dict[str, Exercise]:
    existing = {e.name: e for e in session.query(Exercise).all()}
    with open(DATA_DIR / "exercises.json") as f:
        exercises = json.load(f)

    for item in exercises:
        if item["name"] not in existing:
            ex = Exercise(**item)
            session.add(ex)
            existing[item["name"]] = ex
    session.commit()
    return {e.name: e for e in session.query(Exercise).all()}


def seed_templates(session: SASession, exercises_by_name: dict[str, Exercise]) -> None:
    existing_names = {t.name for t in session.query(ProgramTemplate).all()}
    with open(DATA_DIR / "templates.json") as f:
        templates = json.load(f)

    for tmpl in templates:
        if tmpl["name"] in existing_names:
            continue
        template = ProgramTemplate(name=tmpl["name"])
        session.add(template)
        session.flush()  # get template.id

        for day in tmpl["days"]:
            program_day = ProgramDay(template_id=template.id, name=day["name"])
            session.add(program_day)
            session.flush()

            for presc in day["prescriptions"]:
                exercise = exercises_by_name.get(presc["exercise"])
                if exercise is None:
                    continue  # skip if exercise name doesn't match seed data
                session.add(
                    ExercisePrescription(
                        day_id=program_day.id,
                        exercise_id=exercise.id,
                        target_sets=presc["target_sets"],
                        target_reps=presc["target_reps"],
                    )
                )
    session.commit()


def seed_gyms(session: SASession, exercises_by_name: dict[str, Exercise]) -> None:
    """Loads data/gym_classes.json: one Gym per entry, plus a GymClass row
    per class on its schedule. Each class is stored as an Exercise
    (category='class'), reusing the seed_exercises dict/existing-name check
    so a class name never collides with a regular exercise."""
    with open(DATA_DIR / "gym_classes.json") as f:
        gyms = json.load(f)

    for gym_data in gyms:
        gym = session.query(Gym).filter_by(name=gym_data["name"]).first()
        if gym is None:
            gym = Gym(name=gym_data["name"])
            session.add(gym)
            session.flush()  # get gym.id

        offered_exercise_ids = {gc.exercise_id for gc in gym.class_offerings}

        for class_name in gym_data["classes"]:
            exercise = exercises_by_name.get(class_name)
            if exercise is None:
                exercise = Exercise(name=class_name, muscle_group="Class", category="class")
                session.add(exercise)
                session.flush()  # get exercise.id
                exercises_by_name[class_name] = exercise

            if exercise.id not in offered_exercise_ids:
                session.add(GymClass(gym_id=gym.id, exercise_id=exercise.id))
                offered_exercise_ids.add(exercise.id)

    session.commit()


def run_seed(session: SASession) -> None:
    exercises_by_name = seed_exercises(session)
    seed_templates(session, exercises_by_name)
    seed_gyms(session, exercises_by_name)
